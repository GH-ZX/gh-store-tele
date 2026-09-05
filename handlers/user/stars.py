import logging
import uuid

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import config
from callbacks import StarsCallback, MyProfileCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.language import Language
from repositories.user import UserRepository
from models.stars_payment import StarsPaymentDTO
from repositories.stars_payment import StarsPaymentRepository
from services.referral import ReferralService
from services.notification import NotificationService
from utils.custom_filters import IsUserExistFilter
from utils.telegram import safe_edit_message
from utils.utils import get_text

stars_router = Router(name="stars")

STAR_PRESETS = [25, 50, 100, 200, 500, 1000]


def get_rate() -> float:
    try:
        return float(config.GHSTORE_STARS_TO_USD or 0.01)
    except ValueError:
        return 0.01


def is_enabled() -> bool:
    return bool(config.GHSTORE_STARS_ENABLED)


def _back_to_menu(language: Language) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=get_text(language, BotEntity.COMMON, "back_button"),
        callback_data=MyProfileCallback.create(level=1).pack())


@stars_router.callback_query(StarsCallback.filter(F.level == 0), IsUserExistFilter())
async def stars_pick(callback: CallbackQuery, callback_data: StarsCallback,
                     language: Language):
    if not is_enabled():
        await callback.answer("Stars top-up is disabled.", show_alert=False)
        return
    kb_builder = InlineKeyboardBuilder()
    for stars in STAR_PRESETS:
        kb_builder.button(
            text=get_text(language, BotEntity.COMMON, "stars_amount_label").format(stars=stars),
            callback_data=StarsCallback.create(level=1, stars=stars).pack())
    kb_builder.adjust(3)
    kb_builder.row(_back_to_menu(language))
    await safe_edit_message(
        callback,
        get_text(language, BotEntity.COMMON, "stars_pick_amount"),
        kb_builder.as_markup(),
    )


@stars_router.callback_query(StarsCallback.filter(F.level == 1), IsUserExistFilter())
async def stars_confirm(callback: CallbackQuery, bot: Bot, callback_data: StarsCallback,
                        language: Language):
    if not is_enabled() or not callback_data.stars:
        await callback.answer()
        return
    usd = round(callback_data.stars * get_rate(), 2)
    title = "GH Store balance top-up"
    description = f"{callback_data.stars} Telegram Stars -> {usd} {config.CURRENCY.get_localized_text()} balance"
    payload = f"stars:{callback.from_user.id}:{callback_data.stars}:{usd}"
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{callback_data.stars} ⭐", amount=callback_data.stars)],
    )


@stars_router.pre_checkout_query()
async def stars_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@stars_router.message(F.successful_payment)
async def stars_successful_payment(message: Message, session: AsyncSession,
                                   language: Language):
    sp = message.successful_payment
    charge_id = getattr(sp, "telegram_payment_charge_id", None)
    if charge_id:
        existing = await StarsPaymentRepository.get_by_charge_id(charge_id, session)
        if existing is not None:
            logging.info("Duplicate Stars payment webhook ignored for charge_id=%s", charge_id)
            return

    rate = get_rate()
    usd = 0.0
    stars = 0
    tg_id = message.from_user.id
    parts = sp.invoice_payload.split(":")
    is_inapp = parts[0] == "stars_inapp"
    product_id = None
    qty = 1
    try:
        if is_inapp and len(parts) >= 6:
            # stars_inapp:tg_id:product_id:qty:stars:amount
            _, tg_id_s, pid_s, qty_s, stars_s, usd_s = parts[:6]
            tg_id = int(tg_id_s)
            product_id = int(pid_s)
            qty = int(qty_s)
            stars = int(stars_s)
            usd = round(float(usd_s), 2)
        elif len(parts) >= 4:
            # stars_topup:tg_id:stars:amount or stars:tg_id:stars:amount
            tg_id = int(parts[1])
            stars = int(parts[2])
            usd = round(float(parts[3]), 2)
        else:
            raise ValueError(f"unrecognized stars payload format: {sp.invoice_payload}")
    except Exception as e:
        logging.warning("Failed to parse Stars payload '%s': %s", sp.invoice_payload, e)
        usd = round((sp.total_amount / 1000000) * rate, 2)
    user = await UserRepository.get_by_tgid(tg_id, session)
    if user is None:
        await message.answer(get_text(language, BotEntity.COMMON, "stars_failed"))
        return

    if charge_id:
        await StarsPaymentRepository.create(StarsPaymentDTO(
            telegram_id=tg_id,
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id=getattr(sp, "provider_payment_charge_id", None),
            stars_amount=stars,
            usd_amount=usd,
            invoice_payload=sp.invoice_payload,
        ), session)

    if is_inapp and product_id:
        from repositories.batstore_product import BatStoreProductRepository
        from repositories.batstore_order import BatStoreOrderRepository
        from models.batstore_order import BatStoreOrderDTO
        from services.batstore import BatStoreService
        product = await BatStoreProductRepository.get_by_product_id(product_id, session)
        customer_ref = f"stars-{tg_id}-{uuid.uuid4().hex[:8]}"
        try:
            placed = await BatStoreService.place_order(session, product_id, qty, customer_reference=customer_ref, idempotency_key=customer_ref)
            order_obj = placed.get("order", {}) or {}
            items = order_obj.get("items") or []
            goods_list = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
            order_status = "completed" if (product and product.delivery_type in ("stock", "supplier_api")) else "pending_fulfillment"
            order = await BatStoreOrderRepository.create(BatStoreOrderDTO(
                telegram_id=tg_id, total_sell=usd, status=order_status,
                external_order_ref=str(placed.get("order", {}).get("id") or placed.get("order_id") or ""),
                customer_reference=customer_ref,
                details=[{"product_id": product_id, "name": product.name if product else "Product", "quantity": qty, "cost_usd": product.cost_usd if product else 0.0, "sell_usd": usd, "delivery_goods": goods_list}],
            ), session)
            await session_commit(session)
            goods_lines = "\n".join(f"• <code>{g}</code>" for g in goods_list[:5]) if goods_list else "Delivered shortly."
            await message.answer(f"🎉 <b>Stars Purchase Successful!</b>\n\nOrder #{order.id}: {qty}× {product.name if product else 'Item'}\n\n📦 <b>Delivered Goods:</b>\n{goods_lines}\n\n<i>(Tap credentials above to copy)</i>")
            await NotificationService.send_to_admins(f"⭐ Stars Direct Buy Order #{order.id}: tg:{tg_id} · {stars}⭐ (${usd})", None)
            return
        except Exception as e:
            logging.error("Failed to fulfill stars_inapp order directly; crediting balance: %s", e)


    await ReferralService.apply_deposit_referral(usd, user, session)
    await session_commit(session)
    sym = config.CURRENCY.get_localized_symbol()
    await message.answer(get_text(language, BotEntity.COMMON, "stars_success").format(
        stars=stars, usd=f"{usd}", sym=sym))
    await NotificationService.send_to_admins(
        f"⭐ Stars top-up by tg:{tg_id} · {stars}⭐ → {usd}{sym}", None)


