#!/usr/bin/env python3
"""Build ficbook mockup HTML from Correctional process PDF export."""

from __future__ import annotations

import html
import re
from pathlib import Path

from pypdf import PdfReader

PDF_PATH = Path(r"c:\Users\Asus\Downloads\Correctional-process_1778702790677 2 (1).pdf")
OUT_DIR = Path(__file__).parent
INDEX_PATH = OUT_DIR / "index.html"

FIC_ID = "13534592"
FIC_TITLE = "Correctional process"
FIC_URL = f"ficbook.net/readfic/{FIC_ID}"

TOC_ENTRY_RE = re.compile(
    r"^(Глава \d+\..+|Часть \d+\..+|Бонус\..+)$", re.MULTILINE
)
PAGE_FOOTER_RE = re.compile(r"^\s*\d+/\d+\s*$")
NOTE_HEADER_RE = re.compile(r"^Примечание к части$", re.IGNORECASE)


def extract_body_text(reader: PdfReader) -> str:
    return "\n".join(p.extract_text() or "" for p in reader.pages[3:])


def parse_toc_entries(reader: PdfReader) -> list[str]:
    toc_text = (reader.pages[1].extract_text() or "") + "\n" + (
        reader.pages[2].extract_text() or ""
    )
    entries: list[str] = []
    for line in toc_text.splitlines():
        line = line.strip()
        if not line or line in ("Оглавление", "2"):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if TOC_ENTRY_RE.fullmatch(line):
            entries.append(line)
    return entries


def parse_metadata(reader: PdfReader) -> dict[str, str]:
    meta_text = reader.pages[0].extract_text() or ""
    fields: dict[str, str] = {}

    def grab(label: str, stop_labels: list[str]) -> str:
        start = meta_text.find(label)
        if start == -1:
            return ""
        start += len(label)
        end = len(meta_text)
        for stop in stop_labels:
            idx = meta_text.find(stop, start)
            if idx != -1:
                end = min(end, idx)
        return re.sub(r"\s+", " ", meta_text[start:end]).strip()

    fields["author"] = grab("Автор:", ["Беты", "Фэндом:"])
    fields["author"] = re.sub(r"\s*https?://\S+", "", fields["author"])
    fields["author"] = re.sub(r"\(\s*\)", "", fields["author"]).strip()
    fields["betas"] = grab("Беты (редакторы):", ["Фэндом:"])
    fields["betas"] = re.sub(r"\s*https?://\S+", "", fields["betas"]).strip(" ,")
    fields["fandom"] = grab("Фэндом:", ["Пэйринг"])
    fields["pairings"] = grab("Пэйринг и персонажи:", ["Рейтинг:"])
    fields["rating"] = grab("Рейтинг:", ["Размер:"])
    fields["size"] = grab("Размер:", ["Количество частей:"])
    fields["parts"] = grab("Количество частей:", ["Статус:"])
    fields["status"] = grab("Статус:", ["Метки:"])
    fields["tags"] = grab("Метки:", ["Описание:"])
    fields["description"] = grab("Описание:", ["Примечания:"])
    fields["notes"] = grab("Примечания:", ["Публикация"])
    fields["pub"] = grab("Публикация на других ресурсах:", [])
    return fields


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()


def find_title_pos(text: str, title: str, start: int) -> int:
    title = normalize_title(title)
    pos = text.find(title, start)
    if pos != -1:
        return pos
    core = title.split(".", 1)[-1].strip()
    if len(core) > 12:
        pos = text.find(core, start)
        if pos != -1:
            return pos
    m = re.search(re.escape(title[: min(24, len(title))]), text[start:])
    if m:
        return start + m.start()
    raise ValueError(f"Title not found: {title!r}")


def split_chapters(text: str, titles: list[str]) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    positions: list[tuple[str, int]] = []
    cursor = 0
    for title in titles:
        pos = find_title_pos(text, title, cursor)
        positions.append((title, pos))
        cursor = pos + 1

    for i, (title, pos) in enumerate(positions):
        end = positions[i + 1][1] if i + 1 < len(positions) else len(text)
        body = text[pos + len(title) : end].strip()
        chunks.append((title, body))
    return chunks


