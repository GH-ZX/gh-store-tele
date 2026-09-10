from enums.bot_entity import BotEntity
from enums.language import Language
from utils.localizator import Localizator


def test_localizator_returns_text_from_json():
    assert Localizator.get_text(Language.EN, BotEntity.COMMON, "cancel") == "❌ Cancel"


def test_localizator_collects_all_localized_values():
    localized = Localizator.get_all_texts(BotEntity.COMMON, "cancel")
    assert "❌ Cancel" in localized
    assert len(localized) >= 2


def test_supported_locales_are_ar_and_en_only():
    assert sorted([m.value for m in Language]) == ["ar", "en"]
    assert Language.from_locale("de") is Language.EN
    assert Language.from_locale("AR") is Language.AR
