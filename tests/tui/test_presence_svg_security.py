from pathlib import Path

APP_JS = Path(__file__).resolve().parents[2] / "docs" / "presence" / "app.js"


def test_mermaid_svg_links_use_a_positive_scheme_allowlist() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    sanitizer = source.split("function isSafeSvgReference", 1)[1].split(
        "function renderMermaidPreview", 1
    )[0]

    assert 'value.charAt(0) === "#"' in sanitizer
    assert 'protocol === "http:"' in sanitizer
    assert 'protocol === "https:"' in sanitizer
    assert 'protocol === "mailto:"' in sanitizer
    assert "new URL(value, document.baseURI)" in sanitizer
    assert 'protocol === "javascript:"' not in sanitizer

    render = source.split("function renderMermaidPreview", 1)[1].split(
        "function initMermaid", 1
    )[0]
    assert "!isSafeSvgReference(attr.value)" in render
