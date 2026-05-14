"""
일일 트렌드 수집 스크립트
- GeekNews (news.hada.io)
- GitHub Trending
- Hugging Face Papers

JSON 파일로 news/data/YYYY-MM-DD.json 저장
"""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "news" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (compatible; SMin0309-NewsBot/1.0)"}


def http_get(url: str, max_redirects: int = 5) -> str:
    """308 등 모든 리다이렉트 수동 처리"""
    from urllib.error import HTTPError
    for _ in range(max_redirects):
        req = Request(url, headers=UA)
        try:
            with urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="ignore")
        except HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                new = e.headers.get("Location")
                if not new:
                    raise
                if new.startswith("/"):
                    from urllib.parse import urlparse
                    p = urlparse(url)
                    new = f"{p.scheme}://{p.netloc}{new}"
                url = new
                continue
            raise
    raise RuntimeError(f"too many redirects: {url}")


def fetch_geeknews(limit: int = 7) -> list[dict]:
    """news.hada.io 메인 페이지의 인기글 추출"""
    html = http_get("https://news.hada.io")
    items = []
    # 제목 + 외부링크 + 토픽ID + 요약을 한 번에
    pattern = re.compile(
        r"topictitle[^>]*>.*?<a href='([^']+)'[^>]*><h1>([^<]+)</h1></a>"
        r".*?topicdesc.*?<a href='topic\?id=(\d+)'[^>]*>([^<]+)</a>",
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        ext_url = m.group(1).strip()
        title = m.group(2).strip().replace("&quot;", '"').replace("&amp;", "&")
        topic_id = m.group(3).strip()
        summary = m.group(4).strip().rstrip(".").rstrip(" ").rstrip("…")
        # GeekNews 토론 페이지 URL을 우선 사용 (한국어 코멘트가 있어 가치 ↑)
        gn_url = f"https://news.hada.io/topic?id={topic_id}"
        items.append({
            "title": title,
            "url": gn_url,
            "external_url": ext_url,
            "summary": summary,
        })
        if len(items) >= limit:
            break
    return items


def fetch_github_trending(limit: int = 5) -> list[dict]:
    """github.com/trending 상위 레포"""
    html = http_get("https://github.com/trending")
    items = []
    # <h2 class="h3 lh-condensed"><a href="/owner/repo" ...>
    repo_pattern = re.compile(
        r'<h2 class="h3 lh-condensed">\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    # 언어: <span itemprop="programmingLanguage">Python</span>
    lang_pattern = re.compile(
        r'<span itemprop="programmingLanguage">([^<]+)</span>'
    )
    # 설명: <p class="col-9 color-fg-muted my-1 pr-4">설명</p>
    desc_pattern = re.compile(
        r'<p class="col-9 color-fg-muted my-1 pr-4">\s*([^<]+)\s*</p>',
        re.DOTALL,
    )

    repos = repo_pattern.findall(html)
    langs = lang_pattern.findall(html)
    descs = desc_pattern.findall(html)

    for i, (path, _raw_name) in enumerate(repos[:limit]):
        path = path.strip().lstrip("/")
        # 항상 path에서 owner/repo 추출 (HTML 변경에 강함)
        name = path.replace("/", " / ")
        url = "https://github.com/" + path
        lang = langs[i].strip() if i < len(langs) else ""
        desc = descs[i].strip() if i < len(descs) else ""
        items.append({"title": name, "url": url, "lang": lang, "summary": desc})
    return items


def strip_html(s: str) -> str:
    """RSS description의 HTML 태그 제거"""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    # HTML 엔티티 처리
    s = s.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    s = s.replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    return s


TECH_KEYWORDS = [
    # AI / ML
    "AI", "인공지능", "머신러닝", "딥러닝", "LLM", "GPT", "Claude", "Gemini",
    "Llama", "생성형", "챗봇", "에이전트", "Agent", "RAG", "임베딩",
    # 개발
    "개발", "개발자", "코딩", "프로그래밍", "프로그래머", "엔지니어",
    "백엔드", "프론트엔드", "풀스택", "DevOps", "오픈소스",
    # 기술 일반
    "기술", "테크", "IT", "소프트웨어", "SW", "플랫폼",
    "클라우드", "AWS", "Azure", "GCP", "쿠버네티스", "Kubernetes", "Docker",
    "데이터", "데이터베이스", "DB", "API", "SaaS",
    "보안", "사이버", "해킹", "취약점",
    # 스타트업/산업
    "스타트업", "유니콘", "투자", "IPO",
    # 디바이스/네트워크
    "모바일", "앱", "iOS", "안드로이드", "Android", "웹",
    "5G", "6G", "통신", "네트워크", "서버",
    # 칩/하드웨어
    "반도체", "GPU", "NPU", "엔비디아", "NVIDIA", "TSMC", "삼성전자", "SK하이닉스",
    # 회사/제품
    "구글", "Google", "애플", "Apple", "메타", "Meta", "MS", "마이크로소프트",
    "OpenAI", "Anthropic", "네이버", "카카오",
]


CATEGORIES = {
    "AI": [
        "ai", "인공지능", "머신러닝", "딥러닝", "llm", "gpt", "claude", "gemini",
        "llama", "생성형", "챗봇", "에이전트", "agent", "rag", "임베딩", "프롬프트",
        "openai", "anthropic", "허깅페이스", "huggingface", "모델", "파인튜닝",
        "엔비디아", "nvidia",  # AI 가속기 맥락 많음
    ],
    "Backend": [
        "백엔드", "backend", "api", "서버", "데이터베이스", "데이터 베이스",
        "rest", "graphql", "마이크로서비스", "msa", "spring", "django",
        "node.js", "nodejs", "go", "rust", "오라클", "oracle", "mysql", "postgresql",
        "redis", "kafka", "neo4j", "mongodb",
    ],
    "Cloud": [
        "클라우드", "cloud", "aws", "azure", "gcp", "docker", "kubernetes",
        "쿠버네티스", "devops", "ci/cd", "젠킨스", "jenkins", "terraform",
        "saas", "paas", "iaas", "오케스트레이터",
    ],
    "Security": [
        "보안", "사이버", "해킹", "취약점", "랜섬웨어", "피싱", "암호화",
        "방화벽", "악성코드", "유출", "침해",
    ],
    "Mobile": [
        "모바일", "mobile", "ios", "안드로이드", "android", "앱", "스마트폰",
        "swift", "kotlin", "flutter", "react native",
    ],
    "Hardware": [
        "반도체", "gpu", "npu", "칩", "프로세서", "삼성전자", "sk하이닉스",
        "tsmc", "asml", "메모리", "d램", "낸드",
    ],
    "Industry": [
        "스타트업", "유니콘", "투자", "ipo", "인수", "합병", "매출", "출시",
        "런칭", "사업", "협력", "맞손", "ceo", "대표", "신사업",
    ],
}


def categorize(item: dict) -> str:
    """제목+요약 기반 카테고리 1개 결정. 매치 점수 최대인 카테고리."""
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    scores = {}
    for cat, keywords in CATEGORIES.items():
        scores[cat] = sum(1 for k in keywords if k in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Etc"


def categorize_all(sources: list[dict]) -> list[dict]:
    for src in sources:
        for item in src.get("items", []):
            item["category"] = categorize(item)
    return sources


def filter_by_keyword(items: list[dict], keywords: list[str], top_n: int) -> list[dict]:
    """제목 + 요약에 키워드가 포함된 아이템만 통과. 매치 점수 순 정렬."""
    kw_lower = [k.lower() for k in keywords]
    scored = []
    for item in items:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        score = sum(1 for k in kw_lower if k in text)
        if score > 0:
            scored.append((score, item))
    # 점수 내림차순, 동점이면 원본 순서 유지
    scored.sort(key=lambda x: -x[0])
    return [it for _, it in scored[:top_n]]


def fetch_rss(url: str, limit: int = 5, summary_len: int = 120) -> list[dict]:
    """일반 RSS 2.0 / Atom 파서"""
    raw = http_get(url)
    items = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        # BOM이나 인코딩 문제 시 정리 후 재시도
        raw = raw.lstrip("﻿")
        raw = re.sub(r"^[^<]+", "", raw)
        root = ET.fromstring(raw)

    # RSS 2.0
    entries = root.findall(".//item")
    if entries:
        for e in entries[:limit]:
            title = (e.findtext("title") or "").strip()
            link = (e.findtext("link") or "").strip()
            desc = strip_html(e.findtext("description") or "")
            if len(desc) > summary_len:
                desc = desc[:summary_len].rstrip() + "…"
            if title and link:
                items.append({"title": title, "url": link, "summary": desc})
        return items

    # Atom
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in root.findall("a:entry", ns)[:limit]:
        title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
        link_el = e.find("a:link", ns)
        link = (link_el.get("href") if link_el is not None else "").strip()
        desc = strip_html(e.findtext("a:summary", default="", namespaces=ns) or "")
        if len(desc) > summary_len:
            desc = desc[:summary_len].rstrip() + "…"
        if title and link:
            items.append({"title": title, "url": link, "summary": desc})
    return items


def fetch_hf_papers(limit: int = 5) -> list[dict]:
    """huggingface.co/papers 인기 논문"""
    html = http_get("https://huggingface.co/papers")
    items = []
    # <h3>...<a href="/papers/2511.xxxxx">제목</a>
    pattern = re.compile(
        r'<h3[^>]*>\s*<a[^>]*href="(/papers/[^"]+)"[^>]*>\s*([^<]+)\s*</a>',
        re.DOTALL,
    )
    seen = set()
    for m in pattern.finditer(html):
        path, title = m.group(1).strip(), m.group(2).strip()
        url = "https://huggingface.co" + path
        if url in seen:
            continue
        seen.add(url)
        items.append({"title": title, "url": url, "summary": ""})
        if len(items) >= limit:
            break
    return items


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[fetch] collecting brief for {today}")

    sources = []
    try:
        items = fetch_geeknews()
        print(f"  GeekNews: {len(items)} items")
        sources.append({"name": "GeekNews 인기글", "items": items})
    except Exception as e:
        print(f"  GeekNews FAILED: {e}")

    rss_sources = [
        # (이름, URL, 표시할 건수, 키워드 필터 적용 여부)
        ("요즘IT", "https://yozm.wishket.com/magazine/feed/", 5, False),
        ("AI타임스", "https://www.aitimes.com/rss/allArticle.xml", 5, True),
        ("ZDNet Korea", "https://feeds.feedburner.com/zdkorea", 5, True),
    ]
    for name, url, limit, do_filter in rss_sources:
        try:
            # 필터링 시 더 많이 가져와서 점수 매긴 뒤 상위 N개 선택
            raw_limit = 30 if do_filter else limit
            items = fetch_rss(url, limit=raw_limit)
            if do_filter:
                items = filter_by_keyword(items, TECH_KEYWORDS, top_n=limit)
            print(f"  {name}: {len(items)} items")
            if items:
                sources.append({"name": name, "items": items})
        except Exception as e:
            print(f"  {name} FAILED: {e}")

    brief = {
        "date": today,
        "label": "오늘의 브리프",
        "pick": "",  # 나중에 LLM 또는 수동 작성
        "sources": sources,
    }

    sources = categorize_all(sources)

    out = DATA_DIR / f"{today}.json"
    out.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fetch] saved -> {out}")


if __name__ == "__main__":
    main()
