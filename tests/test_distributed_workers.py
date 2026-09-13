import asyncio
import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from services.distributed_lock import (
    DistributedLock,
    leader_lease,
    order_lock,
    sms_lock,
    _key_to_int64,
)
from services.provider_health import ProviderHealthTracker
from repositories.order import OrderRepository
from models.order import Order


def test_key_to_int64_deterministic():
    key1 = "ghstore:leader:catalog_sync"
    key2 = "ghstore:leader:catalog_sync"
    key3 = "ghstore:leader:balance_monitor"
    assert _key_to_int64(key1) == _key_to_int64(key2)
    assert _key_to_int64(key1) != _key_to_int64(key3)
    # Must fit in 64-bit signed integer
    val = _key_to_int64(key1)
    assert -9223372036854775808 <= val <= 9223372036854775807


@pytest.mark.asyncio
async def test_distributed_lock_redis_acquire_and_release():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    mock_redis.eval.return_value = 1

    lock = DistributedLock("ghstore:test:key", ttl_seconds=30, redis_client=mock_redis)
    acquired = await lock.acquire()
    assert acquired is True
    assert lock._acquired_backend == "redis"
    mock_redis.set.assert_awaited_once()

    await lock.release()
    assert lock._acquired_backend is None
    mock_redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_distributed_lock_redis_contention_fails():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = None  # Key already held

    lock = DistributedLock("ghstore:test:contention", ttl_seconds=30, redis_client=mock_redis)
    acquired = await lock.acquire()
    assert acquired is False
    assert lock._acquired_backend is None


@pytest.mark.asyncio
async def test_distributed_lock_postgres_fallback():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = True  # lock granted
    mock_session.execute.return_value = mock_result

    # No redis provided -> falls back to Postgres advisory lock
    lock = DistributedLock("ghstore:test:pg_key", ttl_seconds=30, redis_client=None, session=mock_session)
    acquired = await lock.acquire()
    assert acquired is True
    assert lock._acquired_backend == "postgres"

    await lock.release()
    assert lock._acquired_backend is None
    assert mock_session.execute.await_count == 2  # try_advisory_lock then advisory_unlock


@pytest.mark.asyncio
async def test_leader_lease_context_manager():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True

    async with leader_lease("catalog_sync", ttl_seconds=60, redis_client=mock_redis) as is_leader:
        assert is_leader is True

    mock_redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_order_lock_and_sms_lock():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True

    async with order_lock(123, redis_client=mock_redis) as acquired:
        assert acquired is True

    async with sms_lock("act-555", redis_client=mock_redis) as acquired:
        assert acquired is True


@pytest.mark.asyncio
async def test_provider_health_tracker_consecutive_failures():
    ProviderHealthTracker._consecutive_failures.clear()

    with patch("services.notification.NotificationService.send_error_to_admins", AsyncMock()) as mock_alert:
        # First 4 failures do not alert admins yet
        for i in range(4):
            await ProviderHealthTracker.record_failure("batstore", f"Error {i}")
            mock_alert.assert_not_called()

        assert ProviderHealthTracker.get_failure_count("batstore") == 4

        # 5th failure triggers alert!
        await ProviderHealthTracker.record_failure("batstore", "Connection reset")
        assert ProviderHealthTracker.get_failure_count("batstore") == 5
        mock_alert.assert_awaited_once()

        # Success resets count to 0
        ProviderHealthTracker.record_success("batstore")
        assert ProviderHealthTracker.get_failure_count("batstore") == 0


@pytest.mark.asyncio
async def test_get_pending_supports_skip_locked():
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_res

    orders = await OrderRepository.get_pending(mock_session, limit=10, skip_locked=True)
    assert orders == []

    executed_stmt = mock_session.execute.call_args[0][0]
    assert executed_stmt._for_update_arg is not None
    assert executed_stmt._for_update_arg.skip_locked is True
    assert executed_stmt._limit_clause.value == 10


@pytest.mark.asyncio
async def test_queue_age_monitoring_alerts_on_stalled_order():
    from services.order_polling import poll_pending_orders
    from unittest.mock import patch

    # Stalled order created 45 minutes ago
    old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=45)
    stalled_order = Order(
        id=777,
        telegram_id=12345,
        status="pending_fulfillment",
        created_at=old_time,
    )

    class FakeSessionCtx:
        async def __aenter__(self):
            return AsyncMock()
        async def __aexit__(self, *args):
            pass

    async def fake_sleep(sec):
        # Stop the infinite loop on first iteration
        raise asyncio.CancelledError()

    with patch("services.order_polling.get_db_session", return_value=FakeSessionCtx()), \
         patch("services.order_polling.drain_retry_order_queue", AsyncMock()), \
         patch("services.order_polling.BatStoreOrderRepository.get_pending", AsyncMock(return_value=[stalled_order])), \
         patch("services.order_polling.NotificationService.send_error_to_admins", AsyncMock()) as mock_alert, \
         patch("services.order_polling.asyncio.sleep", side_effect=fake_sleep), \
         patch("services.order_polling.poll_one_order", AsyncMock()):

        try:
            await poll_pending_orders()
        except asyncio.CancelledError:
            pass

        mock_alert.assert_awaited_once()
        alert_key = mock_alert.call_args[0][0]
        alert_text = mock_alert.call_args[0][1]
        assert alert_key == "stalled_order_777"
        assert "#777" in alert_text
        assert "45" in alert_text
