#!/usr/bin/env python3
"""Seed renderer for agents-workshop layouts. Next week: Layout factory."""

from __future__ import annotations

import html
import json
from pathlib import Path

W, H = 182, 130
RAIL = 26
CANVAS = W - RAIL  # 156
REPO = Path(__file__).resolve().parents[3]
DOCS = Path(__file__).resolve().parent
PLAN = (
    Path.home()
    / ".vibecrafted/artifacts/vetcoders/vibecrafted/2026_0817/plans/agents-workshop-layouts"
)

SESSION = "01a00bfd-5efc-7bf0-883f-a5d096f5235d"
AUTHOR = "grok <agents@vetcoders.io>"
DATE = "2026-08-17"


def vis(s: str) -> int:
    return len(s)


def clip(s: str, n: int, fill: str = " ") -> str:
    s = s.replace("\t", " ")
    if vis(s) > n:
        return s[:n]
    return s + fill * (n - vis(s))


def lr(left: str, right: str, w: int) -> str:
    left, right = left[:w], right[:w]
    gap = w - vis(left) - vis(right)
    if gap < 1:
        return (left + right)[:w]
    return left + (" " * gap) + right


def wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = (cur + " " + word).strip()
        if vis(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def frontmatter(*, layout_id: str, title: str, kind: str = "layout") -> str:
    return (
        "---\n"
        f"status: draft\n"
        f"kind: {kind}\n"
        f"layout_id: {layout_id}\n"
        f"title: {title}\n"
        f"owner: grok\n"
        f"authored_by: {AUTHOR}\n"
        f"session_id: {SESSION}\n"
        f"date: {DATE}\n"
        f"grid: {W}x{H}\n"
        f"source_cheat: 182x40\n"
        f"scope: agents-workshop\n"
        f"product: vibecrafted\n"
        f"next: layout-factory\n"
        "---\n"
    )


class Frame:
    def __init__(self) -> None:
        self.rows = [[" "] * W for _ in range(H)]

    def put(self, x: int, y: int, s: str) -> None:
        for i, ch in enumerate(s):
            xx = x + i
            if 0 <= y < H and 0 <= xx < W:
                self.rows[y][xx] = ch

    def hline(self, x: int, y: int, n: int, ch: str = "─") -> None:
        self.put(x, y, ch * n)

    def rect(self, x: int, y: int, w: int, h: int) -> None:
        if h < 2 or w < 2:
            return
        self.put(x, y, "┌" + "─" * (w - 2) + "┐")
        for yy in range(y + 1, y + h - 1):
            self.put(x, yy, "│")
            self.put(x + w - 1, yy, "│")
            for xx in range(x + 1, x + w - 1):
                self.rows[yy][xx] = " "
        self.put(x, y + h - 1, "└" + "─" * (w - 2) + "┘")

    def fill(self, x: int, y: int, w: int, h: int, ch: str = " ") -> None:
        for yy in range(y, y + h):
            self.put(x, yy, ch * w)

    def lines(self) -> list[str]:
        return ["".join(r) for r in self.rows]


def compact_bar() -> str:
    left = "  Vibecrafted.    |  L   ○ Start here    ◉ Agents Interactive    ○ shell    ○ voc"
    right = "Composer  ·  Quick cmd"
    return clip(lr(left, right, W), W)


def status_bar() -> str:
    left = " LOCK   PANE   TAB   MOVE   SEARCH"
    right = "Composer · Quick cmd   LIVE 3 | CPU  ·  | MEM  ·  | DISK  ·  | HEALTH"
    return clip(lr(left, right, W), W)


def paint_chrome(fr: Frame) -> None:
    fr.put(0, 0, compact_bar())
    fr.put(0, H - 1, status_bar())


def paint_rail(fr: Frame) -> None:
    rail = [
        "SESSIONS 5",
        " ● Live 3",
        "01 ○ main",
        "02 ○ lbrx-services",
        "   · Shell",
        "03 ○ w-c207-r155013",
        "   · resume-grok",
        "   · resume-codex",
        "04 ◉ vibecrafted-release",
        "   · Start here",
        "   ◉ Agents Interactive",
        "   · shell",
        "   · voc",
        "05 ○ vibecrafted-vc_",
        "   · resume-grok",
        "   · Shell",
        "   · grok",
    ]
    for i, line in enumerate(rail):
        fr.put(0, 1 + i, clip(line, RAIL))


def paint_canvas_frame(fr: Frame, title: str, switcher: str) -> None:
    x, y = RAIL, 1
    w, h = CANVAS, H - 2
    fr.rect(x, y, w, h)
    left = "┌ " + title + " "
    right = " " + switcher + " ┐"
    fill = w - vis(left) - vis(right)
    if fill < 1:
        left = clip(left, w - vis(right) - 1)
        fill = w - vis(left) - vis(right)
    fr.put(x, y, left + ("─" * fill) + right)


def paint_text(fr: Frame, x: int, y: int, lines: list[str], width: int) -> int:
    for i, line in enumerate(lines):
        fr.put(x, y + i, clip(line, width))
    return y + len(lines)


def grok_transcript() -> list[str]:
    blocks = [
        "4.1.0 release · fix/4.1.0-patch-resume-no-implicit-native-session",
        "No todo items.",
        "",
        "Maciej: floating panele, potem Ctrl+P i strzałki. hehe",
        "",
        "To nie jest sześć ekranów. To jeden talerz. Strzałki przewracają karty.",
        "Cały czas sesja 04 vibecrafted-release, tab Agents Interactive.",
        "Host już umie: float, rename, PANE, strzałki, list-panes.",
        "",
        "Agent switcher na Quick cmd to atrapa. Prawdziwe [‹][›] Groka to inna talia,",
        "wewnątrz tego TTY. voc Observe 8 live to trzecia talia — farma, nie ten tab.",
        "",
        "Maciej: brakowało jednego przycisku do designu: [New agent]",
        "",
        "Pasek talii hosta:",
        "  [‹][›]           poprzednia / następna twarz tego taba",
        "  [Voc Console]    drzwi / oczy",
        "  [New agent]      narodziny interaktywnego panelu",
        "",
        "Z Session Managera bierzemy rytuał karty, nie listę KDL",
        "(vibecrafted / host / dashboard / workflow / marbles).",
        "",
        "Trzy osie konfiguratora:",
        "  agent     agy  claude  codex  grok  junie",
        "  rytuał    init  resume  operator  partner",
        "  ścieżka   gdzie się rodzi",
        "",
        "↑/↓ wiersz. ←/→ chip. spacja zaznacz. enter odpal. esc anuluj.",
        "",
        "[New agent] = tylko interaktywny TTY na tym tabie.",
        "Headless / runy idą później jako [New dispatch], albo z wnętrza już",
        "żywego interaktywnego agenta, albo z Quick cmd — inny widok.",
        "",
        "[resume] jest jawnym wyborem. Bez cichego native-attach.",
        "",
        "Za tydzień: Layout factory. Te rysunki są Layout-1..n — analog CUT-1..n.",
        "",
        "Sciaga operatora: 182x40. Makieta jest wyzsza (130), zeby bylo widac",
        "rozmowe i karte naraz. Zywe okno zostaje ~40 wierszy; to jest widok do recenzji.",
    ]
    width = CANVAS - 4
    out: list[str] = []
    for block in blocks:
        if block == "":
            out.append("")
        else:
            out.extend(wrap(block, width))
    return out


def paint_prompt(fr: Frame, y: int, model: str) -> None:
    x = RAIL + 2
    w = CANVAS - 4
    fr.put(x, y, "╭" + "─" * (w - 2) + "╮")
    fr.put(x, y + 1, "│ ❯" + " " * (w - 4) + "│")
    fr.put(x, y + 2, "╰" + clip("─ " + model + " ", w - 2, "─") + "╯")
    fr.put(
        x,
        y + 3,
        "Ctrl+\\ dashboard   Ctrl+[ ] talia wewnątrz TTY   (nie mylić z hostowym [‹][›])",
    )


def workshop(switcher: str, title: str, transcript: list[str], model: str) -> Frame:
    fr = Frame()
    paint_chrome(fr)
    paint_rail(fr)
    paint_canvas_frame(fr, title, switcher)
    y = paint_text(fr, RAIL + 2, 3, transcript, CANVAS - 4)
    # keep prompt near the bottom of content, above status
    prompt_y = min(H - 8, max(y + 2, H - 12))
    paint_prompt(fr, prompt_y, model)
    return fr


def box_new_agent(focus: str = "agent") -> list[str]:
    inner_w = 92
    agents = ["agy", "claude", "codex", "grok", "junie"]
    flows = ["init", "resume", "operator", "partner"]

    def chips(items: list[str], selected: str) -> str:
        parts = []
        for it in items:
            parts.append(f"« {it} »" if it == selected else f"[ {it} ]")
        return "   ".join(parts)

    def mark(name: str) -> str:
        return "▸" if focus == name else " "

    path = "/Volumes/vc-workspace/vetcoders/vibecrafted-suite/vibecrafted"
    if focus == "path":
        path += "█"
    rows_inner = [
        "",
        f"  {mark('agent')} agent",
        f"    {chips(agents, 'grok')}",
        "",
        f"  {mark('workflow')} rytuał",
        f"    {chips(flows, 'resume')}",
        "",
        f"  {mark('path')} ścieżka",
        f"    {path}",
        "",
        "  Enter otworzy interaktywny panel na tym tabie.",
        "  Nie nowa sesja muxa. Nie headless. Nie farma voc.",
        "",
    ]
    title = "┌ ❯ Nowy agent "
    right = " [Anuluj] ┐"
    fill = inner_w - vis(title) - vis(right)
    top = title + ("─" * fill) + right
    bot = (
        "└"
        + clip(
            "─ ↑/↓ wiersz   ←/→ chip   spacja zaznacz   enter odpal   esc ",
            inner_w - 2,
            "─",
        )
        + "┘"
    )
    body = ["│" + clip(s, inner_w - 2) + "│" for s in rows_inner]
    return [top, *body, bot]


def box_new_dispatch() -> list[str]:
    inner_w = 92
    rows_inner = [
        "",
        "  ▸ agent",
        "    [ agy ]   [ claude ]   [ codex ]   « grok »   [ junie ]",
        "",
        "    rytuał",
        "    [ init ]   « resume »   [ operator ]   [ partner ]",
        "",
        "    ścieżka",
        "    /Volumes/vc-workspace/vetcoders/vibecrafted-suite/vibecrafted",
        "",
        "  Enter odpalą HEADLESS workera. Bez TTY. Widać go na serwerze / w voc.",
        "  Później: można go „położyć” na panel jako obserwację, nie jako twarz.",
        "",
    ]
    title = "┌ ❯ Nowy dispatch "
    right = " [Anuluj] ┐"
    fill = inner_w - vis(title) - vis(right)
    top = title + ("─" * fill) + right
    bot = (
        "└"
        + clip("─ ten sam chassis co Nowy agent · inne narodziny ", inner_w - 2, "─")
        + "┘"
    )
    body = ["│" + clip(s, inner_w - 2) + "│" for s in rows_inner]
    return [top, *body, bot]


def box_voc() -> list[str]:
    inner_w = 72
    rows_inner = [
        "  4 twarze na tym tabie · 0 wierszy farmy",
        "",
        "  ● grok      vibecrafted      14m   na wierzchu",
        "  ○ claude    vibecrafted       0m   właśnie urodzony",
        "  ○ codex     vc-workspace      1h   float",
        "  ○ junie     ~                40m   float",
        "",
        "  j/k wybierz    enter podnieś    n Nowy agent",
        "",
        "  To nie jest Observe · 8 live.",
        "  To talia, którą [‹][›] już przekłada.",
    ]
    title = "┌ voc · ten tab · Agents Interactive "
    right = " PIN ◉ ┐"
    fill = inner_w - vis(title) - vis(right)
    top = title + ("─" * max(1, fill)) + right
    bot = "└" + clip("─ drzwi do talii tego taba ", inner_w - 2, "─") + "┘"
    body = ["│" + clip(s, inner_w - 2) + "│" for s in rows_inner]
    return [top, *body, bot]


def clear_canvas_band(fr: Frame, y0: int, y1: int) -> None:
    """Empty the pane interior so a card does not slice words."""
    for y in range(max(2, y0), min(H - 2, y1)):
        fr.put(RAIL + 2, y, " " * (CANVAS - 4))


def stamp(fr: Frame, box: list[str], x: int, y: int) -> None:
    clear_canvas_band(fr, y - 1, y + len(box) + 1)
    for i, line in enumerate(box):
        fr.put(x, y + i, line)


SWITCH_NOW = "[‹] 2/4 [›]  [Voc Console] [New agent]"
SWITCH_AFTER = "[‹] 3/5 [›]  [Voc Console] [New agent]"


def layout_1() -> list[str]:
    return workshop(
        SWITCH_NOW, "grok · vibecrafted", grok_transcript(), "Grok 4.6 · always-approve"
    ).lines()


def layout_2() -> list[str]:
    fr = workshop(
        SWITCH_NOW, "grok · vibecrafted", grok_transcript(), "Grok 4.6 · always-approve"
    )
    box = box_new_agent("agent")
    x = RAIL + (CANVAS - vis(box[0])) // 2
    y = 28
    stamp(fr, box, x, y)
    return fr.lines()


def layout_3() -> list[str]:
    born = [
        "claude · resume · /Volumes/vc-workspace/vetcoders/vibecrafted-suite/vibecrafted",
        "",
        "Właśnie się urodził. Interaktywny TTY. Host nadał tytuł.",
        "Talia jest teraz 3/5. Ten panel jest na wierzchu.",
        "",
        "Poprzedni grok żyje jedno [‹] wstecz.",
        "Nie powstała nowa sesja vc-frame. Nie powstał Tab #7. Nie powstał resume-*.",
        "",
        "Jeśli chcesz headless — to nie ten przycisk. To [New dispatch] (Layout-5)",
        "albo dispatch z wnętrza tej sesji, albo Quick cmd.",
    ]
    width = CANVAS - 4
    lines: list[str] = []
    for b in born:
        lines.extend([""] if b == "" else wrap(b, width))
    return workshop(
        SWITCH_AFTER,
        "claude · resume · vibecrafted",
        lines,
        "Claude · interactive pane",
    ).lines()


def layout_4() -> list[str]:
    fr = workshop(
        SWITCH_NOW, "grok · vibecrafted", grok_transcript(), "Grok 4.6 · always-approve"
    )
    box = box_voc()
    stamp(fr, box, RAIL + 6, 24)
    return fr.lines()


def layout_5() -> list[str]:
    fr = workshop(
        SWITCH_NOW, "grok · vibecrafted", grok_transcript(), "Grok 4.6 · always-approve"
    )
    box = box_new_dispatch()
    x = RAIL + (CANVAS - vis(box[0])) // 2
    stamp(fr, box, x, 28)
    return fr.lines()


def fence(lines: list[str]) -> str:
    assert len(lines) == H, len(lines)
    for i, line in enumerate(lines):
        if vis(line) != W:
            raise SystemExit(f"row {i} width {vis(line)}")
    tens = "".join(str((i // 10) % 10) if i % 10 == 0 else " " for i in range(W))
    ones = "".join(str(i % 10) for i in range(W))
    return "```\n" + tens + "\n" + ones + "\n" + "\n".join(lines) + "\n```\n"


PRAWO = f"""{frontmatter(layout_id="Layout-0", title="Prawo siatki i dwóch drzwi", kind="design-doc")}
# Agents workshop — prawo, korekty, Layout-1..n

Te pliki są po to, żeby **człowiek** zobaczył warsztat zanim ktokolwiek ruszy plugin.
Nie są kalką bałaganu z żywej ściągi. Są spakowanym celem na siatce ze ściągi.

## Frontmatter — jak mnie znaleźć

Każdy Layout ma:

```
owner: grok
authored_by: {AUTHOR}
session_id: {SESSION}
date: {DATE}
grid: {W}x{H}
```

Szukaj `session_id: {SESSION}` albo `authored_by: grok`.

## Siatka

| | żywa ściąga | makieta do recenzji |
|---|---|---|
| szerokość | ~182 | **182** |
| wysokość | ~40 | **130** |
| po co wyżej | okno na laptopie | widać rozmowę i kartę naraz, bez 20 pustych dziur |

```
wiersz    1     compact-bar
wiersze   2–129 ciało   (rail {RAIL} + canvas {CANVAS})
wiersz    130   status-bar
```

Żywe okno zostaje ~40. 130 to widok recenzji (jakbyś zescrollował TUI).

## Korekty po przejściu oczami użytkownika (delta 40→130)

Poprzednie 182×40 były nie do użycia jako makieta:

1. Środek był pusty. Wyglądało jak zepsuty TUI, nie warsztat.
2. Karta „Nowy agent” przecinała słowa w tle (`THIS ta│`). Nie da się tego czytać.
3. Ścieżka ucinała się na `vibecr`. Nie sprawdzisz, gdzie się rodzi.
4. Na pasku NOW wisiał już `[New dispatch]`. Za wcześnie — myli drzwi.
5. `Tab #6` w celu. W celu ten tab nazywa się `voc`.
6. Trzy kopie tej samej pustej ramki na trzy stany fokusu. Człowiek nie porównuje, tylko się gubi.
7. Angielskie notatki projektowe w środku „produktu”. Tu chrome zostaje jak żywy (SESSIONS/LOCK), karta mówi po polsku.

Wektor z naszych klatek:

float+PANE+strzałki → talia hosta → brakowało `[New agent]` → rytuał 3 osi, nie KDL → headless to inne drzwi.

## Dwa launchery

| drzwi | przycisk | narodziny |
|---|---|---|
| teraz | `[New agent]` | interaktywny TTY na **tym** tabie |
| później | `[New dispatch]` | worker, najlepiej headless, tylko przez serwer |
| zawsze | z wewnątrz żywego interaktywnego agenta | dispatch jak dziś |
| zawsze | Quick cmd | osobny widok, nie atrapa paska |

## Nawigacja karty

| klawisz | skutek |
|---|---|
| `↑` `↓` | wiersz agent → rytuał → ścieżka |
| `←` `→` | chip (w ścieżce: kursor) |
| `spacja` | zaznacz chip |
| `enter` | launch |
| `esc` / Anuluj | nic się nie rodzi |

## Layout factory (za tydzień)

CUT-1..n były briefami do cięcia kodu.
**Layout-1..n** są rysunkami do cięcia powierzchni.

Nie generujemy jeszcze KDL. Te pliki są ziarnem fabryki.

## Pliki

| id | plik | co widzisz |
|---|---|---|
| Layout-0 | ten dokument | prawo |
| Layout-1 | `Layout-1.md` | warsztat, jedna twarz |
| Layout-2 | `Layout-2.md` | Nowy agent (karta) |
| Layout-3 | `Layout-3.md` | po Enter |
| Layout-4 | `Layout-4.md` | voc jako drzwi tego taba |
| Layout-5 | `Layout-5.md` | Nowy dispatch, później |

HTML studio: `preview.html` (lewe taby Layout-1..n, jeden canvas). Analog `/scaffold/editor`.
"""


LAYOUTS = [
    ("Layout-0", "Prawo siatki i dwóch drzwi", "design-doc", None, PRAWO),
    (
        "Layout-1",
        "Warsztat",
        "brief",
        layout_1,
        "Jedna twarz. Pasek talii w tytule, nie na Quick cmd. Rail zostaje. Zero nachodzących floatów.\n",
    ),
    (
        "Layout-2",
        "Nowy agent",
        "brief",
        layout_2,
        "Rytuał z Session Managera, nie jego lista. Tylko interaktywny launch. `←` `→` po chipach.\n",
    ),
    (
        "Layout-3",
        "Po launchu",
        "brief",
        layout_3,
        "Enter z karty. Urodził się panel. Talia 3/5. Poprzedni grok jedno `[‹]` wstecz.\n",
    ),
    (
        "Layout-4",
        "Voc drzwi",
        "brief",
        layout_4,
        "`[Voc Console]` podnosi voc. Lista = twarze tego taba, nie Observe 8 live.\n",
    ),
    (
        "Layout-5",
        "Nowy dispatch (później)",
        "brief",
        layout_5,
        "Nie budujemy teraz. Ten sam chassis. Inne narodziny: headless, serwer, nie TTY.\n",
    ),
]


def md_for(layout_id: str, title: str, kind: str, drawer, preface: str) -> str:
    head = frontmatter(layout_id=layout_id, title=title, kind=kind)
    if drawer is None:
        return preface
    return head + f"# {layout_id} · {title}\n\n{preface}\n" + fence(drawer())


def preview_html(frames: dict[str, list[str]]) -> str:
    tabs = []
    sections = []
    for i, (lid, title, *_rest) in enumerate(LAYOUTS):
        if lid == "Layout-0":
            continue
        body = "\n".join(frames[lid])
        tabs.append(
            f'<button type="button" class="tab{" is-active" if i == 1 else ""}" data-id="{lid}">{lid}<span>{html.escape(title)}</span></button>'
        )
        sections.append(
            f'<section class="doc{" is-active" if i == 1 else ""}" id="{lid}">'
            f"<pre>{html.escape(body)}</pre></section>"
        )
    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Agents workshop · Layout-1..n</title>
<style>
:root {{
  --bg:#101216; --ink:#e8e6e1; --mute:#8b8a84; --line:#2a2d33;
  --accent:#c4b08a; --rail:#16181d; --hi:#1e2229;
  font-family: ui-sans-serif, system-ui, sans-serif;
}}
* {{ box-sizing:border-box; }}
html,body {{ margin:0; height:100%; background:var(--bg); color:var(--ink); }}
.app {{ display:grid; grid-template-columns:220px 1fr 240px; grid-template-rows:48px 1fr 28px; height:100%; }}
.top {{ grid-column:1/-1; display:flex; align-items:center; gap:16px; padding:0 16px; border-bottom:1px solid var(--line); }}
.brand {{ letter-spacing:.08em; font-size:13px; color:var(--accent); }}
.top small {{ color:var(--mute); }}
.left {{ background:var(--rail); border-right:1px solid var(--line); padding:12px 8px; overflow:auto; }}
.tab {{ display:flex; flex-direction:column; align-items:flex-start; width:100%; gap:2px; margin:0 0 4px; padding:8px 10px; background:transparent; color:var(--ink); border:1px solid transparent; border-radius:6px; cursor:pointer; text-align:left; }}
.tab span {{ color:var(--mute); font-size:12px; }}
.tab.is-active {{ background:var(--hi); border-color:var(--line); }}
.center {{ overflow:auto; padding:16px; }}
.doc {{ display:none; }}
.doc.is-active {{ display:block; }}
pre {{ margin:0; font:12px/1.15 ui-monospace, Menlo, Consolas, monospace; white-space:pre; color:#d7d4cc; }}
.right {{ border-left:1px solid var(--line); padding:16px; font-size:13px; }}
.right h2 {{ font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--mute); margin:0 0 8px; }}
.right p {{ margin:0 0 10px; color:var(--mute); }}
.stat {{ border-top:1px solid var(--line); grid-column:1/-1; display:flex; gap:24px; align-items:center; padding:0 16px; font-size:12px; color:var(--mute); }}
</style>
</head>
<body>
<div class="app">
  <header class="top">
    <div class="brand">Vibecrafted. · Layout studio</div>
    <small>182×130 · analog CUT-1..n · seed Layout factory</small>
  </header>
  <nav class="left">{"".join(tabs)}</nav>
  <main class="center">{"".join(sections)}</main>
  <aside class="right">
    <h2>Inspector</h2>
    <p>owner: grok</p>
    <p>authored_by: {html.escape(AUTHOR)}</p>
    <p>session: {SESSION}</p>
    <p>date: {DATE}</p>
    <p>grid: {W}×{H}</p>
    <p>Źródło: ściąga 182×40. Wysokość 130 jest do recenzji, nie do okna laptopa.</p>
    <p>Layout-5 jest przygaszony w prawie — nie budujemy go teraz.</p>
  </aside>
  <footer class="stat">
    <span>studio · jeden dokument</span>
    <span>znaki/wiersz {W}</span>
    <span>wiersze {H}</span>
    <span>Layout-1..5</span>
  </footer>
</div>
<script>
const tabs=[...document.querySelectorAll('.tab')];
const docs=[...document.querySelectorAll('.doc')];
function show(id){{
  tabs.forEach(t=>t.classList.toggle('is-active', t.dataset.id===id));
  docs.forEach(d=>d.classList.toggle('is-active', d.id===id));
  history.replaceState(null,'','#'+id);
}}
tabs.forEach(t=>t.addEventListener('click',()=>show(t.dataset.id)));
if(location.hash) show(location.hash.slice(1));
</script>
</body>
</html>
"""


def manifest() -> dict:
    arts = []
    for lid, title, role, *_ in LAYOUTS:
        path = "README.md" if lid == "Layout-0" else f"layouts/{lid}.md"
        arts.append(
            {
                "id": lid.lower(),
                "role": role,
                "path": path,
                "editable": True,
                "required": True,
                "title": title,
            }
        )
    return {
        "schema_version": "1",
        "plan_id": "agents-workshop-layouts",
        "org": "vetcoders",
        "repo": "vibecrafted",
        "day": "2026_0817",
        "title": "Agents workshop · Layout-1..n",
        "owner": "grok",
        "authored_by": AUTHOR,
        "session_id": SESSION,
        "artifacts": arts,
    }


def write_all() -> None:
    frames = {
        "Layout-1": layout_1(),
        "Layout-2": layout_2(),
        "Layout-3": layout_3(),
        "Layout-4": layout_4(),
        "Layout-5": layout_5(),
    }
    docs_files = {
        "00-prawo.md": PRAWO,
        "Layout-1.md": md_for("Layout-1", "Warsztat", "brief", layout_1, LAYOUTS[1][4]),
        "Layout-2.md": md_for(
            "Layout-2", "Nowy agent", "brief", layout_2, LAYOUTS[2][4]
        ),
        "Layout-3.md": md_for(
            "Layout-3", "Po launchu", "brief", layout_3, LAYOUTS[3][4]
        ),
        "Layout-4.md": md_for(
            "Layout-4", "Voc drzwi", "brief", layout_4, LAYOUTS[4][4]
        ),
        "Layout-5.md": md_for(
            "Layout-5", "Nowy dispatch (później)", "brief", layout_5, LAYOUTS[5][4]
        ),
        "preview.html": preview_html(frames),
    }
    # drop leftover short mockups
    for stale in (
        "01-warsztat.md",
        "02-new-agent.md",
        "03-po-launchu.md",
        "04-voc-drzwi.md",
        "05-new-dispatch-pozniej.md",
    ):
        p = DOCS / stale
        if p.exists():
            p.unlink()

    DOCS.mkdir(parents=True, exist_ok=True)
    for name, text in docs_files.items():
        (DOCS / name).write_text(text, encoding="utf-8")
        print("docs", name, "bytes", len(text.encode()))

    PLAN.mkdir(parents=True, exist_ok=True)
    (PLAN / "layouts").mkdir(exist_ok=True)
    (PLAN / "README.md").write_text(PRAWO, encoding="utf-8")
    for lid in ("Layout-1", "Layout-2", "Layout-3", "Layout-4", "Layout-5"):
        (PLAN / "layouts" / f"{lid}.md").write_text(
            docs_files[f"{lid}.md"], encoding="utf-8"
        )
    (PLAN / "preview.html").write_text(docs_files["preview.html"], encoding="utf-8")
    (PLAN / "manifest.json").write_text(
        json.dumps(manifest(), indent=2) + "\n", encoding="utf-8"
    )
    print("plan", PLAN)


if __name__ == "__main__":
    write_all()