def pdf_block_to_paragraphs(block: str) -> list[str]:
    """Merge PDF line wraps; ignore blank lines between wrapped fragments."""
    lines: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or PAGE_FOOTER_RE.match(line):
            continue
        lines.append(line)

    paragraphs: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            paragraphs.append(" ".join(buf))
            buf.clear()

    for line in lines:
        if line == "***":
            flush()
            paragraphs.append("***")
            continue
        if NOTE_HEADER_RE.match(line):
            flush()
            paragraphs.append("__NOTE__")
            continue
        if line.startswith("—") and buf:
            flush()
            buf.append(line)
            continue
        buf.append(line)

    flush()
    return paragraphs


def paragraphs_to_html(paragraphs: list[str]) -> str:
    parts: list[str] = []
    note_lines: list[str] = []
    in_note = False

    def flush_note() -> None:
        nonlocal in_note
        if note_lines:
            note_html = "<br>".join(html.escape(x) for x in note_lines)
            parts.append(f'<div class="author-note">{note_html}</div>')
            note_lines.clear()
        in_note = False

    for para in paragraphs:
        if para == "__NOTE__":
            flush_note()
            in_note = True
            continue
        if in_note:
            note_lines.append(para)
            continue
        if para == "***":
            flush_note()
            parts.append('<p class="scene-break">***</p>')
            continue
        if para.startswith("Комментарий к") or para.startswith("Примечание"):
            flush_note()
            in_note = True
            note_lines.append(para)
            continue
        flush_note()
        parts.append(f"<p>{html.escape(para)}</p>")

    flush_note()
    return "\n\n    ".join(parts)


