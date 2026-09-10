import pytest
from unittest.mock import AsyncMock, MagicMock
from callbacks import SamCallback
from enums.language import Language


class TestShamcashPayment:
    """Tests for ShamCash payment flows, currency toggle (USD vs SYP), and invoice creation."""

    def test_sam_callback_currency_field(self):
        cb_default = SamCallback.create(level=0)
        assert cb_default.level == 0
        assert cb_default.provider is None
        assert cb_default.currency is None

        cb_sham_usd = SamCallback.create(level=2, provider="shamcash", currency="USD")
        assert cb_sham_usd.level == 2
        assert cb_sham_usd.provider == "shamcash"
        assert cb_sham_usd.currency == "USD"

        cb_sham_syp = SamCallback.create(level=2, provider="shamcash", currency="SYP")
        assert cb_sham_syp.level == 2
        assert cb_sham_syp.provider == "shamcash"
        assert cb_sham_syp.currency == "SYP"

    @pytest.mark.asyncio
    async def test_sam_pick_provider_buttons(self, monkeypatch):
        from handlers.user.sam import sam_pick_provider

        callback = MagicMock()
        callback.message = MagicMock()
        callback_data = SamCallback.create(level=0)
        session = AsyncMock()

        # Mock _provider_enabled
        async def fake_enabled(sess, key, env_val):
            return True

        monkeypatch.setattr("handlers.user.sam._provider_enabled", fake_enabled)
        mock_safe_edit = AsyncMock()
        monkeypatch.setattr("handlers.user.sam.safe_edit_message", mock_safe_edit)

        await sam_pick_provider(callback, callback_data, session, Language.EN)
        assert mock_safe_edit.called
        args, kwargs = mock_safe_edit.call_args
        # Markup has buttons for shamcash and syriatel
        markup = args[2]
        callback_datas = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert any("provider=shamcash" in cd or "shamcash" in cd for cd in callback_datas)

    @pytest.mark.asyncio
    async def test_sam_pick_currency_for_shamcash(self, monkeypatch):
        from handlers.user.sam import sam_pick_currency

        callback = MagicMock()
        callback_data = SamCallback.create(level=1, provider="shamcash")
        mock_safe_edit = AsyncMock()
        monkeypatch.setattr("handlers.user.sam.safe_edit_message", mock_safe_edit)

        await sam_pick_currency(callback, callback_data, Language.EN)
        assert mock_safe_edit.called
        args, kwargs = mock_safe_edit.call_args
        markup = args[2]
        button_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        # Should offer both USD and SYP options
        assert any("USD" in text for text in button_texts)
        assert any("SYP" in text for text in button_texts)

    @pytest.mark.asyncio
    async def test_sam_amount_prompt_currency_assignment(self, monkeypatch):
        from handlers.user.sam import sam_amount_prompt

        callback = MagicMock()
        state = AsyncMock()
        mock_safe_edit = AsyncMock()
        monkeypatch.setattr("handlers.user.sam.safe_edit_message", mock_safe_edit)

        # 1. ShamCash with USD
        cb_usd = SamCallback.create(level=2, provider="shamcash", currency="USD")
        await sam_amount_prompt(callback, cb_usd, state, Language.EN)
        state.update_data.assert_called_with(sam_provider="shamcash", sam_waiting_amount=True, sam_currency="USD")

        # 2. ShamCash with SYP
        cb_syp = SamCallback.create(level=2, provider="shamcash", currency="SYP")
        await sam_amount_prompt(callback, cb_syp, state, Language.EN)
        state.update_data.assert_called_with(sam_provider="shamcash", sam_waiting_amount=True, sam_currency="SYP")