@stars_router.subscription()
async def stars_subscription_update(event: "BotSubscriptionUpdated", session: AsyncSession, bot: Bot):
    """Bot API 8.3: Track user payment subscription changes for recurring Telegram Stars subscriptions."""
    tg_id = event.user.id
    payload = event.invoice_payload or ""
    state = str(event.state or "").lower()

    logging.info("BotSubscriptionUpdated event: tg:%s, state=%s, payload=%s", tg_id, state, payload)

    if state == "active":
        product_id = None
        parts = payload.split(":")
        if len(parts) >= 3 and (parts[0] in ("stars_inapp", "stars_sub")):
            try:
                product_id = int(parts[2])
            except Exception:
                pass

        goods_lines = ""
        if product_id:
            try:
                from repositories.batstore_product import BatStoreProductRepository
                from repositories.batstore_order import BatStoreOrderRepository
                from models.batstore_order import BatStoreOrderDTO
                from services.batstore import BatStoreService
                prod = await BatStoreProductRepository.get_by_product_id(product_id, session)
                if prod:
                    cust_ref = f"stars-sub-renewal-{tg_id}-{uuid.uuid4().hex[:6]}"
                    placed = await BatStoreService.place_order(
                        session, product_id, 1,
                        customer_reference=cust_ref,
                        idempotency_key=cust_ref
                    )
                    items = placed.get("order", {}).get("items") or []
                    goods = [it.get("value") or it.get("data") or str(it) for it in items] if items else []
                    await BatStoreOrderRepository.create(BatStoreOrderDTO(
                        telegram_id=tg_id,
                        total_sell=float(prod.sell_price_usd or 0.0),
                        status="completed",
                        customer_reference=cust_ref,
                        external_order_ref=str(placed.get("order", {}).get("id") or ""),
                        details=[{
                            "product_id": product_id,
                            "name": f"{prod.name} (Subscription Renewal)",
                            "quantity": 1,
                            "cost_usd": prod.cost_usd,
                            "sell_usd": prod.sell_price_usd,
                            "delivery_goods": goods,
                        }]
                    ), session)
                    await session_commit(session)
                    if goods:
                        goods_lines = "\n\n📦 <b>بيانات التفعيل الجديدة:</b>\n" + "\n".join(f"• <code>{g}</code>" for g in goods)
            except Exception as e:
                logging.error("Failed to auto-fulfill recurring Star renewal: %s", e)

        try:
            msg = (
                f"🌟 <b>تم تجديد اشتراكك بنجاح عبر نجوم تيليجرام!</b>\n\n"
                f"تم تمديد صلاحية حسابك لشهر إضافي.{goods_lines}\n\n"
                f"شكراً لاستمرارك معنا في متجر GH Store! ✨"
            )
            await bot.send_message(chat_id=tg_id, text=msg, parse_mode="HTML")
            await NotificationService.send_to_admins(
                f"🌟 Telegram Star subscription renewed: tg:{tg_id} · {payload}",
                None
            )
        except Exception as e:
            logging.warning("Failed to notify user of subscription renewal: %s", e)
    elif state in ("cancelled", "expired"):
        try:
            await bot.send_message(
                chat_id=tg_id,
                text="⚠️ <b>تم إلغاء أو انتهاء اشتراك نجوم تيليجرام</b>\n\nيمكنك إعادة تفعيل الاشتراك في أي وقت من خلال متجر GH Store.",
                parse_mode="HTML"
            )
            await NotificationService.send_to_admins(
                f"⚠️ Telegram Star subscription cancelled/expired: tg:{tg_id} · {payload}",
                None
            )
        except Exception as e:
            logging.warning("Failed to notify user of subscription cancellation: %s", e)