"""Telegram Mini App (TMA) SMS Activation API Routes.

Provides virtual SMS number allocation, live incoming code polling, and order
lifecycle management (finish, cancel, and ban) using 5sim with admin controls.
"""
import datetime
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, desc

import config
from db import get_db_session, session_commit
from models.order import Order
from models.sms_activation import SmsActivation, SmsServiceConfig, SmsCountryConfig
from repositories.user import UserRepository
from routes.common import verify_admin
from services.fivesim import (
    FiveSimService,
    FiveSimAPIError,
    FiveSimOutOfStockError,
    FiveSimLowBalanceError
)
from services.telegram_auth import extract_and_verify_telegram_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sms"])


@router.get("/api/sms/services")
async def get_sms_services():
    """Return active popular SMS services (Telegram, WhatsApp, OpenAI, etc.)."""
    async with get_db_session() as session:
        result = await session.execute(
            select(SmsServiceConfig)
            .where(SmsServiceConfig.is_enabled == True)
            .order_by(SmsServiceConfig.sort_order.asc())
        )
        services = result.scalars().all()
        return {
            "status": "ok",
            "services": [
                {
                    "code": s.service_code,
                    "name_en": s.name_en,
                    "name_ar": s.name_ar,
                    "icon": s.icon,
                    "sort_order": s.sort_order,
                }
                for s in services
            ],
        }


@router.get("/api/sms/countries")
async def get_sms_countries():
    """Return active good-rate regions/countries (USA, UK, Netherlands, etc.)."""
    async with get_db_session() as session:
        result = await session.execute(
            select(SmsCountryConfig)
            .where(SmsCountryConfig.is_enabled == True)
            .order_by(SmsCountryConfig.sort_order.asc())
        )
        countries = result.scalars().all()
        return {
            "status": "ok",
            "countries": [
                {
                    "code": c.country_code,
                    "name_en": c.name_en,
                    "name_ar": c.name_ar,
                    "flag_emoji": c.flag_emoji,
                    "sort_order": c.sort_order,
                }
                for c in countries
            ],
        }


@router.get("/api/sms/quote")
async def get_sms_price_quote(service: str, country: str):
    """Fetch real-time price quote and stock for a service and country."""
    if not service or not country:
        return JSONResponse({"error": "missing_parameters"}, status_code=400)

    try:
        prices_data = await FiveSimService.get_prices(country=country, service=service)
        # 5sim structure: { country: { service: { operator: { cost: X, count: Y } } } }
        country_data = prices_data.get(country, {})
        service_data = country_data.get(service, {})
        if not service_data:
            return JSONResponse({"error": "service_unavailable_in_country", "available": False}, status_code=404)

        # Find best operator rate
        min_cost_rub = None
        total_count = 0
        for op_name, op_info in service_data.items():
            cost = float(op_info.get("cost", 0.0))
            count = int(op_info.get("count", 0))
            total_count += count
            if count > 0 and (min_cost_rub is None or cost < min_cost_rub):
                min_cost_rub = cost

        if min_cost_rub is None or total_count <= 0:
            return JSONResponse({"error": "out_of_stock", "available": False, "count": 0}, status_code=200)

        cost_usd = round(min_cost_rub * FiveSimService.RUB_TO_USD_RATE, 2)
        # Apply margin: min margin $0.20 or 25%
        margin_pct = float(config.MARGIN_PERCENT or 25.0)
        sell_price_usd = round(max(cost_usd * (1.0 + margin_pct / 100.0), cost_usd + 0.20), 2)

        return {
            "status": "ok",
            "service": service,
            "country": country,
            "available": True,
            "stock_count": total_count,
            "cost_usd": cost_usd,
            "sell_price_usd": sell_price_usd,
        }
    except Exception as e:
        logger.error("Error getting SMS quote for %s in %s: %s", service, country, e)
        return JSONResponse({"error": str(e), "available": False}, status_code=500)


