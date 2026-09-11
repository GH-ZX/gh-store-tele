"""TMA Orders, Checkout, Cart, Quotes, and Support Ticket API Routes."""
import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

import config
from db import get_db_session, session_commit, session_execute
from models.batstore_order import BatStoreOrderDTO
from repositories.batstore_order import BatStoreOrderRepository
from repositories.batstore_product import BatStoreProductRepository
from repositories.user import UserRepository
from services.batstore import BatStoreService
from services.notification import NotificationService
from services.sale_pricing import price_lines
from services.telegram_auth import extract_and_verify_telegram_user
from services.user import get_vip_tier_info

router = APIRouter(tags=["checkout"])


async def _send_order_delivery_receipt_telegram(telegram_id: int, order_id: int, product_name: str, total_paid: float, goods_list: list, instructions_list: list = None):
    """Send real-time Telegram receipt and keys directly to user chat on MiniApp purchase."""
    from bot import bot
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    from routes.common import normalize_delivery_good
    from services.telegram_auth import generate_session_token

    try:
        tma_host = (config.WEBHOOK_HOST or "").strip().rstrip('/')
        auth_tok = generate_session_token(telegram_id)
        ord_url = f"{tma_host}/app?tg_id={telegram_id}&auth_token={auth_tok}&startapp=ord_{order_id}"

        keys_text = ""
        if goods_list:
            clean_keys = [normalize_delivery_good(g) for g in goods_list[:4]]
            clean_keys = [k for k in clean_keys if k]
            if clean_keys:
                keys_text = "\n".join(f"<code>{k}</code>" for k in clean_keys)

        msg = (
            f"🎉 <b>تم تأكيد واستلام طلبك بنجاح! | Order Confirmed</b>\n\n"
            f"📦 <b>رقم الطلب:</b> #{order_id}\n"
            f"🛍️ <b>المنتج:</b> {product_name}\n"
            f"💰 <b>المبلغ:</b> ${total_paid:.2f} USD\n"
        )
        if keys_text:
            msg += f"\n🔑 <b>بيانات التفعيل / الاستلام:</b>\n{keys_text}\n"
        if instructions_list:
            steps_formatted = "\n".join(f"• {s}" for s in instructions_list[:3])
            msg += f"\n📋 <b>خطوات التفعيل والاستخدام:</b>\n{steps_formatted}\n"

        msg += "\n💡 <i>يمكنك متابعة تفاصيل وضمان هذا الطلب دائماً عبر زر المتجر أدناه.</i>"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 تفاصيل الطلب والإيصال", web_app=WebAppInfo(url=ord_url))]
        ])

        await bot.send_message(chat_id=telegram_id, text=msg, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logging.debug("Could not push Telegram order delivery receipt to %s: %s", telegram_id, e)

@router.post("/api/buy")
async def tma_instant_buy(request: Request):
    """In-app checkout for Telegram Mini App. Customers stay in the app without text chat redirect."""
    from bot import redis

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    product_id = int(body.get("product_id") or 0)
    quantity = max(1, min(10, int(body.get("quantity") or 1)))
    selected_item_id = body.get("selected_item_id")
    catalogue_name = str(body.get("catalogue_name") or "").strip()
    player_id = str(body.get("player_id") or "").strip()
    server_id = str(body.get("server_id") or "").strip() or None
    charname = str(body.get("charname") or "").strip() or None
    if not tg_id or not product_id:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    # Concurrency Lock: prevent double-tap race conditions
    lock = redis.lock(f"lock:checkout:{tg_id}", timeout=15)
    acquired = await lock.acquire(blocking=False)
    if not acquired:
        return JSONResponse(
            {"error": "checkout_in_progress", "message": "Another checkout is currently processing for this user."},
            status_code=409,
        )

    try:
        async with get_db_session() as session:
            user = await UserRepository.get_by_tgid(tg_id, session)
            if not user:
                return JSONResponse({"error": "user_not_found"}, status_code=404)

            product = await BatStoreProductRepository.get_by_product_id(product_id, session)
            if not product or product.hidden:
                return JSONResponse({"error": "product_not_found"}, status_code=404)
            if getattr(product, "supplier", "") == "g2bulk" and getattr(product, "delivery_type", "") in ("direct_topup", "game_recharge") and quantity != 1:
                return JSONResponse({"error": "direct_topup_quantity_one", "message": "الشحن المباشر يتم تنفيذ فئة واحدة في كل طلب."}, status_code=400)

            tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
            coupon_code = (body.get("coupon_code") or "").strip()
            coupon_type = coupon_value = None
            if coupon_code:
                from repositories.coupon import CouponRepository
                coupon = await CouponRepository.get_by_code(coupon_code, session)
                if coupon and coupon.is_active:
                    if not (coupon.usage_limit and coupon.usage_count >= coupon.usage_limit):
                        coupon_type, coupon_value = coupon.type, float(coupon.value or 0.0)
            is_reseller = bool(user and getattr(user, "is_reseller", False))
            from services.sale_pricing import compute_reseller_price
            prod_cost = float(product.cost_usd or 0.0)
            chosen_item = None

            # G2Bulk dynamic item denomination resolution
            if getattr(product, "supplier", "") == "g2bulk" and getattr(product, "extra_meta", None) and product.extra_meta.get("items"):
                for it in product.extra_meta["items"]:
                    if selected_item_id and str(it.get("id")) == str(selected_item_id):
                        chosen_item = it
                        break
                    if catalogue_name and str(it.get("name")).lower() == catalogue_name.lower():
                        chosen_item = it
                        break
                if not chosen_item and product.extra_meta["items"]:
                    chosen_item = next(
                        (item for item in product.extra_meta["items"]
                         if item.get("stock") is None or float(item.get("stock") or 0) > 0),
                        product.extra_meta["items"][0],
                    )

            if chosen_item:
                prod_cost = float(chosen_item.get("cost") or prod_cost)
                if is_reseller:
                    unit_price = float(chosen_item.get("reseller_price") or chosen_item.get("price") or product.sell_price_usd)
                else:
                    unit_price = float(chosen_item.get("price") or product.sell_price_usd)
                if not catalogue_name:
                    catalogue_name = str(chosen_item.get("name") or "")
                try:
                    if chosen_item.get("stock") is not None and float(chosen_item.get("stock") or 0) <= 0:
                        return JSONResponse({"error": "out_of_stock", "message": "هذه الفئة غير متوفرة حالياً."}, status_code=400)
                except (TypeError, ValueError):
                    pass
            elif is_reseller:
                from services.config import ConfigService
                g_reseller_m = float(await ConfigService.get(session, "GLOBAL_RESELLER_MARGIN_PERCENT", default="8.0") or 8.0)
                unit_price = compute_reseller_price(
                    cost=prod_cost,
                    retail_price=product.sell_price_usd,
                    reseller_price_usd=getattr(product, "reseller_price_usd", None),
                    reseller_margin_pct=getattr(product, "reseller_margin_pct", None),
                    global_reseller_margin_pct=g_reseller_m
                )
            else:
                unit_price = product.sell_price_usd

            # Player inputs verification for instant game recharges
            player_nickname = ""
            if getattr(product, "supplier", "") == "g2bulk" and getattr(product, "delivery_type", "") in ("direct_topup", "game_recharge"):
                req_fields = (product.extra_meta or {}).get("required_fields", ["userid"])
                if "userid" in req_fields and not player_id:
                    return JSONResponse({"error": "missing_player_id", "message": "معرف اللاعب (Player ID) مطلوب لإتمام الشحن."}, status_code=400)
                if "serverid" in req_fields and not server_id:
                    return JSONResponse({"error": "missing_server_id", "message": "معرف السيرفر / المنطقة مطلوب لإتمام الشحن."}, status_code=400)
                # Real-time player check
                try:
                    from services.g2bulk import G2BulkService
                    game_code = getattr(product, "reseller_key_override", None) or (product.extra_meta or {}).get("game_code") or "aoem"
                    val_res = await G2BulkService.check_player_id(game_code, player_id, server_id=server_id, charname=charname, session=session)
                    if not val_res.get("valid") and val_res.get("raw", {}).get("valid") == "invalid":
                        return JSONResponse({
                            "error": "invalid_player_id",
                            "message": f"معرف اللاعب غير صحيح: {val_res.get('message', 'يرجى التحقق من رقم الـ ID والسيرفر')}"
                        }, status_code=400)
                    player_nickname = val_res.get("name") or ""
                except Exception as ex_chk:
                    logging.debug("Live player check skipped or errored: %s", ex_chk)
            line_inputs = [(unit_price, prod_cost, quantity,
                            BatStoreService.get_volume_discount(quantity))]
            try:
                line_totals, _ = price_lines(
                    line_inputs, discount_pct=discount_pct,
                    coupon_type=coupon_type, coupon_value=coupon_value or 0,
                )
            except ValueError as e:
                if str(e) == "price_unavailable":
                    return JSONResponse({"error": "price_unavailable"}, status_code=400)
                raise
            total = round(float(line_totals[0]), 2)

            coupon_id_to_burn = None
            if coupon_code and coupon_type is not None:
                from repositories.coupon import CouponRepository as _CR
                _c = await _CR.get_by_code(coupon_code, session)
                if _c and _c.is_active:
                    coupon_id_to_burn = _c.id

            debited = await UserRepository.try_debit_balance(user.telegram_id, total, session)
            if not debited:
                available = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
                return JSONResponse({
                    "error": "insufficient_balance",
                    "needed": total,
                    "available": available,
                    "shortage": round(total - available, 2)
                }, status_code=400)
            if coupon_id_to_burn is not None:
                from repositories.coupon import CouponRepository
                claimed_coupon = await CouponRepository.increment_usage(coupon_id_to_burn, session)
                if not claimed_coupon:
                    await session.rollback() if hasattr(session, "rollback") else None
                    return JSONResponse({"error": "coupon_limit_reached"}, status_code=400)
            await session_commit(session)

            cust_ref = f"tma-{user.telegram_id}-{uuid.uuid4().hex[:8]}"
            idempotency_key = cust_ref

            wholesale_cost = float(prod_cost) * quantity
            from services.multi_supplier import MultiSupplierService
            supp_balance = await MultiSupplierService.get_cached_supplier_balance(product, session)

            needs_recharge = (supp_balance < wholesale_cost)
            placed = None
            goods_list = []
            upstream_id = ""
            order_status = "completed" if product.delivery_type in ("stock", "supplier_api") else "pending_fulfillment"

            if not needs_recharge:
                try:
                    extra_order_params = {
                        "player_id": player_id,
                        "server_id": server_id,
                        "charname": charname,
                        "catalogue_name": catalogue_name,
                        "selected_item_id": selected_item_id
                    }
                    placed_result = await MultiSupplierService.place_order_with_failover(
                        session, product, quantity,
                        customer_reference=cust_ref,
                        idempotency_key=idempotency_key,
                        extra_params=extra_order_params,
                    )
                    goods_list = placed_result.get("goods") or []
                    upstream_status = str(placed_result.get("status") or "").upper()
                    order_status = "completed" if goods_list or upstream_status == "COMPLETED" else "pending_fulfillment"
                except Exception as e:
                    logging.warning("Multi-supplier placement error on buy, queueing for admin recharge: %s", e)
                    needs_recharge = True

            if needs_recharge:
                order_status = "pending_supplier_recharge"

            from services.product_spec import ProductSpecParser
            if getattr(product, "supplier", "") == "g2bulk" and getattr(product, "delivery_type", "") in ("direct_topup", "game_recharge"):
                inst_ar = [
                    f"تم تنفيذ طلب شحن {catalogue_name or product.name} إلى حسابك مباشرة.",
                    f"معرف اللاعب: {player_id}" + (f" ({player_nickname})" if player_nickname else ""),
                    "يرجى فتح اللعبة والتأكد من استلام الرصيد داخل الحساب.",
                ]
                inst_en = [
                    f"Direct recharge for {catalogue_name or product.name} has been processed.",
                    f"Player ID: {player_id}" + (f" ({player_nickname})" if player_nickname else ""),
                    "Please launch the game to confirm balance.",
                ]
            elif getattr(product, "supplier", "") == "g2bulk" and getattr(product, "delivery_type", "") == "voucher" and getattr(product, "extra_meta", None):
                inst_en = product.extra_meta.get("instructions_en") or []
                inst_ar = product.extra_meta.get("instructions_ar") or []
            else:
                from services.product_spec import ProductSpecParser
                inst = ProductSpecParser.extract_clean_instructions(product.description, getattr(product, "description_ar", None), product.name)
                inst_en = inst.get("steps_en", [])
                inst_ar = inst.get("steps_ar", [])
            order_dto = BatStoreOrderDTO(
                telegram_id=user.telegram_id,
                total_sell=total,
                status=order_status,
                external_order_ref=upstream_id,
                customer_reference=cust_ref,
                details=[{
                    "product_id": product.product_id,
                    "name": f"{product.name} - {catalogue_name}" if catalogue_name else product.name,
                    "catalogue_name": catalogue_name,
                    "player_id": player_id,
                    "server_id": server_id,
                    "charname": charname,
                    "player_nickname": player_nickname,
                    "quantity": quantity,
                    "cost_usd": product.cost_usd,
                    "sell_usd": total,
                    "delivery_type": product.delivery_type,
                    "delivery_goods": goods_list,
                    "warranty_days": product.warranty_days or 0,
                    "instructions_en": inst_en,
                    "instructions_ar": inst_ar,
                    "redemption_url": (product.extra_meta or {}).get("redemption_url", "") if getattr(product, "supplier", "") == "g2bulk" else "",
                }],
            )
            order = await BatStoreOrderRepository.create(order_dto, session)
            try:
                from repositories.cartItem import CartItemRepository
                await CartItemRepository.clear_cart_by_user_id(user.id, session)
                from bot import redis
                if redis:
                    await redis.delete(f"ghstore:tma_cart:{user.telegram_id}")
            except Exception as ex_cart:
                logging.debug("Cart clear error on instant buy: %s", ex_cart)
            await session_commit(session)

            if needs_recharge:
                from services.supplier_recharge import SupplierRechargeService
                await SupplierRechargeService.notify_customer_order_queued(order.id, product.name, user.telegram_id)
                await SupplierRechargeService.notify_admin_recharge_needed(order, product, quantity, wholesale_cost, user)
                return {
                    "status": "success",
                    "order_id": order.id,
                    "product_name": product.name,
                    "quantity": quantity,
                    "total_paid": total,
                    "sym": config.CURRENCY.get_localized_symbol(),
                    "instructions_en": inst_en,
                    "instructions_ar": inst_ar,
                    "redemption_url": (product.extra_meta or {}).get("redemption_url", "") if getattr(product, "supplier", "") == "g2bulk" else "",
                    "goods": [],
                    "reseller_status": "pending_supplier_recharge",
                    "message": "تم استلام وتأكيد طلبك بنجاح! جاري التجهيز والتسليم فور اكتمال التفعيل."
                }
            # Process 0.2% referral commission from margin
            if getattr(user, "referred_by_user_id", None):
                try:
                    referrer = await UserRepository.get_by_id(user.referred_by_user_id, session)
                    if referrer:
                        margin_profit = max(0.0, total - (float(prod_cost) * quantity))
                        ref_rate_cfg = await ConfigService.get(session, "REFERRAL_MARGIN_COMMISSION_PERCENT", default="0.2")
                        ref_rate = float(ref_rate_cfg or 0.2) / 100.0
                        commission = round(margin_profit * ref_rate, 3)
                        if commission > 0.001:
                            await UserRepository.credit_balance(referrer.telegram_id, commission, session)
                            from models.referral import ReferralBonusDTO
                            from repositories.referral import ReferralRepository
                            await ReferralRepository.create(ReferralBonusDTO(
                                referral_user_id=user.id,
                                referrer_user_id=referrer.id,
                                payment_amount=total,
                                applied_referral_bonus=0.0,
                                applied_referrer_bonus=commission,
                            ), session)
                            await session_commit(session)
                            try:
                                await NotificationService.send_to_user(
                                    f"🎁 <b>عمولة إحالة جديدة!</b>\n\nقام صديقك المدعو بإتمام طلب بقيمة ${total:.2f}.\nتمت إضافة <b>+${commission:.3f}</b> إلى رصيدك!",
                                    referrer.telegram_id
                                )
                            except Exception:
                                pass
                except Exception as e:
                    logging.error("Failed to process referral margin commission: %s", e)

            asyncio.create_task(_send_order_delivery_receipt_telegram(
                telegram_id=user.telegram_id,
                order_id=order.id,
                product_name=product.name,
                total_paid=total,
                goods_list=goods_list,
                instructions_list=inst_ar or inst_en
            ))
            return {
                "status": "success",
                "order_id": order.id,
                "product_name": product.name,
                "quantity": quantity,
                "total_paid": total,
                "sym": config.CURRENCY.get_localized_symbol(),
                "goods": goods_list,
                "reseller_status": order_status,
                "instructions_en": inst_en,
                "instructions_ar": inst_ar,
                "redemption_url": (product.extra_meta or {}).get("redemption_url", "") if getattr(product, "supplier", "") == "g2bulk" else "",
            }
    finally:
        try:
            await lock.release()
        except Exception:
            pass


@router.post("/api/cart/checkout")
async def tma_cart_checkout(request: Request):
    """Atomic multi-item checkout for the Telegram Mini App Cart Drawer."""
    from bot import redis

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    items_input = body.get("items") or []
    if not tg_id or not items_input:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    # Concurrency Lock: prevent double-tap race conditions
    lock = redis.lock(f"lock:checkout:{tg_id}", timeout=20)
    acquired = await lock.acquire(blocking=False)
    if not acquired:
        return JSONResponse(
            {"error": "checkout_in_progress", "message": "Another checkout is currently processing for this user."},
            status_code=409,
        )

    try:
        async with get_db_session() as session:
            user = await UserRepository.get_by_tgid(tg_id, session)
            if not user:
                return JSONResponse({"error": "user_not_found"}, status_code=404)

            cart_products = []
            price_inputs = []
            for it in items_input:
                pid = int(it.get("product_id") or 0)
                qty = max(1, min(20, int(it.get("quantity") or 1)))
                prod = await BatStoreProductRepository.get_by_product_id(pid, session)
                if not prod or prod.hidden:
                    return JSONResponse({"error": f"Product #{pid} is unavailable"}, status_code=400)
                is_reseller = bool(user and getattr(user, "is_reseller", False))
                from services.sale_pricing import compute_reseller_price
                if is_reseller:
                    from services.config import ConfigService
                    g_reseller_m = float(await ConfigService.get(session, "GLOBAL_RESELLER_MARGIN_PERCENT", default="8.0") or 8.0)
                    unit_price = compute_reseller_price(
                        cost=prod.cost_usd,
                        retail_price=prod.sell_price_usd,
                        reseller_price_usd=getattr(prod, "reseller_price_usd", None),
                        reseller_margin_pct=getattr(prod, "reseller_margin_pct", None),
                        global_reseller_margin_pct=g_reseller_m
                    )
                else:
                    unit_price = prod.sell_price_usd
                cart_products.append({"product": prod, "quantity": qty, "unit_price": unit_price})
                price_inputs.append((unit_price, prod.cost_usd, qty,
                                    BatStoreService.get_volume_discount(qty)))

            tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
            coupon_code = (body.get("coupon_code") or "").strip()
            coupon_type = coupon_value = None
            if coupon_code:
                from repositories.coupon import CouponRepository
                coupon = await CouponRepository.get_by_code(coupon_code, session)
                if coupon and coupon.is_active:
                    if not (coupon.usage_limit and coupon.usage_count >= coupon.usage_limit):
                        coupon_type, coupon_value = coupon.type, float(coupon.value or 0.0)
            try:
                line_totals, discount_limited = price_lines(
                    price_inputs, discount_pct=discount_pct,
                    coupon_type=coupon_type, coupon_value=coupon_value or 0,
                )
            except ValueError as e:
                if str(e) == "price_unavailable":
                    return JSONResponse({"error": "price_unavailable"}, status_code=400)
                raise
            for cp, line_total in zip(cart_products, line_totals):
                cp["line_total"] = float(line_total)
            total = round(float(sum(line_totals)), 2)
            if coupon_code and coupon_type is not None:
                from repositories.coupon import CouponRepository
                coupon = await CouponRepository.get_by_code(coupon_code, session)
                if coupon and coupon.is_active:
                    await CouponRepository.increment_usage(coupon.id, session)

            debited = await UserRepository.try_debit_balance(user.telegram_id, total, session)
            if not debited:
                available = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
                return JSONResponse({
                    "error": "insufficient_balance",
                    "needed": total,
                    "available": available,
                    "shortage": round(total - available, 2)
                }, status_code=400)
            await session_commit(session)

            all_goods = []
            order_details = []
            failed_refund_total = 0.0
            for cp in cart_products:
                prod = cp["product"]
                qty = cp["quantity"]
                cust_ref = f"cart-{user.telegram_id}-{prod.product_id}-{uuid.uuid4().hex[:6]}"
                goods_list = []
                try:
                    from services.multi_supplier import MultiSupplierService
                    placed_result = await MultiSupplierService.place_order_with_failover(
                        session, prod, qty,
                        customer_reference=cust_ref,
                        idempotency_key=cust_ref
                    )
                    goods_list = placed_result.get("goods") or []
                    all_goods.extend(goods_list)
                except Exception as e:
                    logging.error("Failed to place item #%s in cart checkout: %s", prod.product_id, e)
                    failed_refund_total += float(cp["line_total"])

                from services.product_spec import ProductSpecParser
                c_inst = ProductSpecParser.extract_clean_instructions(prod.description, getattr(prod, "description_ar", None), prod.name)
                order_details.append({
                    "product_id": prod.product_id,
                    "name": prod.name,
                    "quantity": qty,
                    "cost_usd": prod.cost_usd,
                    "sell_usd": cp["line_total"],
                    "delivery_type": prod.delivery_type,
                    "delivery_goods": goods_list,
                    "warranty_days": prod.warranty_days or 0,
                    "instructions_en": c_inst.get("steps_en", []),
                    "instructions_ar": c_inst.get("steps_ar", []),
                })

            if failed_refund_total > 0.0:
                await UserRepository.refund_balance(user.telegram_id, failed_refund_total, session)
                logging.info("Auto-refunded %.2f to user %s for failed cart items", failed_refund_total, user.telegram_id)

            final_status = "completed" if all_goods else ("refunded" if failed_refund_total >= total else "partially_completed")
            order = await BatStoreOrderRepository.create(BatStoreOrderDTO(
                telegram_id=user.telegram_id,
                total_sell=total,
                status=final_status,
                customer_reference=f"cart-{uuid.uuid4().hex[:10]}",
                details=order_details
            ), session)
            await session_commit(session)
            try:
                from repositories.cartItem import CartItemRepository
                await CartItemRepository.clear_cart_by_user_id(user.id, session)
                await redis.delete(f"ghstore:tma_cart:{user.telegram_id}")
                await session_commit(session)
            except Exception as ex_cart:
                logging.debug("Cart clear error on cart checkout: %s", ex_cart)
            cart_desc = ", ".join(it.get("name") or "Product" for it in cart_products[:2])
            if len(cart_products) > 2:
                cart_desc += f" (+{len(cart_products) - 2})"
            first_inst = order_details[0] if order_details else {}
            asyncio.create_task(_send_order_delivery_receipt_telegram(
                telegram_id=user.telegram_id,
                order_id=order.id,
                product_name=f"{len(cart_products)} منتجات: {cart_desc}",
                total_paid=total,
                goods_list=all_goods,
                instructions_list=first_inst.get("instructions_ar") or first_inst.get("instructions_en")
            ))
            sym = config.CURRENCY.get_localized_symbol()
            return {
                "status": "success",
                "order_id": order.id,
                "total_paid": total,
                "sym": sym,
                "goods": all_goods,
                "items_count": len(cart_products),
                "instructions_en": first_inst.get("instructions_en", []),
                "instructions_ar": first_inst.get("instructions_ar", []),
            }
    finally:
        try:
            await lock.release()
        except Exception:
            pass


@router.post("/api/cart/sync")
async def tma_cart_sync(request: Request):
    """Sync client-side TMA cart to Redis for abandoned cart recovery notifications."""
    from bot import redis

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    items = body.get("items") or []
    key = f"ghstore:tma_cart:{tg_id}"
    if not items:
        try:
            await redis.delete(key)
        except Exception:
            pass
        return {"status": "cleared"}

    cart_data = {
        "tg_id": tg_id,
        "items": items,
        "updated_at": time.time()
    }
    try:
        await redis.setex(key, 604800, json.dumps(cart_data))
    except Exception as e:
        logging.warning("Failed to sync TMA cart to Redis: %s", e)
    return {"status": "synced", "items_count": len(items)}


@router.post("/api/price-quote")
async def tma_price_quote(request: Request):
    """Authoritative cost-floored quote shared by checkout; never exposes supplier costs."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    items_input = body.get("items") or []
    if not tg_id or not items_input:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session) if tg_id else None
        if user:
            _, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0),
                                                getattr(user, "custom_discount_pct", None))
        else:
            discount_pct = 0.0
        price_inputs, quote_meta = [], []
        for it in items_input:
            pid = int(it.get("product_id") or 0)
            qty = max(1, min(20, int(it.get("quantity") or 1)))
            prod = await BatStoreProductRepository.get_by_product_id(pid, session)
            if not prod or prod.hidden:
                return JSONResponse({"error": f"Product #{pid} is unavailable"}, status_code=400)
            is_reseller = bool(user and getattr(user, "is_reseller", False))
            from services.sale_pricing import compute_reseller_price
            quote_cost = float(prod.cost_usd or 0.0)
            quote_item = None
            if getattr(prod, "supplier", "") == "g2bulk" and getattr(prod, "extra_meta", None):
                item_list = prod.extra_meta.get("items") or []
                selected_item_id = it.get("selected_item_id")
                catalogue_name = str(it.get("catalogue_name") or "").strip()
                for candidate in item_list:
                    if selected_item_id is not None and str(candidate.get("id")) == str(selected_item_id):
                        quote_item = candidate
                        break
                    if catalogue_name and str(candidate.get("name") or "").lower() == catalogue_name.lower():
                        quote_item = candidate
                        break
                if not quote_item and (selected_item_id is not None or catalogue_name):
                    return JSONResponse({"error": "invalid_game_denomination"}, status_code=400)
                if not quote_item and item_list:
                    quote_item = next(
                        (item for item in item_list
                         if item.get("stock") is None or float(item.get("stock") or 0) > 0),
                        item_list[0],
                    )
                try:
                    if quote_item.get("stock") is not None and float(quote_item.get("stock") or 0) <= 0:
                        return JSONResponse({"error": "out_of_stock"}, status_code=400)
                except (TypeError, ValueError):
                    pass

            if quote_item:
                quote_cost = float(quote_item.get("cost") or quote_cost)
                retail_price = float(quote_item.get("price") or prod.sell_price_usd)
                reseller_price = quote_item.get("reseller_price") or retail_price
                unit_price = float(reseller_price if is_reseller else retail_price)
            elif is_reseller:
                from services.config import ConfigService
                g_reseller_m = float(await ConfigService.get(session, "GLOBAL_RESELLER_MARGIN_PERCENT", default="8.0") or 8.0)
                unit_price = compute_reseller_price(
                    cost=quote_cost,
                    retail_price=prod.sell_price_usd,
                    reseller_price_usd=getattr(prod, "reseller_price_usd", None),
                    reseller_margin_pct=getattr(prod, "reseller_margin_pct", None),
                    global_reseller_margin_pct=g_reseller_m
                )
            else:
                unit_price = prod.sell_price_usd
            price_inputs.append((unit_price, quote_cost, qty,
                                BatStoreService.get_volume_discount(qty)))
            quote_meta.append({"product_id": pid, "quantity": qty})
        coupon_code = (body.get("coupon_code") or "").strip()
        coupon_type = coupon_value = None
        if coupon_code:
            from repositories.coupon import CouponRepository
            coupon = await CouponRepository.get_by_code(coupon_code, session)
            if coupon and coupon.is_active:
                if not (coupon.usage_limit and coupon.usage_count >= coupon.usage_limit):
                    coupon_type, coupon_value = coupon.type, float(coupon.value or 0.0)
        try:
            line_totals, discount_limited = price_lines(
                price_inputs, discount_pct=discount_pct,
                coupon_type=coupon_type, coupon_value=coupon_value or 0)
        except ValueError as e:
            if str(e) == "price_unavailable":
                return JSONResponse({"error": "price_unavailable"}, status_code=400)
            raise
        lines = [{**meta, "total": float(total)} for meta, total in zip(quote_meta, line_totals)]
    return {"total": round(float(sum(line_totals)), 2), "lines": lines, "discount_limited": discount_limited}


@router.post("/api/coupon/validate")
async def tma_validate_coupon(request: Request):
    """Validate a promo/coupon code and compute discount for Mini App checkout."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    code = (body.get("code") or "").strip()
    subtotal = float(body.get("subtotal") or 0.0)
    if not code:
        return JSONResponse({"error": "missing_code"}, status_code=400)

    from repositories.coupon import CouponRepository
    async with get_db_session() as session:
        coupon = await CouponRepository.get_by_code(code, session)
        if not coupon or not coupon.is_active:
            return JSONResponse({"valid": False, "error": "كود الخصم غير صالح أو منتهي الصلاحية"}, status_code=400)

        if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
            return JSONResponse({"valid": False, "error": "تم استنفاد الحد الأقصى لاستخدام هذا الكود"}, status_code=400)

        from services.sale_pricing import normalize_coupon_type
        discount = 0.0
        if normalize_coupon_type(coupon.type) == "PERCENTAGE":
            discount = round(subtotal * (float(coupon.value) / 100.0), 2)
        else:
            discount = round(float(coupon.value), 2)

        discount = min(discount, subtotal)
        new_total = max(0.01, round(subtotal - discount, 2))

    return {
        "valid": True,
        "code": coupon.code,
        "type": coupon.type.value if hasattr(coupon.type, "value") else str(coupon.type),
        "value": float(coupon.value),
        "discount": discount,
        "new_total": new_total,
        "message": f"تم تطبيق كود الخصم بنجاح (-${discount:.2f})!"
    }


@router.post("/api/warranty/claim")
async def tma_claim_warranty(request: Request):
    """Claim warranty replacement directly from inside the Mini App."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    order_id = int(body.get("order_id") or 0)

    async with get_db_session() as session:
        order = await BatStoreOrderRepository.get_by_id(order_id, session)
        if not order or order.telegram_id != tg_id or order.status != "completed":
            return JSONResponse({"error": "order_not_eligible"}, status_code=400)
        if getattr(order, "warranty_claimed", False):
            return JSONResponse({"error": "already_claimed"}, status_code=400)

        details = order.details or []
        pid = details[0].get("product_id") if details else None
        if not pid:
            return JSONResponse({"error": "missing_product_info"}, status_code=400)

        repl_ref = f"warranty-tma-{order.id}-{tg_id}"
        try:
            placed = await BatStoreService.place_order(
                session, pid, 1,
                customer_reference=repl_ref,
                idempotency_key=repl_ref,
            )
            items = placed.get("order", {}).get("items") or []
            goods_list = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
            await BatStoreOrderRepository.mark_warranty_claimed(order.id, True, session)
            await session_commit(session)
            await NotificationService.send_to_admins(
                f"🛡️ Automated warranty issued for #{order.id} (tg:{tg_id}) via Mini App",
                None
            )
            return {"status": "success", "goods": goods_list}
        except Exception as e:
            await BatStoreOrderRepository.mark_warranty_claimed(order.id, True, session)
            await session_commit(session)
            await NotificationService.send_to_admins(
                f"🛡️ Manual warranty claim for #{order.id} (tg:{tg_id}) via Mini App: {e}",
                None
            )
            return {"status": "pending_manual_review"}


@router.post("/api/restock/subscribe")
async def tma_restock_subscribe(request: Request):
    """Subscribe user to in-app restock notification when out-of-stock product returns."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    product_id = int(body.get("product_id") or 0)
    if not tg_id or not product_id:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        user_id = user.id if user else None
        lang = user.language if user and user.language else "ar"

        from repositories.restock_subscription import RestockSubscriptionRepository
        await RestockSubscriptionRepository.subscribe(
            telegram_id=tg_id,
            user_id=user_id,
            batstore_product_id=product_id,
            subcategory_id=None,
            language=lang,
            session=session
        )
        await session_commit(session)

    return {"status": "success", "message": "تم تفعيل التنبيه فور توفر المنتج بنجاح!"}


@router.post("/api/support/ticket")
async def submit_support_ticket(request: Request):
    """In-app customer support inquiry dispatched to admin Telegram topic."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    subject = str(body.get("subject") or "استفسار عام / General Inquiry").strip()
    message = str(body.get("message") or "").strip()
    order_id = body.get("order_id")

    if not message or len(message) < 3:
        return JSONResponse({"error": "message_too_short"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        username_str = f"@{user.telegram_username}" if (user and user.telegram_username) else f"tg:{tg_id}"
        ticket_id = int(time.time()) % 100000
        ticket_card = (
            f"🎫 <b>تذكرة دعم فني جديدة #{ticket_id}</b>\n\n"
            f"• <b>العميل:</b> {username_str} (<code>{tg_id}</code>)\n"
            f"• <b>الطلب المتعلق:</b> #{order_id or 'لا يوجد'}\n"
            f"• <b>الموضوع:</b> {subject}\n\n"
            f"📝 <b>نص الرسالة:</b>\n{message}"
        )
        await NotificationService.send_to_admins(ticket_card, None)
    return {"status": "success", "ticket_id": ticket_id}

