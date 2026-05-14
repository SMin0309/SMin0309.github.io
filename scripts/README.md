# News Automation

매일 자동으로 개발/AI 트렌드를 수집해서 `news/index.html`에 추가하는 파이프라인.

## 구조

```
scripts/
├── fetch.py       데이터 수집 (GeekNews · GitHub Trending · HF Papers)
└── generate.py    JSON → HTML 페이지 갱신

news/
├── data/          일별 JSON (YYYY-MM-DD.json)
└── index.html     자동 생성

.github/workflows/
└── daily-brief.yml  매일 09:00 KST 실행
```

## 흐름

```
[09:00 KST] GitHub Actions 트리거
  ↓
fetch.py    → news/data/2026-05-15.json 생성
  ↓
generate.py → news/index.html 재생성 (전체 JSON 합쳐서)
  ↓
git commit & push (자동)
```

## 로컬에서 수동 실행

```bash
python scripts/fetch.py     # 오늘 자 데이터 수집
python scripts/generate.py  # HTML 갱신
```

## "오늘의 Pick" 추가

`news/data/YYYY-MM-DD.json`의 `"pick"` 필드에 직접 작성한 뒤 `generate.py` 다시 실행:

```json
{
  "date": "2026-05-14",
  "pick": "<strong>legalQ</strong> 프로젝트가 눈에 띈다...",
  ...
}
```

## 주의

- GeekNews/HF Papers는 페이지 구조가 바뀌면 정규식 수정 필요
- GitHub Actions 무료 한도: 월 2000분 (이 작업은 회당 1분 미만)
- LLM 요약은 STEP 4에서 추가 예정 (Gemini API)