@router.post("/api/sms/buy")
async def buy_sms_activation(request: Request):
    """Purchase a virtual number for SMS verification."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        tg_id = extract_and_verify_telegram_user(request, int(body.get("tg_id") or 0))
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    service = str(body.get("service") or "").strip().lower()
    country = str(body.get("country") or "").strip().lower()
    operator = str(body.get("operator") or "any").strip().lower()

    if not service or not country:
        return JSONResponse({"error": "missing_service_or_country"}, status_code=400)

    async with get_db_session() as session:
        # 1. Verify service and country are enabled
        svc_res = await session.execute(
            select(SmsServiceConfig).where(
                SmsServiceConfig.service_code == service,
                SmsServiceConfig.is_enabled == True
            )
        )
        if not svc_res.scalar_one_or_none():
            return JSONResponse({"error": "service_disabled_by_admin"}, status_code=400)

        ctry_res = await session.execute(
            select(SmsCountryConfig).where(
                SmsCountryConfig.country_code == country,
                SmsCountryConfig.is_enabled == True
            )
        )
        if not ctry_res.scalar_one_or_none():
            return JSONResponse({"error": "country_disabled_by_admin"}, status_code=400)

        # 2. Verify User and Balance
        user = await UserRepository.get_by_tgid(tg_id, session)
        if not user:
            return JSONResponse({"error": "user_not_found"}, status_code=404)

        current_balance = float(user.top_up_amount or 0.0) - float(user.consume_records or 0.0)

        # 3. Get expected price
        try:
            prices_data = await FiveSimService.get_prices(country=country, service=service)
            country_data = prices_data.get(country, {}).get(service, {})
            min_cost_rub = min((float(v.get("cost", 999)) for k, v in country_data.items() if int(v.get("count", 0)) > 0), default=None)
            if min_cost_rub is None:
                return JSONResponse({"error": "no_stock_available"}, status_code=400)
            cost_usd = round(min_cost_rub * FiveSimService.RUB_TO_USD_RATE, 2)
            margin_pct = float(config.MARGIN_PERCENT or 25.0)
            sell_price_usd = round(max(cost_usd * (1.0 + margin_pct / 100.0), cost_usd + 0.20), 2)
        except Exception:
            sell_price_usd = 0.50
            cost_usd = 0.25

        if current_balance < sell_price_usd:
            return JSONResponse({
                "error": "insufficient_balance",
                "required_usd": sell_price_usd,
                "current_balance": round(current_balance, 2)
            }, status_code=402)

        # 4. Call 5sim to allocate number
        try:
            activation_data = await FiveSimService.buy_activation(country, service, operator)
        except FiveSimOutOfStockError:
            return JSONResponse({"error": "no_numbers_available"}, status_code=404)
        except FiveSimLowBalanceError:
            return JSONResponse({"error": "supplier_liquidity_issue"}, status_code=503)
        except FiveSimAPIError as e:
            return JSONResponse({"error": f"supplier_error: {e}"}, status_code=502)

        # 5. Debit user wallet atomically
        debited = await UserRepository.try_debit_balance(
            tg_id,
            sell_price_usd,
            session,
            reference=f"sms_deb_{activation_data['activation_id']}",
            description=f"SMS Activation {service} ({country})",
            supplier="5sim",
            supplier_cost=activation_data.get("cost_usd"),
            supplier_currency="USD",
        )
        if not debited:
            try:
                await FiveSimService.cancel_order(activation_data["activation_id"])
            except Exception:
                pass
            return JSONResponse({"error": "insufficient_balance"}, status_code=402)

        # Parse expiration
        expires_str = activation_data.get("expires")
        expires_dt = None
        if expires_str:
            try:
                expires_dt = datetime.datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            except Exception:
                expires_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
        else:
            expires_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)

        # 6. Create Order and SmsActivation records
        order = Order(
            telegram_id=tg_id,
            total_sell=sell_price_usd,
            status="pending_sms",
            external_order_ref=activation_data["activation_id"],
            customer_reference=f"sms-{activation_data['activation_id']}",
            details=[{
                "type": "sms_activation",
                "service": service,
                "country": country,
                "operator": activation_data.get("operator", operator),
                "phone": activation_data["phone"],
                "activation_id": activation_data["activation_id"],
                "sell_usd": sell_price_usd,
                "cost_usd": cost_usd,
                "status": "pending_sms",
                "expires_at": expires_dt.isoformat(),
            }]
        )
        session.add(order)
        await session.flush()

        activation = SmsActivation(
            order_id=order.id,
            telegram_id=tg_id,
            activation_id=activation_data["activation_id"],
            service=service,
            country=country,
            operator=activation_data.get("operator", operator),
            phone=activation_data["phone"],
            cost_rub=activation_data.get("price_rub", 0.0),
            cost_usd=cost_usd,
            sell_price_usd=sell_price_usd,
            status="pending",
            expires_at=expires_dt,
        )
        session.add(activation)
        await session.commit()

        return {
            "status": "ok",
            "order_id": order.id,
            "activation_id": activation.activation_id,
            "phone": activation.phone,
            "service": service,
            "country": country,
            "expires_at": expires_dt.isoformat(),
            "expires_in_seconds": max(0, int((expires_dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds())),
            "sell_price_usd": sell_price_usd,
        }


@router.get("/api/sms/order/{activation_id}")
async def get_sms_order_status(activation_id: str, request: Request):
    """Check live status of an allocated SMS number and poll for incoming SMS."""
    async with get_db_session() as session:
        result = await session.execute(
            select(SmsActivation).where(SmsActivation.activation_id == str(activation_id))
        )
        activation = result.scalar_one_or_none()
        if not activation:
            return JSONResponse({"error": "activation_not_found"}, status_code=404)

        # If already terminal, return stored state
        if activation.status in ("finished", "canceled", "timeout", "banned") and activation.sms_code:
            return {
                "status": activation.status,
                "phone": activation.phone,
                "sms_code": activation.sms_code,
                "sms_text": activation.sms_text,
                "completed": True,
            }

        # Check upstream 5sim
        try:
            upstream = await FiveSimService.check_order(activation.activation_id)
            up_status = upstream.get("status", "PENDING").upper()
            sms_code = upstream.get("sms_code")
            sms_text = upstream.get("sms_text")

            now_utc = datetime.datetime.now(datetime.timezone.utc)

            # Check if SMS arrived
            if sms_code:
                activation.sms_code = str(sms_code)
                activation.sms_text = str(sms_text or "")
                activation.status = "received"

                # Update associated order
                if activation.order_id:
                    ord_res = await session.execute(select(Order).where(Order.id == activation.order_id))
                    order = ord_res.scalar_one_or_none()
                    if order:
                        order.status = "completed"
                        details = list(order.details or [])
                        if details:
                            details[0]["status"] = "completed"
                            details[0]["sms_code"] = sms_code
                            details[0]["delivery_goods"] = [activation.phone, f"Code: {sms_code}"]
                            order.details = details

                # Auto finish upstream
                await FiveSimService.finish_order(activation.activation_id)
                activation.status = "finished"
                await session.commit()

                return {
                    "status": "finished",
                    "phone": activation.phone,
                    "sms_code": sms_code,
                    "sms_text": sms_text,
                    "completed": True,
                }

            # Check for upstream timeout / cancel
            if up_status in ("CANCELED", "TIMEOUT") or (activation.expires_at and activation.expires_at < now_utc):
                activation.status = "timeout" if up_status == "TIMEOUT" else "canceled"
                # Auto refund customer if not refunded yet
                if activation.order_id:
                    ord_res = await session.execute(select(Order).where(Order.id == activation.order_id))
                    order = ord_res.scalar_one_or_none()
                    if order and order.status != "refunded":
                        order.status = "refunded"
                        await UserRepository.refund_balance(order.telegram_id, activation.sell_price_usd, session)

                await session.commit()
                return {
                    "status": activation.status,
                    "phone": activation.phone,
                    "sms_code": None,
                    "completed": True,
                    "refunded": True,
                }

            seconds_left = max(0, int((activation.expires_at - now_utc).total_seconds())) if activation.expires_at else 0
            return {
                "status": "pending",
                "phone": activation.phone,
                "sms_code": None,
                "seconds_left": seconds_left,
                "completed": False,
            }
        except Exception as e:
            logger.error("Error polling 5sim order %s: %s", activation_id, e)
            return JSONResponse({"status": activation.status, "error": str(e)}, status_code=500)


@router.post("/api/sms/order/{activation_id}/cancel")
async def cancel_sms_order(activation_id: str, request: Request):
    """User or admin cancels number if no code arrived, triggering immediate refund."""
    async with get_db_session() as session:
        result = await session.execute(
            select(SmsActivation).where(SmsActivation.activation_id == str(activation_id))
        )
        activation = result.scalar_one_or_none()
        if not activation:
            return JSONResponse({"error": "activation_not_found"}, status_code=404)

        if activation.status in ("finished", "received") or activation.sms_code:
            return JSONResponse({"error": "cannot_cancel_received_sms"}, status_code=400)

        if activation.status in ("canceled", "timeout"):
            return JSONResponse({"status": "already_canceled"}, status_code=200)

        # Cancel upstream in 5sim
        await FiveSimService.cancel_order(activation.activation_id)
        activation.status = "canceled"

        # Refund user wallet
        if activation.order_id:
            ord_res = await session.execute(select(Order).where(Order.id == activation.order_id))
            order = ord_res.scalar_one_or_none()
            if order and order.status != "refunded":
                order.status = "refunded"
                details = list(order.details or [])
                if details:
                    details[0]["status"] = "refunded"
                    details[0]["refund_applied"] = True
                    order.details = details
                await UserRepository.refund_balance(order.telegram_id, activation.sell_price_usd, session)

        await session.commit()
        return {
            "status": "ok",
            "message": "activation_canceled_and_refunded",
            "refunded_usd": activation.sell_price_usd,
        }


@router.post("/api/sms/order/{activation_id}/ban")
async def ban_sms_order(activation_id: str, request: Request):
    """Report a phone number as already used / banned by the target service."""
    async with get_db_session() as session:
        result = await session.execute(
            select(SmsActivation).where(SmsActivation.activation_id == str(activation_id))
        )
        activation = result.scalar_one_or_none()
        if not activation:
            return JSONResponse({"error": "activation_not_found"}, status_code=404)

        if activation.status in ("finished", "received"):
            return JSONResponse({"error": "cannot_ban_received_sms"}, status_code=400)

        # Ban upstream
        await FiveSimService.ban_order(activation.activation_id)
        activation.status = "banned"

        # Refund user
        if activation.order_id:
            ord_res = await session.execute(select(Order).where(Order.id == activation.order_id))
            order = ord_res.scalar_one_or_none()
            if order and order.status != "refunded":
                order.status = "refunded"
                await UserRepository.refund_balance(order.telegram_id, activation.sell_price_usd, session)

        await session.commit()
        return {
            "status": "ok",
            "message": "number_banned_and_refunded",
            "refunded_usd": activation.sell_price_usd,
        }


# --- Admin Controls for 5sim Services & Countries ---
@router.get("/api/admin/sms/settings")
async def admin_get_sms_settings(request: Request):
    """Admin endpoint to list all available services and countries with toggle states."""
    tg_id = request.headers.get("X-Telegram-User-Id")
    if not verify_admin(tg_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    async with get_db_session() as session:
        from services.config import ConfigService
        svcs = (await session.execute(select(SmsServiceConfig).order_by(SmsServiceConfig.sort_order))).scalars().all()
        ctries = (await session.execute(select(SmsCountryConfig).order_by(SmsCountryConfig.sort_order))).scalars().all()

        fivesim_key = await ConfigService.get(session, "FIVESIM_API_KEY", env_fallback=getattr(config, "FIVESIM_API_KEY", "") or "")
        fivesim_url = await ConfigService.get(session, "FIVESIM_API_URL", default="https://5sim.net/v1")
        fivesim_enabled = (await ConfigService.get(session, "FIVESIM_ENABLED", default="true")).lower() == "true"
        fivesim_rate = float(await ConfigService.get(session, "FIVESIM_RUB_USD_RATE", default="0.011") or 0.011)

        # Fetch 5sim wallet balance
        balance_info = {}
        try:
            balance_info = await FiveSimService.get_balance(session=session)
        except Exception as e:
            balance_info = {"error": str(e)}

        return {
            "status": "ok",
            "balance": balance_info,
            "config": {
                "api_key_configured": bool(fivesim_key),
                "api_key_masked": (fivesim_key[:6] + "..." + fivesim_key[-4:]) if len(fivesim_key or "") > 10 else ("configured" if fivesim_key else ""),
                "api_url": fivesim_url,
                "is_enabled": fivesim_enabled,
                "rub_usd_rate": fivesim_rate,
            },
            "services": [
                {
                    "id": s.id,
                    "code": s.service_code,
                    "name_en": s.name_en,
                    "name_ar": s.name_ar,
                    "is_enabled": s.is_enabled,
                }
                for s in svcs
            ],
            "countries": [
                {
                    "id": c.id,
                    "code": c.country_code,
                    "name_en": c.name_en,
                    "name_ar": c.name_ar,
                    "flag": c.flag_emoji,
                    "is_enabled": c.is_enabled,
                }
                for c in ctries
            ],
        }


@router.post("/api/admin/sms/config")
async def admin_update_sms_config(request: Request):
    """Admin updates 5sim API key, URL, enabled status, and rate."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    admin_id = body.get("admin_tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    api_key = str(body.get("api_key") or "").strip()
    api_url = str(body.get("api_url") or "").strip()
    is_enabled = body.get("is_enabled")
    rate = body.get("rub_usd_rate")

    async with get_db_session() as session:
        from services.config import ConfigService
        if api_key:
            await ConfigService.set(session, "FIVESIM_API_KEY", api_key)
        if api_url:
            await ConfigService.set(session, "FIVESIM_API_URL", api_url)
        if is_enabled is not None:
            await ConfigService.set(session, "FIVESIM_ENABLED", "true" if is_enabled else "false")
        if rate is not None and str(rate).strip():
            try:
                r_val = float(rate)
                if r_val > 0:
                    await ConfigService.set(session, "FIVESIM_RUB_USD_RATE", str(r_val))
            except ValueError:
                pass
        await session_commit(session)

    return {"status": "ok"}


