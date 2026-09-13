import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from models.wallet_ledger import WalletLedger, WalletLedgerAdmin
from models.user import User
from repositories.user import UserRepository


def test_wallet_ledger_admin_view_permissions():
    assert WalletLedgerAdmin.can_create is False
    assert WalletLedgerAdmin.can_edit is False
    assert WalletLedgerAdmin.can_delete is False
    assert WalletLedger.reference in WalletLedgerAdmin.column_searchable_list
    assert WalletLedger.telegram_id in WalletLedgerAdmin.column_searchable_list


def test_wallet_ledger_repr():
    entry = WalletLedger(
        id=101,
        telegram_id=12345678,
        transaction_type="reservation",
        amount=Decimal("15.50"),
        reference="deb_12345678_test",
    )
    assert "101" in repr(entry)
    assert "12345678" in repr(entry)
    assert "15.5" in repr(entry)


@pytest.mark.asyncio
async def test_try_debit_balance_records_ledger_entry():
    session = AsyncMock()
    mock_user = MagicMock()
    mock_user.top_up_amount = 50.0
    mock_user.consume_records = 10.0

    ref_check_res = MagicMock()
    ref_check_res.scalar_one_or_none.return_value = None  # no existing reference

    update_res = MagicMock()
    update_res.scalar_one_or_none.return_value = 1  # user ID returned from UPDATE

    added_objects = []
    session.add = lambda obj: added_objects.append(obj)

    with patch.object(UserRepository, "get_by_tgid", return_value=mock_user), \
         patch("repositories.user.session_execute", AsyncMock(side_effect=[ref_check_res, update_res])), \
         patch("repositories.user.session_flush", AsyncMock()):

        debited = await UserRepository.try_debit_balance(
            telegram_id=999888,
            amount=15.0,
            session=session,
            reference="ref_test_debit_1",
            order_id=42,
            supplier="batstore",
            supplier_cost=10.5,
            supplier_currency="USD",
            description="Test checkout debit",
        )

        assert debited is True
        assert len(added_objects) == 1
        ledger = added_objects[0]
        assert isinstance(ledger, WalletLedger)
        assert ledger.telegram_id == 999888
        assert ledger.transaction_type == "reservation"
        assert ledger.amount == Decimal("15.00")
        assert ledger.balance_before == Decimal("40.00")
        assert ledger.balance_after == Decimal("25.00")
        assert ledger.reference == "ref_test_debit_1"
        assert ledger.order_id == 42
        assert ledger.supplier == "batstore"
        assert ledger.supplier_cost == Decimal("10.5000")
        assert ledger.supplier_currency == "USD"


@pytest.mark.asyncio
async def test_try_debit_balance_idempotency_prevents_duplicate():
    session = AsyncMock()
    mock_user = MagicMock()
    mock_user.top_up_amount = 50.0
    mock_user.consume_records = 10.0

    # Simulate existing reference found
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = 1  # reference already in DB

    added_objects = []
    session.add = lambda obj: added_objects.append(obj)

    with patch.object(UserRepository, "get_by_tgid", return_value=mock_user), \
         patch("repositories.user.session_execute", AsyncMock(return_value=mock_execute_res)):

        # Should return True without adding duplicate ledger or deducting again
        res = await UserRepository.try_debit_balance(
            telegram_id=999888,
            amount=15.0,
            session=session,
            reference="ref_already_processed",
        )
        assert res is True
        assert len(added_objects) == 0


@pytest.mark.asyncio
async def test_refund_balance_records_ledger_entry():
    session = AsyncMock()
    mock_user = MagicMock()
    mock_user.top_up_amount = 50.0
    mock_user.consume_records = 25.0

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = None  # no existing reference

    added_objects = []
    session.add = lambda obj: added_objects.append(obj)

    with patch.object(UserRepository, "get_by_tgid", return_value=mock_user), \
         patch("repositories.user.session_execute", AsyncMock(return_value=mock_execute_res)), \
         patch("repositories.user.session_flush", AsyncMock()):

        await UserRepository.refund_balance(
            telegram_id=999888,
            amount=12.50,
            session=session,
            reference="ref_test_refund_1",
            order_id=42,
            description="Item failed refund",
        )

        assert len(added_objects) == 1
        ledger = added_objects[0]
        assert isinstance(ledger, WalletLedger)
        assert ledger.telegram_id == 999888
        assert ledger.transaction_type == "refund"
        assert ledger.amount == Decimal("12.50")
        assert ledger.balance_before == Decimal("25.00")
        assert ledger.balance_after == Decimal("37.50")
        assert ledger.reference == "ref_test_refund_1"
        assert ledger.order_id == 42


@pytest.mark.asyncio
async def test_credit_balance_records_ledger_entry():
    session = AsyncMock()
    mock_user = MagicMock()
    mock_user.top_up_amount = 20.0
    mock_user.consume_records = 5.0

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = None

    added_objects = []
    session.add = lambda obj: added_objects.append(obj)

    with patch.object(UserRepository, "get_by_tgid", return_value=mock_user), \
         patch("repositories.user.session_execute", AsyncMock(return_value=mock_execute_res)), \
         patch("repositories.user.session_flush", AsyncMock()):

        await UserRepository.credit_balance(
            telegram_id=999888,
            amount=50.00,
            session=session,
            reference="crd_test_topup_1",
            description="Crypto deposit top-up",
        )

        assert len(added_objects) == 1
        ledger = added_objects[0]
        assert isinstance(ledger, WalletLedger)
        assert ledger.telegram_id == 999888
        assert ledger.transaction_type == "credit"
        assert ledger.amount == Decimal("50.00")
        assert ledger.balance_before == Decimal("15.00")
        assert ledger.balance_after == Decimal("65.00")
        assert ledger.reference == "crd_test_topup_1"


@pytest.mark.asyncio
async def test_record_capture_retains_supplier_cost_and_currency():
    session = AsyncMock()
    mock_user = MagicMock()
    mock_user.top_up_amount = 100.0
    mock_user.consume_records = 20.0

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = None

    added_objects = []
    session.add = lambda obj: added_objects.append(obj)

    with patch.object(UserRepository, "get_by_tgid", return_value=mock_user), \
         patch("repositories.user.session_execute", AsyncMock(return_value=mock_execute_res)), \
         patch("repositories.user.session_flush", AsyncMock()):

        await UserRepository.record_capture(
            telegram_id=999888,
            amount=20.00,
            session=session,
            order_id=88,
            reference="cap_order_88",
            supplier="prodseller",
            supplier_cost=14.2550,
            supplier_currency="USDT",
            description="Order #88 captured from ProdSeller",
        )

        assert len(added_objects) == 1
        ledger = added_objects[0]
        assert isinstance(ledger, WalletLedger)
        assert ledger.telegram_id == 999888
        assert ledger.transaction_type == "capture"
        assert ledger.amount == Decimal("20.00")
        assert ledger.order_id == 88
        assert ledger.supplier == "prodseller"
        assert ledger.supplier_cost == Decimal("14.2550")
        assert ledger.supplier_currency == "USDT"
        assert ledger.reference == "cap_order_88"
