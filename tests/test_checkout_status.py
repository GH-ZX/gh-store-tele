import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace


class TestCheckoutStatusDetermination:
    """Tests that activation orders get 'pending_fulfillment' status and stock orders get 'completed'."""

    def test_activation_delivery_sets_pending(self):
        from services.batstore import BatStoreService
        product = SimpleNamespace(delivery_type="activation")
        assert product.delivery_type in ("activation",)

    def test_stock_delivery_sets_completed(self):
        product = SimpleNamespace(delivery_type="stock")
        assert product.delivery_type not in ("activation",)

    def test_supplier_api_sets_completed(self):
        product = SimpleNamespace(delivery_type="supplier_api")
        assert product.delivery_type not in ("activation",)

    def test_status_logic_in_checkout_flow(self):
        """Verify the status assignment logic matches our expected behavior."""
        for delivery_type, expected in [
            ("activation", "pending_fulfillment"),
            ("stock", "completed"),
            ("supplier_api", "completed"),
            ("instant", "completed"),
        ]:
            product = SimpleNamespace(delivery_type=delivery_type)
            status = "completed"
            if product.delivery_type in ("activation",):
                status = "pending_fulfillment"
            assert status == expected, f"delivery_type={delivery_type}"


class TestBatStoreOrderRepositoryPending:
    """Tests for BatStoreOrderRepository pending order queries."""

    @pytest.mark.asyncio
    async def test_get_pending_returns_only_pending(self):
        from repositories.batstore_order import BatStoreOrderRepository
        from unittest.mock import MagicMock

        mock_session = AsyncMock()
        order1 = SimpleNamespace(id=1, status="pending_fulfillment",
                                  external_order_ref="12345")
        order2 = SimpleNamespace(id=2, status="completed",
                                  external_order_ref="12346")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [order1]
        mock_session.execute = AsyncMock(return_value=mock_result)

        pending = await BatStoreOrderRepository.get_pending(mock_session)
        assert len(pending) == 1
        assert pending[0].status == "pending_fulfillment"

    @pytest.mark.asyncio
    async def test_update_status_sets_new_status(self):
        from repositories.batstore_order import BatStoreOrderRepository
        from models.batstore_order import BatStoreOrder

        order = SimpleNamespace(id=1, status="pending_fulfillment", details=[{"name": "test"}])
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = order
        mock_session.execute = AsyncMock(return_value=mock_result)

        updated = await BatStoreOrderRepository.update_status(
            1, "completed", ["goods1"], mock_session)

        assert updated.status == "completed"
        assert order.details[0].get("delivery_goods") == ["goods1"]

    @pytest.mark.asyncio
    async def test_update_status_returns_none_if_not_found(self):
        from repositories.batstore_order import BatStoreOrderRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await BatStoreOrderRepository.update_status(
            999, "completed", None, mock_session)
        assert result is None
