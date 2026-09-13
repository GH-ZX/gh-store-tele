"""Provider health and failure tracking service.

Tracks consecutive failure counters for upstream suppliers (BatStore, ProdSeller,
G2Bulk, 5sim) and issues deduplicated admin alerts when repeated failures occur.
"""
import logging
import time
from typing import Any
from services.notification import NotificationService

logger = logging.getLogger(__name__)

_FAILURE_THRESHOLD = 5
_ALERT_WINDOW_SECONDS = 1800  # at most 1 alert per 30 minutes per failing provider


class ProviderHealthTracker:
    """Tracks consecutive upstream supplier failures and alerts admins upon degradation."""

    _consecutive_failures: dict[str, int] = {}
    _last_errors: dict[str, str] = {}
    _last_failure_times: dict[str, float] = {}

    @classmethod
    def record_success(cls, provider: str | None) -> None:
        """Reset consecutive failure counter on a successful provider operation."""
        if not provider:
            return
        provider = provider.lower()
        cls._consecutive_failures[provider] = 0

    @classmethod
    async def record_failure(cls, provider: str | None, error_message: str) -> None:
        """Increment consecutive failure counter and alert admins if threshold reached."""
        if not provider:
            return
        provider = provider.lower()
        failures = cls._consecutive_failures.get(provider, 0) + 1
        cls._consecutive_failures[provider] = failures
        cls._last_errors[provider] = str(error_message)
        cls._last_failure_times[provider] = time.time()

        logger.warning("Provider %s failure count: %d. Latest error: %s", provider, failures, error_message)

        if failures >= _FAILURE_THRESHOLD:
            badge_map = {
                "batstore": "سيرفر 1 (BatStore)",
                "prodseller": "سيرفر 2 (ProdSeller)",
                "g2bulk": "سيرفر 3 (G2Bulk Games)",
                "5sim": "سيرفر الأرقام الافتراضية (5sim)",
            }
            display_name = badge_map.get(provider, provider.upper())
            alert_text = (
                f"🚨 <b>تنبيه تعطل مزود التوريد — {display_name}</b>\n\n"
                f"• عدد الإخفاقات المتتالية: <b>{failures}</b>\n"
                f"• آخر خطأ مسجل: <code>{error_message[:200]}</code>\n\n"
                "<i>يرجى فحص رصيد المزود أو الاتصال بحساب التوريد للتأكد من استقرار الخدمة.</i>"
            )
            try:
                await NotificationService.send_error_to_admins(
                    f"provider_down_{provider}",
                    alert_text,
                    None,
                    window_seconds=_ALERT_WINDOW_SECONDS,
                )
            except Exception as e:
                logger.error("Failed sending provider health alert for %s: %s", provider, e)

    @classmethod
    def get_failure_count(cls, provider: str) -> int:
        return cls._consecutive_failures.get(provider.lower(), 0)

    @classmethod
    def get_all_status(cls) -> dict[str, Any]:
        return {
            p: {
                "consecutive_failures": cls._consecutive_failures.get(p, 0),
                "last_error": cls._last_errors.get(p),
                "last_failure_time": cls._last_failure_times.get(p),
            }
            for p in set(list(cls._consecutive_failures.keys()) + ["batstore", "prodseller", "g2bulk", "5sim"])
        }
