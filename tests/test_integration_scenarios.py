"""Real Integration Tests for GH Store against live PostgreSQL and Redis.

Covers critical audit items:
1. Duplicate purchase idempotency & double debit prevention.
2. Timeout-after-acceptance and queued order fulfillment recovery.
3. Concurrent webhook vs. poller execution races with distributed & row locks.
4. Variant mismatches and price/variant binding tampering protection.
5. Mixed-success multi-item carts with partial fulfillment and atomic refund.
"""
import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
import random
import time
import pytest
from fastapi import HTTPException
import redis.asyncio as aioredis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import config
from models.batstore_order import BatStoreOrder
from models.batstore_product import BatStoreProduct
from models.order import Order
from models.user import User
from models.wallet_ledger import WalletLedger
from repositories.user import UserRepository
from services.checkout import CheckoutService
from services.distributed_lock import order_lock
from services.order_fulfillment import FulfillmentService

from sqlalchemy.pool import NullPool
import db as db_module

REAL_DB_URL = "postgresql+asyncpg://postgres:4F-gPIVS4tGY64s2ANkb180mwcgfeEnA@localhost:5432/ghstore"
REAL_REDIS_URL = "redis://:qyzmUAd8CDVnoGPI2kAXWigO0xsLtXzu@localhost:6379/0"


@pytest.fixture
def real_engine():
    engine = create_async_engine(REAL_DB_URL, echo=False, poolclass=NullPool)
    yield engine
    engine.sync_engine.dispose()


@pytest.fixture
def real_session_maker(real_engine):
    return async_sessionmaker(real_engine, expire_on_commit=False, class_=AsyncSession)



@asynccontextmanager
async def create_test_user(session_maker):
    """Create a unique test user with funded balance in real PostgreSQL."""
    tg_id = 888000000 + random.randint(1000, 999999)
    async with session_maker() as session:
        user = User(
            telegram_id=tg_id,
            telegram_username=f"user_{tg_id}",
            top_up_amount=Decimal("100.00"),
            consume_records=Decimal("0.00"),
        )
        session.add(user)
        await session.commit()
    try:
        yield tg_id
    finally:
        async with session_maker() as session:
            await session.execute(text("DELETE FROM wallet_ledger WHERE telegram_id = :tgid"), {"tgid": tg_id})
            await session.execute(text("DELETE FROM batstore_orders WHERE telegram_id = :tgid"), {"tgid": tg_id})
            await session.execute(text("DELETE FROM users WHERE telegram_id = :tgid"), {"tgid": tg_id})
            await session.commit()


@asynccontextmanager
async def create_test_products(session_maker):
    """Create test products in real PostgreSQL."""
    pid1 = 777000 + random.randint(100, 999)
    pid2 = 777000 + random.randint(1000, 9999)
    async with session_maker() as session:
        p1 = BatStoreProduct(
            product_id=pid1,
            name="Test Instant Item A",
            cost_usd=Decimal("5.00"),
            sell_price_usd=Decimal("10.00"),
            supplier="batstore",
            delivery_type="stock",
            stock=20,
            hidden=False,
            extra_meta={},
        )
        p2 = BatStoreProduct(
            product_id=pid2,
            name="Test Instant Item B",
            cost_usd=Decimal("8.00"),
            sell_price_usd=Decimal("15.00"),
            supplier="batstore",
            delivery_type="stock",
            stock=20,
            hidden=False,
            extra_meta={},
        )
        session.add(p1)
        session.add(p2)
        await session.commit()
    try:
        yield {"p1": pid1, "p2": pid2}
    finally:
        async with session_maker() as session:
            await session.execute(text("DELETE FROM batstore_products WHERE product_id IN (:pid1, :pid2)"),
                                  {"pid1": pid1, "pid2": pid2})
            await session.commit()


