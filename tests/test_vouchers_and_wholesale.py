import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from services.batstore import BatStoreService
from services.currency_rates import CurrencyRateService
from repositories.gift_voucher import GiftVoucherRepository
from models.gift_voucher import GiftVoucherDTO


def test_volume_discount_matrix():
    assert BatStoreService.get_volume_discount(1) == 0.0
    assert BatStoreService.get_volume_discount(4) == 0.0
    assert BatStoreService.get_volume_discount(5) == 7.0
    assert BatStoreService.get_volume_discount(9) == 7.0
    assert BatStoreService.get_volume_discount(10) == 15.0
    assert BatStoreService.get_volume_discount(50) == 15.0


def test_doa_validation():
    # Valid credentials
    assert BatStoreService.validate_delivery_goods(["user:pass123", "KEY-9999"]) is True

    # Empty list
    assert BatStoreService.validate_delivery_goods([]) is False

    # Error or revoked credentials
    assert BatStoreService.validate_delivery_goods(["Error: upstream failed"]) is False
    assert BatStoreService.validate_delivery_goods(["null"]) is False
    assert BatStoreService.validate_delivery_goods(["ab"]) is False  # too short


def test_currency_rates_service():
    assert CurrencyRateService.get_rate("USD") == 1.0
    assert CurrencyRateService.get_rate("EUR") > 0.5
    assert CurrencyRateService.get_rate("XTR") == 100.0


def test_voucher_code_generation():
    code1 = GiftVoucherRepository.generate_code()
    code2 = GiftVoucherRepository.generate_code()
    assert code1.startswith("GH-")
    assert code2.startswith("GH-")
    assert code1 != code2
    assert len(code1) == 12