@router.post("/api/admin/sms/services/toggle")
async def admin_toggle_sms_service(request: Request):
    """Admin toggles a service (e.g. enable/disable Telegram or OpenAI)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_id = body.get("admin_tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    service_code = body.get("service_code")
    is_enabled = bool(body.get("is_enabled", True))

    async with get_db_session() as session:
        result = await session.execute(
            select(SmsServiceConfig).where(SmsServiceConfig.service_code == service_code)
        )
        svc = result.scalar_one_or_none()
        if not svc:
            return JSONResponse({"error": "service_not_found"}, status_code=404)
        svc.is_enabled = is_enabled
        await session.commit()
        return {"status": "ok", "service_code": service_code, "is_enabled": is_enabled}


@router.post("/api/admin/sms/countries/toggle")
async def admin_toggle_sms_country(request: Request):
    """Admin toggles a country (e.g. enable/disable USA or UK)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    admin_id = body.get("admin_tg_id")
    if not verify_admin(admin_id, request):
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    country_code = body.get("country_code")
    is_enabled = bool(body.get("is_enabled", True))

    async with get_db_session() as session:
        result = await session.execute(
            select(SmsCountryConfig).where(SmsCountryConfig.country_code == country_code)
        )
        ctry = result.scalar_one_or_none()
        if not ctry:
            return JSONResponse({"error": "country_not_found"}, status_code=404)
        ctry.is_enabled = is_enabled
        await session.commit()
        return {"status": "ok", "country_code": country_code, "is_enabled": is_enabled}