# ==============================================================================
# Scenario 1: Duplicate Purchases & Idempotency Key Replay Protection
# ==============================================================================
@pytest.mark.asyncio
async def test_integration_duplicate_purchase_idempotency(real_session_maker):
    """Verify that duplicate checkouts with the same idempotency key do not double-debit balance."""
    async with create_test_user(real_session_maker) as tg_id, \
               create_test_products(real_session_maker) as prods:
        pid = prods["p1"]
        idem_key = f"test_idem_{uuid_suffix()}"

        checkout_body = {
            "product_id": pid,
            "quantity": 1,
        }

        # First attempt: initial checkout
        async with real_session_maker() as session:
            order1, created1 = await CheckoutService.reserve(tg_id, checkout_body, idem_key, session)
            assert created1 is True
            assert order1.id is not None
            assert float(order1.total_sell) == 10.00
            await session.commit()

        # Verify user balance after 1st reservation: $100 - $10 = $90
        async with real_session_maker() as session:
            u1 = await UserRepository.get_by_tgid(tg_id, session)
            assert float(u1.top_up_amount - u1.consume_records) == 90.00

            # Check ledger: exactly 1 reservation
            ledgers = (await session.execute(select(WalletLedger).where(WalletLedger.telegram_id == tg_id))).scalars().all()
            assert len(ledgers) == 1
            assert ledgers[0].transaction_type == "reservation"
            assert float(ledgers[0].amount) == 10.00

        # Second attempt: exact duplicate request replay with same idempotency key
        async with real_session_maker() as session:
            order2, created2 = await CheckoutService.reserve(tg_id, checkout_body, idem_key, session)
            assert created2 is False
            assert order2.id == order1.id
            await session.commit()

        # Verify balance was NOT debited again: still $90.00
        async with real_session_maker() as session:
            u2 = await UserRepository.get_by_tgid(tg_id, session)
            assert float(u2.top_up_amount - u2.consume_records) == 90.00

            # Still only 1 ledger reservation entry
            ledgers2 = (await session.execute(select(WalletLedger).where(WalletLedger.telegram_id == tg_id))).scalars().all()
            assert len(ledgers2) == 1

        # Third attempt: same idempotency key with conflicting body (e.g. quantity=2)
        with pytest.raises(HTTPException) as exc:
            async with real_session_maker() as session:
                await CheckoutService.reserve(tg_id, {"product_id": pid, "quantity": 2}, idem_key, session)
        assert exc.value.status_code == 409


# ==============================================================================
# Scenario 2: Timeout-After-Acceptance & Recovery
# ==============================================================================
@pytest.mark.asyncio
async def test_integration_timeout_after_acceptance(real_session_maker):
    """Verify that an order whose fulfillment times out remains durable and can be recovered."""
    async with create_test_user(real_session_maker) as tg_id, \
               create_test_products(real_session_maker) as prods:
        pid = prods["p1"]
        idem_key = f"test_timeout_{uuid_suffix()}"

        # 1. Order reservation creates durable pending order
        async with real_session_maker() as session:
            order, created = await CheckoutService.reserve(tg_id, {"product_id": pid, "quantity": 1}, idem_key, session)
            assert created is True
            order_id = order.id
            await session.commit()

        # Verify user balance debited: $90.00
        async with real_session_maker() as session:
            u = await UserRepository.get_by_tgid(tg_id, session)
            assert float(u.top_up_amount - u.consume_records) == 90.00

        # 2. Simulate background poller or recovery claiming the order and completing fulfillment
        async with real_session_maker() as session:
            # Transition line item 0 to completed with delivery keys
            updated_order, applied = await FulfillmentService.transition_item(
                order_id,
                index=0,
                status="completed",
                goods=["LICENSE-KEY-ABC-12345"],
                session=session,
                supplier="batstore",
            )
            assert applied is True
            # Mark overall order completed
            updated_order.status = "completed"
            await session.commit()

        # 3. Verify capture ledger recorded with supplier cost
        async with real_session_maker() as session:
            ord_db = await session.get(Order, order_id)
            assert ord_db.status == "completed"

            ledgers = (await session.execute(select(WalletLedger).where(WalletLedger.telegram_id == tg_id))).scalars().all()
            types = [l.transaction_type for l in ledgers]
            assert "reservation" in types
            assert "capture" in types


# ==============================================================================
# Scenario 3: Webhook vs Poller Concurrency Race
# ==============================================================================
@pytest.mark.asyncio
async def test_integration_webhook_poller_concurrency_race(real_session_maker):
    """Simulate poller and webhook arriving simultaneously; verify race is safely serialized."""
    async with create_test_user(real_session_maker) as tg_id, \
               create_test_products(real_session_maker) as prods:
        pid = prods["p1"]
        idem_key = f"test_race_{uuid_suffix()}"

        async with real_session_maker() as session:
            order, _ = await CheckoutService.reserve(tg_id, {"product_id": pid, "quantity": 1}, idem_key, session)
            order_id = order.id
            await session.commit()

        async def worker_poller():
            async with real_session_maker() as session:
                async with order_lock(order_id, session=session):
                    ord_res, applied = await FulfillmentService.transition_item(
                        order_id, 0, "completed", ["KEY-FROM-POLLER"], session, supplier="batstore"
                    )
                    if applied:
                        ord_res.status = "completed"
                        await session.commit()
                    return applied

        async def worker_webhook():
            async with real_session_maker() as session:
                async with order_lock(order_id, session=session):
                    ord_res, applied = await FulfillmentService.transition_item(
                        order_id, 0, "completed", ["KEY-FROM-WEBHOOK"], session, supplier="batstore"
                    )
                    if applied:
                        ord_res.status = "completed"
                        await session.commit()
                    return applied

        # Run both simultaneously
        results = await asyncio.gather(worker_poller(), worker_webhook())

        # Exactly ONE worker must succeed, the other must be rejected (applied=False)
        assert sum(1 for r in results if r is True) == 1
        assert sum(1 for r in results if r is False) == 1

        # Verify exactly one capture entry in ledger
        async with real_session_maker() as session:
            captures = (await session.execute(
                select(WalletLedger)
                .where(WalletLedger.telegram_id == tg_id)
                .where(WalletLedger.transaction_type == "capture")
            )).scalars().all()
            assert len(captures) == 1