def chapter_nav(i: int, chapters: list[dict]) -> str:
    prev_link = (
        f'<a class="chapter-nav-link" href="{chapters[i - 1]["file"]}">← {html.escape(chapters[i - 1]["title"])}</a>'
        if i > 0
        else '<span class="chapter-nav-link disabled">←</span>'
    )
    next_link = (
        f'<a class="chapter-nav-link" href="{chapters[i + 1]["file"]}">{html.escape(chapters[i + 1]["title"])} →</a>'
        if i + 1 < len(chapters)
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
<title>{page_title} — {html.escape(FIC_TITLE)}</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>

<div class="browser-bar">
  <div class="browser-pill">
    <span>{FIC_URL}</span>
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


def tags_html(tags_raw: str) -> str:
    tags = [t.strip() for t in re.split(r",\s*", tags_raw) if t.strip()]
    return "\n      ".join(f'<span class="tag">{html.escape(t)}</span>' for t in tags)


def pairing_tags_html(pairings_raw: str) -> str:
    parts = [p.strip() for p in re.split(r",\s*", pairings_raw) if p.strip()]
    return "\n      ".join(f'<span class="tag pairing">{html.escape(p)}</span>' for p in parts)


def _sub_once(index: str, pattern: str, repl_fn, flags: int = 0) -> str:
    match = re.search(pattern, index, flags)
    if not match:
        raise ValueError(f"Pattern not found: {pattern[:60]}")
    return index[: match.start()] + repl_fn(match) + index[match.end() :]


def update_index(meta: dict[str, str], chapters: list[dict]) -> None:
    index = INDEX_PATH.read_text(encoding="utf-8")

    index = _sub_once(
        index,
        r"<title>[^<]*</title>",
        lambda m: f"<title>{html.escape(FIC_TITLE)} — Ficbook Mockup</title>",
    )
    index = _sub_once(
        index,
        r"(<span>)ficbook\.net/readfic/[^<]*(</span>)",
        lambda m: f"{m.group(1)}{FIC_URL}{m.group(2)}",
    )
    index = _sub_once(
        index,
        r'(<div class="fic-title">)[^<]*(</div>)',
        lambda m: f"{m.group(1)}{html.escape(FIC_TITLE)}{m.group(2)}",
    )
    index = _sub_once(
        index,
        r'(<div class="author-name">)[^<]*(</div>)',
        lambda m: f"{m.group(1)}{html.escape(meta['author'])}{m.group(2)}",
    )
    index = _sub_once(
        index,
        r'(<div class="meta-value">)Stray Kids(</div>)',
        lambda m: f"{m.group(1)}{html.escape(meta['fandom'])}{m.group(2)}",
    )

    pairing_block = pairing_tags_html(meta["pairings"])

    def repl_pairing(m):
        return f"{m.group(1)}{pairing_block}\n    {m.group(2)}"

    index = _sub_once(
        index,
        r'(<div class="meta-label">Пэйринг и персонажи:</div>\s*<div class="tags-wrap">)\s*[\s\S]*?(</div>\s*\n\s*</div>\s*\n\s*<!-- Meta: Size -->)',
        lambda m: f"{m.group(1)}\n      {pairing_block}\n    {m.group(2)}",
        flags=re.DOTALL,
    )

    parts_n = meta["parts"].strip()
    size_line = f"{meta['size'].strip()}, {parts_n} частей"

    index = _sub_once(
        index,
        r'(<div class="meta-label">Размер:</div>\s*<div class="meta-value">)[^<]*(</div>)',
        lambda m: f"{m.group(1)}{html.escape(size_line)}{m.group(2)}",
        flags=re.DOTALL,
    )

    tags_block = tags_html(meta["tags"])

    index = _sub_once(
        index,
        r'(<div class="meta-label">Метки:</div>\s*<div class="tags-wrap">)\s*[\s\S]*?(</div>\s*\n\s*</div>\s*\n\s*<hr class="divider-h">)',
        lambda m: f"{m.group(1)}\n      {tags_block}\n    {m.group(2)}",
        flags=re.DOTALL,
    )

    index = _sub_once(
        index,
        r'(<div class="meta-label">Описание:</div>\s*<div style="font-size:13px;color:#ccc;margin:4px 0 2px">)[\s\S]*?(</div>\s*\n\s*</div>)',
        lambda m: f"{m.group(1)}{html.escape(meta['description'])}{m.group(2)}",
        flags=re.DOTALL,
    )

    notes_clean = meta["notes"].replace("•", "• ")

    index = _sub_once(
        index,
        r'(<div class="meta-label">Примечания:</div>\s*<div style="font-size:13px;color:#ccc;margin:4px 0 2px">)[\s\S]*?(</div>\s*\n\s*</div>)',
        lambda m: f"{m.group(1)}{html.escape(notes_clean)}{m.group(2)}",
        flags=re.DOTALL,
    )

    index = _sub_once(
        index,
        r'(<div class="meta-label">Посвящение:</div>\s*<div style="font-size:13px;color:#ccc;margin:4px 0 2px">)\s*[\s\S]*?(</div>)',
        lambda m: f"{m.group(1)}\n        —{m.group(2)}",
        flags=re.DOTALL,
    )

    index = _sub_once(
        index,
        r'(<div class="pub-label">Публикация на других ресурсах:</div>\s*<div>)[^<]*(</div>)',
        lambda m: f"{m.group(1)}{html.escape(meta['pub'])}{m.group(2)}",
        flags=re.DOTALL,
    )

    toc_items = []
    for ch in chapters:
        toc_items.append(
            f"""    <a class="toc-item" href="{ch['file']}">
      <div class="toc-item-text">
        <div class="toc-item-title">{html.escape(ch['title'])}</div>
        <div class="toc-item-sub">{html.escape(ch['meta'])}</div>
      </div>
      <div class="toc-arrow">›</div>
    </a>"""
        )
    toc_html = "\n".join(toc_items)
    index = _sub_once(
        index,
        r'(<div class="toc-list">)\s*[\s\S]*?(</div>\s*\n\s*</div><!-- end \.fic-page -->)',
        lambda m: f"{m.group(1)}\n{toc_html}\n  {m.group(2)}",
        flags=re.DOTALL,
    )

    INDEX_PATH.write_text(index, encoding="utf-8")


def main() -> None:
    reader = PdfReader(str(PDF_PATH))
    meta = parse_metadata(reader)
    titles = parse_toc_entries(reader)
    body = extract_body_text(reader)
    split = split_chapters(body, titles)

    chapters: list[dict] = []
    for i, (title, raw_body) in enumerate(split):
        chapters.append(
            {
                "file": f"chapter-{i + 1}.html",
                "title": title,
                "meta": FIC_TITLE,
            }
        )

    for i, (title, raw_body) in enumerate(split):
        paras = pdf_block_to_paragraphs(raw_body)
        body_html = paragraphs_to_html(paras)
        nav_html = chapter_nav(i, chapters)
        page = page_template(title, chapters[i]["meta"], body_html, nav_html)
        out_path = OUT_DIR / chapters[i]["file"]
        out_path.write_text(page, encoding="utf-8")
        print(f"Wrote {out_path.name} ({len(body_html)} chars)")

    # Remove stale chapter files from the old 6-chapter fic
    for old in OUT_DIR.glob("chapter-*.html"):
        num = int(old.stem.split("-")[1])
        if num > len(chapters):
            old.unlink()
            print(f"Removed {old.name}")

    update_index(meta, chapters)
    print(f"Updated {INDEX_PATH.name}")


if __name__ == "__main__":
    main()
