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

router = APIRouter(tags=["wallet"])


@router.post("/api/invoice/stars")
async def create_tma_stars_invoice(request: Request):
    """Generate a Telegram Stars invoice link for direct in-app Mini App checkout."""
    from bot import bot
    body = await request.json()
    tg_id = int(body.get("tg_id") or 0)
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

    tg_id = int(body.get("tg_id") or 0)
    amount = float(body.get("amount") or 10.0)
    method = (body.get("method") or "stars").lower()

    if not tg_id or amount <= 0:
        return JSONResponse({"error": "invalid_params"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

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
                    callbackSecret="secret",
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
                pay_curr = "USD"
                inv_amt = amount

                if sam_prov == "syriatel":
                    pay_curr = "SYP"
                    syp_cfg = await ConfigService.get(session, "SAM_SYP_USD_RATE", env_fallback=config.SAM_SYP_USD_RATE)
                    syp_val = float(syp_cfg or 0.002551)
                    syp_rate = (1.0 / syp_val) if syp_val < 1.0 else syp_val
                    inv_amt = round(amount * syp_rate)

                cust_ref = f"tma-{sam_prov}-{tg_id}-{uuid.uuid4().hex[:6]}"
                sam_inv = await SamService.create_invoice(
                    session=session,
                    amount=inv_amt,
                    currency=pay_curr,
                    customer_reference=cust_ref,
                    description=f"GH Store Top-up ${amount:.2f} ({sam_prov})",
                    customer_name=user.telegram_username or f"User_{tg_id}",
                    metadata={"telegram_id": tg_id, "amount_usd": amount, "method": sam_prov},
                    payment_method=sam_prov,
                )

                inv_id = str(sam_inv.get("id") or sam_inv.get("invoice_id") or "")
                pay_url = sam_inv.get("payment_url") or sam_inv.get("url") or ""

                await SamPaymentRepository.create(SamPaymentDTO(
                    telegram_id=tg_id,
                    invoice_id=inv_id,
                    customer_reference=cust_ref,
                    amount=inv_amt,
                    currency=pay_curr,
                    usd_amount=amount,
                    event="invoice.created",
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
                logging.error("SAM invoice generation failed: %s", e)
                err_str = str(e)
                return JSONResponse({"status": "error", "error": "تعذر إنشاء فاتورة الشحن حالياً. يرجى إعادة المحاولة.", "detail": err_str}, status_code=502)

    return JSONResponse({"error": "unknown_method"}, status_code=400)


@router.post("/api/invoice/check")
async def check_tma_invoice(request: Request):
    """Check payment status of a top-up invoice in real-time and refresh user balance."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    invoice_id = str(body.get("invoice_id") or "").strip()
    method = str(body.get("method") or "").lower()

    if not tg_id:
        return JSONResponse({"error": "missing_tg_id"}, status_code=400)

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
                    if payment.event == "invoice.paid":
                        is_paid = True
                    else:
                        status_info = await SamService.get_invoice(session, invoice_id)
                        upstream_status = (status_info.get("status") or "").lower()
                        if upstream_status == "paid":
                            is_paid = True
                            credited_now = True
                            await ReferralService.apply_deposit_referral(payment.usd_amount, user, session)
                            await SamPaymentRepository.mark_event(invoice_id, "invoice.paid", status_info.get("transactionRef"), session)
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


@router.post("/api/voucher/redeem")
async def tma_redeem_voucher(request: Request):
    """Redeem a prepaid digital gift voucher code."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    tg_id = int(body.get("tg_id") or 0)
    code = (body.get("code") or "").strip()

    if not tg_id or not code:
        return JSONResponse({"error": "missing_code_or_id"}, status_code=400)

    async with get_db_session() as session:
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

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

        from models.referral_withdrawal import ReferralWithdrawalDTO
        withdrawal = await ReferralWithdrawalRepository.create(ReferralWithdrawalDTO(
            telegram_id=user.telegram_id,
            amount_usd=amount,
            method=method,
            destination_address=address,
            status="pending",
        ), session)
        await session_commit(session)

        from services.notification import NotificationService
        user_mention = f"@{user.telegram_username}" if user.telegram_username else f"ID: {user.telegram_id}"
        await NotificationService.send_to_admins(
            f"💸 <b>Affiliate Withdrawal Request #{withdrawal.id}</b>\n\n"
            f"• <b>User:</b> {user_mention}\n"
            f"• <b>Amount:</b> ${amount:.2f} USD\n"
            f"• <b>Rail:</b> {method.upper()}\n"
            f"• <b>Destination:</b> <code>{address}</code>\n\n"
            f"<i>Review or approve this payout via SQLAdmin or Mini App Admin Center.</i>",
            None
        )

    return {
        "status": "success",
        "withdrawal_id": withdrawal.id,
        "amount_usd": amount,
        "message": "Withdrawal request submitted for review."
    }


@router.get("/api/recharges/{recharge_id}/receipt.pdf")
async def get_recharge_receipt_pdf(recharge_id: str, request: Request, tg_id: int | None = None):
    """Serve official vector-rendered PDF top-up receipt for completed customer deposits."""
    from fastapi import Response
    from sqlalchemy import select
    from models.sam_payment import SamPayment
    from models.stars_payment import StarsPayment
    from models.deposit import Deposit
    from services.pdf_receipt import PDFReceiptService
    from db import session_execute

    rec_data = {}
    async with get_db_session() as session:
        if recharge_id.startswith("SAM-") or recharge_id.isdigit():
            clean_id = int(recharge_id.replace("SAM-", ""))
            sp = (await session_execute(select(SamPayment).where(SamPayment.id == clean_id), session)).scalar_one_or_none()
            if sp:
                rec_data = {
                    "telegram_id": sp.telegram_id,
                    "method": getattr(sp, "method", None) or "SAM",
                    "amount_usd": sp.usd_amount,
                    "invoice_amount": sp.amount,
                    "currency": sp.currency,
                    "invoice_id": sp.invoice_id,
                    "created_at": sp.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if sp.created_at else None,
                    "approved_by_admin": False,
                }
        elif recharge_id.startswith("STR-"):
            clean_id = int(recharge_id.replace("STR-", ""))
            stp = (await session_execute(select(StarsPayment).where(StarsPayment.id == clean_id), session)).scalar_one_or_none()
            if stp:
                rec_data = {
                    "telegram_id": stp.telegram_id,
                    "method": "Telegram Stars",
                    "amount_usd": stp.usd_amount,
                    "invoice_amount": stp.stars_amount,
                    "currency": "XTR",
                    "invoice_id": stp.telegram_payment_charge_id,
                    "created_at": stp.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if stp.created_at else None,
                    "approved_by_admin": False,
                }
        elif recharge_id.startswith("CRY-"):
            clean_id = int(recharge_id.replace("CRY-", ""))
            dp = (await session_execute(select(Deposit).where(Deposit.id == clean_id), session)).scalar_one_or_none()
            if dp:
                user = await UserRepository.get_by_id(dp.user_id, session)
                rec_data = {
                    "telegram_id": user.telegram_id if user else None,
                    "method": "Crypto (USDT)",
                    "amount_usd": getattr(dp, "fiat_amount", getattr(dp, "amount", 0.0)),
                    "invoice_amount": getattr(dp, "fiat_amount", getattr(dp, "amount", 0.0)),
                    "currency": "USD",
                    "invoice_id": f"CRY-{dp.id}",
                    "created_at": dp.deposit_datetime.strftime("%Y-%m-%d %H:%M:%S UTC") if getattr(dp, "deposit_datetime", None) else None,
                    "approved_by_admin": False,
                }

        if not rec_data:
            from models.admin_audit_log import AdminAuditLog
            clean_str = recharge_id.replace("sam_", "").replace("SAM-", "")
            stmt_audit = select(AdminAuditLog).where(AdminAuditLog.action == "recharge_approved").order_by(AdminAuditLog.id.desc()).limit(20)
            logs = (await session_execute(stmt_audit, session)).scalars().all()
            for l in logs:
                det = l.details or {}
                if str(det.get("recharge_id", "")).endswith(clean_str):
                    rec_data = {
                        "telegram_id": det.get("target_user"),
                        "method": "Store Admin Recharge",
                        "amount_usd": float(det.get("amount_usd", 0.0)),
                        "currency": "USD",
                        "invoice_id": f"ADMIN-APP-{l.id}",
                        "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if getattr(l, "created_at", None) else None,
                        "approved_by_admin": True,
                    }
                    break

        if not rec_data:
            return JSONResponse({"error": "recharge_not_found"}, status_code=404)

        pdf_bytes = PDFReceiptService.generate_recharge_receipt_bytes(recharge_id, rec_data)

    clean_name_id = str(recharge_id).replace('#', '')
    filename = f"GHStore_Receipt_Recharge_{clean_name_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Cache-Control": "public, max-age=86400",
        }
    )
