from change_plate_next.interfaces.desktop.i18n import Translator, language_from_locale, normalize_language


def test_language_from_locale() -> None:
    assert language_from_locale("zh_CN") == "zh"
    assert language_from_locale("fr-FR") == "fr"
    assert language_from_locale("en_US") == "en"
    assert language_from_locale("de_DE") == "en"


def test_translator_returns_supported_languages() -> None:
    assert Translator("en").text("button.export") == "Export"
    assert Translator("fr").text("button.export") == "Exporter"
    assert Translator("zh").text("button.export") == "导出"


def test_translator_fallbacks() -> None:
    assert normalize_language(None) == "en"
    assert Translator("de").language == "en"
    assert Translator("fr").text("missing.key") == "missing.key"


def test_homepage_uses_compose_language_not_queue() -> None:
    assert Translator("en").text("nav.compose") == "Compose"
    assert "queue" not in Translator("en").text("hero.description").lower()
    assert "queue" not in Translator("en").text("page.compose.caption").lower()
    assert "queue" not in Translator("en").text("metric.sources.label").lower()
    assert "队列" not in Translator("zh").text("hero.description")
    assert "队列" not in Translator("zh").text("page.compose.caption")
    assert "队列" not in Translator("zh").text("metric.sources.label")