# ==============================================================================
# Scenario 4: Variant Mismatch & Price Tampering Protection
# ==============================================================================
@pytest.mark.asyncio
async def test_integration_variant_price_mismatch_protection(real_session_maker):
    """Verify that submitting mismatched variants or illegal variant selectors is rejected."""
    async with create_test_user(real_session_maker) as tg_id, \
               create_test_products(real_session_maker) as prods:
        pid = prods["p1"]  # BatStore product (supplier != g2bulk)

        # Supplying a variant selector on non-g2bulk product must be rejected
        with pytest.raises(HTTPException) as exc:
            async with real_session_maker() as session:
                await CheckoutService.reserve(
                    tg_id,
                    {"product_id": pid, "quantity": 1, "selected_item_id": "999", "catalogue_name": "forged_variant"},
                    f"test_var_{uuid_suffix()}",
                    session,
                )
        assert exc.value.status_code == 400
        assert exc.value.detail == "invalid_variant"

        # Verify balance was NOT touched
        async with real_session_maker() as session:
            u = await UserRepository.get_by_tgid(tg_id, session)
            assert float(u.top_up_amount - u.consume_records) == 100.00

            # Zero ledger rows
            ledgers = (await session.execute(select(WalletLedger).where(WalletLedger.telegram_id == tg_id))).scalars().all()
            assert len(ledgers) == 0


# ==============================================================================
# Scenario 5: Mixed-Success Multi-Item Cart & Atomic Partial Refund
# ==============================================================================
@pytest.mark.asyncio
async def test_integration_mixed_success_cart(real_session_maker):
    """Cart with 2 items: item 1 completes ($10), item 2 fails ($15) and is refunded."""
    async with create_test_user(real_session_maker) as tg_id, \
               create_test_products(real_session_maker) as prods:
        pid1 = prods["p1"]  # $10.00
        pid2 = prods["p2"]  # $15.00
        idem_key = f"test_cart_{uuid_suffix()}"

        cart_body = {
            "items": [
                {"product_id": pid1, "quantity": 1},
                {"product_id": pid2, "quantity": 1},
            ]
        }

        # 1. Checkout reserves full cart total: $10 + $15 = $25.00
        async with real_session_maker() as session:
            order, created = await CheckoutService.reserve(tg_id, cart_body, idem_key, session, cart=True)
            assert created is True
            order_id = order.id
            await session.commit()

        # Balance after reservation: $100 - $25 = $75.00
        async with real_session_maker() as session:
            u = await UserRepository.get_by_tgid(tg_id, session)
            assert float(u.top_up_amount - u.consume_records) == 75.00

        # 2. Fulfill Item 1 -> Completed ($10.00)
        async with real_session_maker() as session:
            _, applied1 = await FulfillmentService.transition_item(
                order_id, 0, "completed", ["KEY-ITEM-1"], session, supplier="batstore"
            )
            assert applied1 is True
            await session.commit()

        # 3. Fulfill Item 2 -> Failed ($15.00) -> Triggers automatic refund of $15.00
        async with real_session_maker() as session:
            _, applied2 = await FulfillmentService.transition_item(
                order_id, 1, "failed", [], session, supplier="batstore"
            )
            assert applied2 is True
            await session.commit()

        # 4. Final verification:
        # - User balance: $75 + $15 (refund) = $90.00 (Net spent = $10.00 for Item 1)
        async with real_session_maker() as session:
            u_final = await UserRepository.get_by_tgid(tg_id, session)
            net_balance = float(u_final.top_up_amount - u_final.consume_records)
            assert net_balance == 90.00

            # Ledger contains: reservation (-$25), capture (Item 1, $10), refund (Item 2, +$15)
            ledgers = (await session.execute(
                select(WalletLedger)
                .where(WalletLedger.telegram_id == tg_id)
                .order_by(WalletLedger.id.asc())
            )).scalars().all()

            op_types = [l.transaction_type for l in ledgers]
            assert op_types == ["reservation", "capture", "refund"]

            res_entry = ledgers[0]
            cap_entry = ledgers[1]
            ref_entry = ledgers[2]

            assert float(res_entry.amount) == 25.00
            assert float(cap_entry.amount) == 10.00
            assert float(ref_entry.amount) == 15.00


def uuid_suffix() -> str:
    return f"{int(time.time())}_{random.randint(1000, 9999)}"
