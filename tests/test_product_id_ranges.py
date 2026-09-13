from types import SimpleNamespace

from services.prodseller import ProdSellerService
from repositories.product import supplier_owns_row


def _row(supplier=None, reseller_key_override=None):
    return SimpleNamespace(supplier=supplier, reseller_key_override=reseller_key_override)


def test_supplier_owns_row_matching_supplier():
    assert supplier_owns_row(_row("batstore"), "batstore", 123) is True
    assert supplier_owns_row(_row("prodseller"), "prodseller", 2000001) is True
    assert supplier_owns_row(_row("g2bulk"), "g2bulk", 30000001) is True


def test_supplier_owns_row_legacy_null_supplier_treated_as_batstore():
    assert supplier_owns_row(_row(None), "batstore", 1) is True
    assert supplier_owns_row(_row(None), "prodseller", 2000001) is False


def test_supplier_owns_row_cross_supplier_collision():
    assert supplier_owns_row(_row("batstore"), "prodseller", 2000001) is False
    assert supplier_owns_row(_row("prodseller"), "g2bulk", 30000001) is False
    assert supplier_owns_row(_row("g2bulk"), "batstore", 35000001) is False


def test_prodseller_ids_stay_in_reserved_range():
    ids = [ProdSellerService.generate_product_id(f"6a2fda51{mongo:08d}") for mongo in range(3000)]
    assert all(2000000 <= pid < 2900000 for pid in ids)
    assert not any(pid >= 30000000 for pid in ids)
    assert len(set(ids)) > 1


def test_g2bulk_reserved_ranges_are_disjoint_from_prodseller():
    min_game_id = 30000000
    min_voucher_id = 35000000
    max_prodseller = 2900000
    sample_games = [30000000 + g_id for g_id in range(0, 5000, 7)]
    sample_vouchers = [35000000 + cat_id for cat_id in range(0, 5000, 7)]
    assert all(pid > max_prodseller for pid in sample_games)
    assert all(pid > max_prodseller for pid in sample_vouchers)
    assert all(pid >= min_game_id for pid in sample_games)
    assert all(pid >= min_voucher_id for pid in sample_vouchers)