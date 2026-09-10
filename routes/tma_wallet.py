"""TMA Wallet, Invoices, Top-ups, Vouchers, and Affiliate Withdrawals API Routes."""
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

import config
from db import get_db_session, session_commit
from repositories.batstore_product import BatStoreProductRepository
from repositories.gift_voucher import GiftVoucherRepository
from repositories.user import UserRepository
from services.telegram_auth import extract_and_verify_telegram_user
from routes.common import is_admin_id
router = APIRouter(tags=["wallet"])


@router.post("/api/invoice/stars")
async def create_tma_stars_invoice(request: Request):
    """Generate a Telegram Stars invoice link for direct in-app Mini App checkout."""
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    product_id = int(body.get("product_id") or 0)
    qty = max(1, min(10, int(body.get("quantity") or 1)))

    if not tg_id or not product_id:
        return JSONResponse({"error": "missing_params"}, status_code=400)

    async with get_db_session() as session:
        product = await BatStoreProductRepository.get_by_product_id(product_id, session)
        if not product:
            return JSONResponse({"error": "product_not_found"}, status_code=404)

        user = await UserRepository.get_by_tgid(tg_id, session)
        from services.sale_pricing import price_lines
        from services.user import get_vip_tier_info
        tier_label, discount_pct = get_vip_tier_info(getattr(user, "consume_records", 0.0), getattr(user, "custom_discount_pct", None))
        try:
            (total_dec,), _ = price_lines(
                [(product.sell_price_usd, product.cost_usd, qty, 0)],
                discount_pct=discount_pct)
        except ValueError:
            return JSONResponse({"error": "price_unavailable"}, status_code=400)
        total_usd = float(total_dec)

        stars_rate = float(config.GHSTORE_STARS_TO_USD or 0.01)
        stars = max(1, int(total_usd / stars_rate))

        from aiogram.types import LabeledPrice
        title = f"{product.name[:32]}"
        description = f"{qty}x {product.name} — Direct Stars Checkout"
        payload = f"stars_inapp:{tg_id}:{product_id}:{qty}:{stars}:{total_usd}"

        sub_period = int(body.get("subscription_period") or 0)
        if body.get("is_subscription") and not sub_period:
            sub_period = 2592000  # Bot API 8.0: 30 days in seconds

        invoice_kwargs = {
            "title": title,
            "description": description,
            "payload": payload,
            "provider_token": "",
            "currency": "XTR",
            "prices": [LabeledPrice(label=f"{stars} ⭐", amount=stars)],
        }
        if sub_period == 2592000:
            invoice_kwargs["subscription_period"] = sub_period

        try:
            invoice_link = await bot.create_invoice_link(**invoice_kwargs)
            return {
                "status": "ok",
                "invoice_link": invoice_link,
                "stars": stars,
                "total_usd": total_usd,
                "subscription_period": sub_period or None,
            }
        except Exception as e:
            logging.error("Failed to create in-app Stars invoice: %s", e)
            return JSONResponse({"error": "invoice_creation_failed", "detail": str(e)}, status_code=502)


