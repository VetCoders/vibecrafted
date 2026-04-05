from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"


class HtmlLinkCollector(HTMLParser):
    def __init__(self, source: Path) -> None:
        super().__init__()
        self.source = source
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        for key in ("href", "src"):
            raw = attr_map.get(key)
            if not raw or raw.startswith(
                ("http://", "https://", "mailto:", "data:", "javascript:")
            ):
                continue

            parts = urlsplit(raw)
            path_part = parts.path
            if not path_part:
                continue

            if raw.startswith("/"):
                target = (DOCS_ROOT / path_part.lstrip("/")).resolve()
            else:
                target = (self.source.parent / path_part).resolve()

            if not target.exists():
                self.errors.append(
                    f"{self.source.relative_to(REPO_ROOT)} missing {key} -> {raw}"
                )
                continue

            if parts.fragment and target.suffix == ".html":
                text = target.read_text(encoding="utf-8")
                fragment = parts.fragment
                if f'id="{fragment}"' not in text and f"id='{fragment}'" not in text:
                    self.errors.append(
                        f"{self.source.relative_to(REPO_ROOT)} missing fragment -> {raw}"
                    )


def test_docs_html_local_links_and_assets_exist() -> None:
    errors: list[str] = []

    for html_file in DOCS_ROOT.rglob("*.html"):
        collector = HtmlLinkCollector(html_file)
        collector.feed(html_file.read_text(encoding="utf-8"))
        errors.extend(collector.errors)

    assert not errors, "\n".join(errors)
