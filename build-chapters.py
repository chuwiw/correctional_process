#!/usr/bin/env python3
"""Parse fic txt and generate chapter HTML pages."""

import html
import re
from pathlib import Path

SOURCE = Path(r"c:\Users\Asus\Downloads\13-573890-defuse-the-error.txt")
OUT_DIR = Path(__file__).parent

CHAPTERS = [
    {
        "file": "chapter-1.html",
        "title": "протяни руку – и это станет твоим.",
        "meta": "2 декабря 2024 г., 09:54 · Отзывы: 1132",
        "marker": "========== протяни руку – и это станет твоим. ==========",
    },
    {
        "file": "chapter-2.html",
        "title": "обещание / 13-573890.",
        "meta": "5 декабря 2024 г., 09:18 · Отзывы: 744",
        "marker": "========== обещание / 13-573890. ==========",
    },
    {
        "file": "chapter-3.html",
        "title": "maybe in the next life.",
        "meta": "10 декабря 2024 г., 08:52 · Отзывы: 846",
        "marker": "========== maybe in the next life. ==========",
    },
    {
        "file": "chapter-4.html",
        "title": "defuse the error.",
        "meta": "14 декабря 2024 г., 08:17 · Отзывы: 725",
        "marker": "========== defuse the error. ==========",
    },
    {
        "file": "chapter-5.html",
        "title": "and if you go, i wanna go with you.",
        "meta": "13 февраля 2025 г., 08:14 · Отзывы: 872",
        "marker": "========== and if you go, i wanna go with you. ==========",
    },
    {
        "file": "chapter-6.html",
        "title": "and if you die, i wanna die with you.",
        "meta": "7 апреля 2025 г., 09:21 · Отзывы: 1892",
        "marker": "========== and if you die, i wanna die with you. ==========",
    },
]

FOOTNOTE_RE = re.compile(r"\{\?\}\[[^\]]*\]")


def clean_line(line: str) -> str:
    line = FOOTNOTE_RE.sub("", line)
    return line.rstrip()


def text_to_html(text: str) -> str:
    parts: list[str] = []
    note_lines: list[str] = []
    in_note = False

    def flush_note() -> None:
        nonlocal note_lines, in_note
        if note_lines:
            note_html = "<br>".join(html.escape(line) for line in note_lines)
            parts.append(f'<div class="author-note">{note_html}</div>')
            note_lines = []
        in_note = False

    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        stripped = line.strip()
        if not stripped:
            flush_note()
            continue

        if stripped == "...":
            flush_note()
            parts.append('<p class="scene-break">...</p>')
            continue

        is_indented = raw_line.startswith("    ")

        if stripped.startswith("Комментарий к"):
            flush_note()
            in_note = True
            note_lines.append(stripped)
            continue

        if in_note and is_indented:
            note_lines.append(stripped)
            continue

        flush_note()
        parts.append(f"<p>{html.escape(stripped)}</p>")

    flush_note()
    return "\n\n    ".join(parts)


def split_chapters(raw: str) -> list[str]:
    markers = [ch["marker"] for ch in CHAPTERS]
    positions = []
    for marker in markers:
        idx = raw.find(marker)
        if idx == -1:
            raise ValueError(f"Marker not found: {marker}")
        positions.append(idx)

    bodies = []
    for i, start in enumerate(positions):
        content_start = start + len(markers[i])
        content_end = positions[i + 1] if i + 1 < len(positions) else len(raw)
        bodies.append(raw[content_start:content_end].strip())
    return bodies


def chapter_nav(i: int) -> str:
    prev_link = (
        f'<a class="chapter-nav-link" href="{CHAPTERS[i - 1]["file"]}">← {CHAPTERS[i - 1]["title"]}</a>'
        if i > 0
        else '<span class="chapter-nav-link disabled">←</span>'
    )
    next_link = (
        f'<a class="chapter-nav-link" href="{CHAPTERS[i + 1]["file"]}">{CHAPTERS[i + 1]["title"]} →</a>'
        if i + 1 < len(CHAPTERS)
        else '<span class="chapter-nav-link disabled">→</span>'
    )
    return f"""
  <div class="chapter-nav">
    {prev_link}
    <a class="chapter-nav-link index-link" href="index.html">Содержание</a>
    {next_link}
  </div>"""


def page_template(title: str, meta: str, body_html: str, nav_html: str) -> str:
    page_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>{page_title} — 13–573890</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>

<div class="browser-bar">
  <div class="browser-pill">
    <span>ficbook.net/readfic/019381d2-4d15-796e-b2e0-1c02512792fa</span>
    <div class="browser-right">
      <div class="tab-count">19</div>
      <span>⋮</span>
    </div>
  </div>
</div>

<div class="install-banner">
  <div class="close">✕</div>
  <div class="app-icon"></div>
  <div class="banner-content">
    <div class="banner-title">Книга Фанфиков</div>
    <div class="banner-sub">Установить в Google Play</div>
  </div>
  <div class="install-link">Установить</div>
</div>

<div class="top-nav">
  <div class="logo"></div>
  <div class="write-btn">✎ Писать</div>
  <div class="notif">🔔<span class="badge">47</span></div>
  <div class="notif">💬<span class="badge">71</span></div>
  <div class="avatar"></div>
</div>

<div class="tabs">
  <div class="tab">Рекомендации</div>
  <div class="tab">Фанфики</div>
  <div class="tab">Авторы</div>
  <div class="tab">ТОП</div>
  <div class="search-btn">⌕</div>
  <div class="menu-btn">☰</div>
</div>

<div class="reading-section">
  <div class="reading-header">{page_title}</div>
  <div class="reading-meta">{html.escape(meta)}</div>
  <div class="reading-body">

    {body_html}

  </div>
  {nav_html}
</div>

<div class="fixed-actions">
  <button class="fixed-btn bookmark-btn" aria-label="Добавить в закладки" onclick="this.style.background=this.style.background==='#27ae60'?'#4a90d9':'#27ae60'">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>
  </button>
  <button class="fixed-btn scroll-top-btn" aria-label="Наверх" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#aaa" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
  </button>
</div>

</body>
</html>
"""


def main() -> None:
    raw = SOURCE.read_text(encoding="utf-8")
    bodies = split_chapters(raw)

    for i, (chapter, body) in enumerate(zip(CHAPTERS, bodies)):
        body_html = text_to_html(body)
        nav_html = chapter_nav(i)
        page = page_template(chapter["title"], chapter["meta"], body_html, nav_html)
        out_path = OUT_DIR / chapter["file"]
        out_path.write_text(page, encoding="utf-8")
        print(f"Wrote {out_path.name} ({len(body_html)} chars)")


if __name__ == "__main__":
    main()
