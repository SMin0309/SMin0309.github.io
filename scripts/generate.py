"""
news/data/*.json → news/index.html 자동 생성
- 모든 JSON 브리프를 날짜 역순으로 페이지에 삽입
- 사이드바 아카이브도 자동 갱신
"""
import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "news" / "data"
HTML_PATH = ROOT / "news" / "index.html"


def render_item(idx: int, item: dict, source_name: str) -> str:
    n = f"{idx:02d}"
    title = escape(item.get("title", ""))
    url = item.get("url", "#")
    summary = escape(item.get("summary", ""))
    lang = item.get("lang", "")
    cat = item.get("category", "")

    lang_tag = f'<span class="lang">{escape(lang)}</span>' if lang else ""
    cat_tag = (
        f'<span class="cat cat-{cat.lower()}">{escape(cat)}</span>'
        if cat else ""
    )
    return (
        f'      <div class="item" data-cat="{escape(cat)}"><div class="num">{n}</div><div class="body">\n'
        f'        <div class="title"><a href="{escape(url)}" target="_blank">{lang_tag}{title}</a> {cat_tag}</div>\n'
        f'        <div class="summary">{summary}</div>\n'
        f"      </div></div>\n"
    )


def render_brief(brief: dict) -> str:
    date = brief["date"]
    label = escape(brief.get("label", "오늘의 브리프"))
    pick = brief.get("pick", "").strip()
    sources = brief.get("sources", [])

    # 이 브리프에 등장하는 카테고리 수집
    cats = []
    for src in sources:
        for it in src.get("items", []):
            c = it.get("category", "")
            if c and c not in cats:
                cats.append(c)
    # 표시 순서 고정
    order = ["AI", "Backend", "Cloud", "Security", "Mobile", "Hardware", "Industry", "Etc"]
    cats.sort(key=lambda x: order.index(x) if x in order else 999)

    parts = []
    parts.append(f'  <article class="brief" id="brief-{date}">\n')
    parts.append('    <div class="brief-date">\n')
    parts.append(f'      <span class="date">{date.replace("-", ".")}</span>\n')
    parts.append(f'      <span class="label">{label}</span>\n')
    parts.append("    </div>\n")
    parts.append('    <div class="brief-divider"></div>\n\n')

    # 카테고리 필터
    if cats:
        parts.append(f'    <div class="cat-filter" data-brief="{date}">\n')
        parts.append('      <span class="label">// filter</span>\n')
        parts.append(f'      <button class="cat-btn active" onclick="filterCat(this,\'{date}\',\'all\')">All</button>\n')
        for c in cats:
            parts.append(f'      <button class="cat-btn" onclick="filterCat(this,\'{date}\',\'{c}\')">{c}</button>\n')
        parts.append('    </div>\n\n')

    if pick:
        parts.append(
            '    <div class="pick-box" style="margin-top:0;margin-bottom:32px;">\n'
            '      <div class="pick-label">오늘의 Pick</div>\n'
            f'      <div class="pick-text">{pick}</div>\n'
            "    </div>\n\n"
        )

    for src in sources:
        name = escape(src.get("name", ""))
        items = src.get("items", [])
        parts.append(f'    <div class="source">\n      <h2>{name}</h2>\n')
        for i, item in enumerate(items, start=1):
            parts.append(render_item(i, item, name))
        parts.append("    </div>\n\n")

    parts.append("  </article>\n")
    return "".join(parts)


def render_archive(briefs: list[dict]) -> str:
    """사이드바 아카이브 li 항목들"""
    lines = []
    for i, brief in enumerate(briefs):
        date = brief["date"]
        count = sum(len(s.get("items", [])) for s in brief.get("sources", []))
        cls = "current" if i == 0 else ""
        lines.append(
            f'      <li><a href="#brief-{date}" class="{cls}">{date.replace("-", ".")}'
            f'<span class="count">{count}</span></a></li>'
        )
    return "\n".join(lines)


def load_briefs() -> list[dict]:
    """데이터 디렉토리의 모든 브리프를 날짜 역순으로 로드"""
    files = sorted(DATA_DIR.glob("*.json"), reverse=True)
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def main():
    briefs = load_briefs()
    if not briefs:
        print("[generate] no briefs found, abort")
        return

    print(f"[generate] {len(briefs)} brief(s) loaded")

    html = HTML_PATH.read_text(encoding="utf-8")

    # 1. 사이드바 아카이브 갱신
    archive_html = render_archive(briefs)
    html = re.sub(
        r'(<aside class="archive-side">.*?<ul>\s*).*?(\s*</ul>)',
        lambda m: m.group(1) + "\n" + archive_html + "\n    " + m.group(2).lstrip(),
        html,
        count=1,
        flags=re.DOTALL,
    )

    # 2. 본문 article들 갱신 (첫 article 부터 마지막 article까지 통째로 교체)
    briefs_html = "\n".join(render_brief(b) for b in briefs)
    html = re.sub(
        r'(<header class="page-head">.*?</header>\s*\n)(.*?)(\n\s*<footer>)',
        lambda m: m.group(1) + "\n" + briefs_html + m.group(3),
        html,
        count=1,
        flags=re.DOTALL,
    )

    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"[generate] -> {HTML_PATH}")


if __name__ == "__main__":
    main()
