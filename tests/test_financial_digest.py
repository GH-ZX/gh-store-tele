import pytest
from unittest.mock import AsyncMock

from services.financial_digest import FinancialDigestService


class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._rows[0] if self._rows else 0

    def scalars(self):
        class _Scalars:
            def __init__(self, items):
                self._items = items
            def all(self):
                return self._items
        return _Scalars(self._rows)


@pytest.mark.asyncio
async def test_financial_digest_format(monkeypatch):
    call_count = [0]

    async def fake_execute(stmt, session):
        call_count[0] += 1
        idx = call_count[0]
        if idx == 1:
            # Crypto deposits
            return _FakeScalarResult([(150.0, 3)])
        elif idx == 2:
            # Stars deposits
            return _FakeScalarResult([(45.0, 2)])
        elif idx == 3:
            # SAM deposits
            return _FakeScalarResult([(80.0, 1)])
        elif idx == 4:
            # Orders
            return _FakeScalarResult([])
        else:
            # Users
            return _FakeScalarResult([5])

    monkeypatch.setattr("services.financial_digest.session_execute", fake_execute)

    report = await FinancialDigestService.generate_digest(None, hours=24)

    assert "GH Store Financial Digest (24h)" in report
    assert "150.00" in report
    assert "45.00" in report
    assert "80.00" in report
    assert "Total Top-ups" in report
    assert "275.00" in report  # 150 + 45 + 80
    assert "5 registrations" in report