@router.post("/api/invoice/topup")
async def create_tma_topup_invoice(request: Request):
    """Generate in-app top-up invoice or payment link for Stars, Crypto, or SAM."""
    from bot import bot
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    amount = float(body.get("amount") or 10.0)
    method = (body.get("method") or "stars").lower()

    if not tg_id or amount <= 0:
        return JSONResponse({"error": "invalid_params"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        if is_admin_id(tg_id):
            return JSONResponse({"error": "admin_cannot_recharge", "message": "حساب الإدارة لا يمكنه شحن الرصيد."}, status_code=403)
        if method == "stars":
            stars_rate = float(config.GHSTORE_STARS_TO_USD or 0.01)
            stars = max(1, int(amount / stars_rate))
            from aiogram.types import LabeledPrice
            title = f"GH Store ${amount:.2f} Top-up"
            description = f"Add ${amount:.2f} USD to your spendable bot balance"
            payload = f"stars_topup:{tg_id}:{stars}:{amount:.2f}"

            try:
                invoice_link = await bot.create_invoice_link(
                    title=title,
                    description=description,
                    payload=payload,
                    provider_token="",
                    currency="XTR",
                    prices=[LabeledPrice(label=f"{stars} ⭐", amount=stars)],
                )
                return {"status": "ok", "type": "stars", "invoice_link": invoice_link, "stars": stars, "amount": amount}
            except Exception as e:
                logging.error("Failed to generate Stars top-up invoice: %s", e)
                return JSONResponse({"error": "invoice_failed", "detail": str(e)}, status_code=502)

        elif method in ("crypto", "bep20", "usdt", "usdt_bep20"):
            try:
                from crypto_api.CryptoApiWrapper import CryptoApiWrapper
                from enums.currency import Currency
                from enums.cryptocurrency import Cryptocurrency
                from models.payment import PaymentType, ProcessingPaymentDTO
                payment = await CryptoApiWrapper.create_invoice(ProcessingPaymentDTO(
                    paymentType=PaymentType.PAYMENT,
                    fiatCurrency=Currency.USD,
                    fiatAmount=amount,
                    cryptoCurrency=Cryptocurrency.USDT_BEP20,
                    callbackUrl=f"{(config.WEBHOOK_HOST or '').rstrip('/')}{config.WEBHOOK_PATH}cryptoprocessing/event",
                    callbackSecret=(config.KRYPTO_EXPRESS_API_SECRET or ""),
                ))
                pay_url = getattr(payment, "paymentUrl", None) or ""
                addr = getattr(payment, "address", None) or ""
                final_url = pay_url if pay_url else (f"https://bscscan.com/address/{addr}" if addr else "")
                return {
                    "status": "ok",
                    "type": "url",
                    "provider": "crypto",
                    "url": final_url,
                    "address": addr,
                    "amount": amount,
                    "currency": "USDT",
                    "invoice_id": getattr(payment, "id", None) or str(uuid.uuid4().hex[:10]),
                }
            except Exception as e:
                logging.error("Crypto API invoice creation failed: %s", e)
                return JSONResponse({"error": "crypto_failed", "detail": str(e)}, status_code=502)

        elif method in ("sam", "shamcash", "syriatelcash", "syriatel"):
            try:
                from models.sam_payment import SamPaymentDTO
                from repositories.sam_payment import SamPaymentRepository
                from services.config import ConfigService
                from services.sam import SamService

                sam_prov = "shamcash" if method == "shamcash" else "syriatel"
                req_curr = (body.get("currency") or ("SYP" if sam_prov == "syriatel" else "USD")).upper()
                pay_curr = "SYP" if (sam_prov == "syriatel" or req_curr == "SYP") else "USD"
                inv_amt = amount

                if pay_curr == "SYP":
                    from services.currency_rates import CurrencyRateService
                    syp_cfg = await ConfigService.get(session, "SAM_SYP_USD_RATE", env_fallback=config.SAM_SYP_USD_RATE)
                    syp_rate = CurrencyRateService.parse_syp_rate(syp_cfg)
                    if not syp_rate:
                        return JSONResponse({"error": "syp_rate_unavailable", "message": "الدفع بالليرة السورية غير متاح حالياً. يرجى اختيار وسيلة أخرى."}, status_code=400)
                    inv_amt = CurrencyRateService.usd_to_syp(amount, syp_rate)

                identifier = await ConfigService.get(session, "SAM_RECEIVING_WALLET", env_fallback=config.SAM_RECEIVING_WALLET)
                webhook_url = config.get_sam_webhook_url()
                sam_inv = await SamService.create_invoice(
                    session=session,
                    method=sam_prov,
                    identifier=identifier,
                    amount=inv_amt,
                    currency=pay_curr,
                    webhook_url=webhook_url,
                )

                inv_id = str(sam_inv.get("invoiceId") or sam_inv.get("id") or "")
                pay_url = sam_inv.get("paymentUrl") or sam_inv.get("url") or ""

                if inv_id:
                    await SamPaymentRepository.create(SamPaymentDTO(
                        telegram_id=tg_id,
                        invoice_id=inv_id,
                        amount=float(inv_amt),
                        currency=pay_curr,
                        usd_amount=float(amount),
                        event="pending",
                        payment_url=pay_url,
                        method=sam_prov,
                    ), session)
                    await session_commit(session)

                return {
                    "status": "ok",
                    "type": "url",
                    "provider": sam_prov,
                    "url": pay_url,
                    "invoice_id": inv_id,
                    "amount": amount,
                    "invoice_amount": inv_amt,
                    "currency": pay_curr,
                }
            except Exception as e:
                logging.error("SAM invoice generation failed for %s: %s", sam_prov, e)
                err_str = str(e)
                if "NOT_FOUND" in err_str or "المحفظة غير موجودة" in err_str:
                    user_msg = "بوابة سيرياتيل كاش قيد الصيانة حالياً. يرجى استخدام شام كاش أو نجوم تيليجرام أو العملات الرقمية." if sam_prov == "syriatel" else "محفظة شام كاش غير متوفرة حالياً. يرجى تجربة طريقة شحن أخرى."
                    return JSONResponse({"status": "error", "error": user_msg}, status_code=400)
                return JSONResponse({"status": "error", "error": "تعذر إنشاء فاتورة الشحن حالياً. يرجى إعادة المحاولة.", "detail": err_str}, status_code=502)
    return JSONResponse({"error": "unknown_method"}, status_code=400)


@router.post("/api/invoice/check")
async def check_tma_invoice(request: Request):
    """Check payment status of a top-up invoice in real-time and refresh user balance."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    invoice_id = str(body.get("invoice_id") or "").strip()
    method = str(body.get("method") or "").lower()
    transaction_ref = str(body.get("transaction_ref") or body.get("txn_ref") or "").strip()

    if not tg_id or not invoice_id:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    from bot import redis
    lock = redis.lock(f"lock:sam:invoice:{invoice_id}", timeout=30) if redis else None
    if lock:
        acquired = await lock.acquire(blocking=False)
        if not acquired:
            return JSONResponse({"error": "check_in_progress", "message": "Verification is already in progress for this invoice."}, status_code=409)

    try:
        async with get_db_session() as session:
            user = await UserRepository.get_by_tgid(tg_id, session)
            if not user:
                return JSONResponse({"error": "user_not_found"}, status_code=404)

            is_paid = False
            credited_now = False

            if invoice_id and method in ("sam", "shamcash", "syriatelcash", "syriatel"):
                try:
                    from repositories.sam_payment import SamPaymentRepository
                    from services.referral import ReferralService
                    from services.sam import SamService
                    payment = await SamPaymentRepository.get_by_invoice_id(invoice_id, session)
                    if payment:
                        if payment.telegram_id != user.telegram_id:
                            return JSONResponse({"error": "forbidden", "message": "This invoice belongs to another account."}, status_code=403)
                        if payment.event == "invoice.paid":
                            is_paid = True
                        else:
                            if transaction_ref:
                                try:
                                    await SamService.verify_invoice(session, invoice_id, transaction_ref)
                                except Exception as verify_err:
                                    logging.warning("Upstream verify call failed for %s with ref %s: %s", invoice_id, transaction_ref, verify_err)
                            status_info = await SamService.get_invoice(session, invoice_id)
                            upstream_status = (status_info.get("status") or "").lower()
                            if upstream_status == "paid":
                                is_paid = True
                                claimed = await SamPaymentRepository.mark_event_if_not_paid(invoice_id, "invoice.paid", status_info.get("transactionRef") or transaction_ref, session)
                                if claimed:
                                    credited_now = True
                                    await ReferralService.apply_deposit_referral(payment.usd_amount, user, session)
                                await session_commit(session)
                            elif transaction_ref:
                                payment.transaction_ref = transaction_ref
                                await session_commit(session)
                except Exception as e:
                    logging.warning("Failed to check SAM invoice %s: %s", invoice_id, e)
            current_balance = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
            curr_pref = getattr(user, "currency_preference", "USD") or "USD"
            from services.user import format_currency_display

            msg = "تم تأكيد الدفع وإضافة الرصيد بنجاح! 🎉" if is_paid else "الفاتورة بانتظار الدفع أو التحويل."
            return {
                "status": "paid" if is_paid else "pending",
                "is_paid": is_paid,
                "credited_now": credited_now,
                "balance": current_balance,
                "display_balance": format_currency_display(current_balance, curr_pref),
                "message": msg
            }
    finally:
        if lock:
            try:
                await lock.release()
            except Exception:
                pass

@router.post("/api/voucher/redeem")
async def tma_redeem_voucher(request: Request):
    """Redeem a prepaid digital gift voucher code."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    code = (body.get("code") or "").strip()

    if not tg_id or not code:
        return JSONResponse({"error": "missing_code_or_id"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        if is_admin_id(tg_id):
            return JSONResponse({"error": "admin_cannot_recharge", "message": "حساب الإدارة لا يمكنه شحن الرصيد عبر كروت الهدايا."}, status_code=403)
        success, amount, msg = await GiftVoucherRepository.redeem(code, user.id, session)
        if not success:
            return JSONResponse({"error": msg}, status_code=400)

        await session_commit(session)
        user_updated = await UserRepository.get_by_tgid(tg_id, session)
        new_bal = round((user_updated.top_up_amount or 0.0) - (user_updated.consume_records or 0.0), 2)
        sym = config.CURRENCY.get_localized_symbol()

    return {
        "status": "success",
        "amount": amount,
        "new_balance": new_bal,
        "message": f"Successfully credited {amount:.2f}{sym} to your balance!",
    }


@router.post("/api/referral/withdraw")
async def request_referral_withdrawal(request: Request):
    """Customer requests affiliate commission payout to USDT BEP-20 or ShamCash."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    amount = float(body.get("amount_usd") or 0.0)
    method = str(body.get("method") or "usdt_bep20").strip().lower()
    address = str(body.get("destination_address") or "").strip()

    if amount < 20.0:
        return JSONResponse({"error": "minimum_withdrawal_is_20_usd"}, status_code=400)
    if method not in ("usdt_bep20", "shamcash"):
        return JSONResponse({"error": "invalid_withdrawal_method"}, status_code=400)
    if not address or len(address) < 6:
        return JSONResponse({"error": "invalid_destination_address"}, status_code=400)

    from bot import redis as _rw_redis
    _rw_lock = _rw_redis.lock(f"lock:referral:withdraw:{tg_id}", timeout=30) if _rw_redis else None
    if _rw_lock is not None:
        try:
            if not await _rw_lock.acquire(blocking=False):
                return JSONResponse({"error": "withdraw_in_progress"}, status_code=409)
        except Exception:
            _rw_lock = None
    withdrawal_id = None
    try:
        async with get_db_session() as session:
            user = await UserRepository.get_by_tgid(tg_id, session)
            if not user:
                return JSONResponse({"error": "user_not_found"}, status_code=404)

            from repositories.referral import ReferralRepository
            total_earned = float(await ReferralRepository.get_bonus_sum_as_referrer(user.id, session) or 0.0)
            from repositories.referral_withdrawal import ReferralWithdrawalRepository
            total_withdrawn = float(await ReferralWithdrawalRepository.get_total_withdrawn_by_tgid(user.telegram_id, session) or 0.0)
            available_commission = round(max(0.0, total_earned - total_withdrawn), 2)

            if amount > available_commission:
                return JSONResponse({
                    "error": "insufficient_commission_balance",
                    "available": available_commission,
                    "requested": amount
                }, status_code=400)
            spendable = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
            if amount > spendable:
                return JSONResponse({
                    "error": "insufficient_spendable_balance",
                    "available": spendable,
                    "requested": amount,
                    "message": "Commission already spent in store; cannot withdraw same funds twice."
                }, status_code=400)

            from models.referral_withdrawal import ReferralWithdrawalDTO
            withdrawal = await ReferralWithdrawalRepository.create(ReferralWithdrawalDTO(
                telegram_id=user.telegram_id,
                amount_usd=amount,
                method=method,
                destination_address=address,
                status="pending",
            ), session)
            await session_commit(session)
            withdrawal_id = withdrawal.id
    finally:
        if _rw_lock is not None:
            try:
                await _rw_lock.release()
            except Exception:
                pass
    if withdrawal_id is None:
        return JSONResponse({"error": "withdrawal_failed"}, status_code=500)
    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        user_mention = f"@{user.telegram_username}" if user and user.telegram_username else f"ID: {tg_id}"
        from services.notification import NotificationService
        await NotificationService.send_to_admins(
            f"💸 <b>Affiliate Withdrawal Request #{withdrawal_id}</b>\n\n"
            f"• <b>User:</b> {user_mention}\n"
            f"• <b>Amount:</b> ${amount:.2f} USD\n"
            f"• <b>Rail:</b> {method.upper()}\n"
            f"• <b>Destination:</b> <code>{address}</code>\n\n"
            f"<i>Review or approve this payout via SQLAdmin or Mini App Admin Center.</i>",
            None
        )

    return {
        "status": "success",
        "withdrawal_id": withdrawal_id,
        "amount_usd": amount,
        "message": "Withdrawal request submitted for review."
    }

