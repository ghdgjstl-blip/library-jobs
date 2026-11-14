"""대학 사서 채용공고 크롤러 (2단계 필터)
1) 목록에서 제목에 채용 관련 단어(채용/모집/초빙/공고)가 있는 글만 후보로 선택
2) 후보의 '행 전체 텍스트'(예: 근무부서 칸)에 사서 키워드가 있으면 바로 채택,
   없으면 상세 페이지 본문을 열어 키워드를 확인 (check_detail: true 인 학교만)
"""
import json, re, sys, time, datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

KEYWORDS = ["사서", "도서관", "학술정보", "정보서비스", "자료관리"]
RECRUIT = ["채용", "모집", "초빙", "공고"]
EXCLUDE_TITLE = ["결과", "발표", "합격", "친인척", "현황", "계획 사전"]   # 제목에 있으면 제외
OUT = "docs/jobs.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (library-job-watcher)"}
KST = datetime.timezone(datetime.timedelta(hours=9))
MAX_DETAIL = 25          # 학교당 상세 페이지 최대 조회 수
_cache = {}


def fetch(url):
    if url in _cache:
        return _cache[url]
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except requests.exceptions.SSLError:
        r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    _cache[url] = r.text
    time.sleep(0.7)      # 서버 부담 줄이기
    return r.text


def find_date(text):
    m = re.search(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    return f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}" if m else ""


def has_kw(text):
    return any(k in text for k in KEYWORDS)


def crawl(src, old):
    items, detail_n = [], 0
    for page_url in src["urls"]:
        soup = BeautifulSoup(fetch(page_url), "html.parser")
        seen_rows = set()
        for a in soup.select(src.get("selector", "a")):
            href = a.get("href", "")
            title = " ".join(a.get_text(" ", strip=True).split())
            row = a.find_parent("tr") or a.find_parent("li") or a.parent
            row_text = " ".join(row.get_text(" ", strip=True).split()) if row else title
            if not title or id(row) in seen_rows:
                continue
            if not any(w in row_text for w in RECRUIT) or any(x in title for x in EXCLUDE_TITLE):
                continue
            seen_rows.add(id(row))

            if src.get("title_from_row") and row is not None and row.name == "tr":
                cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
                title = " · ".join(c for c in cells[1:6] if c)       # 순번 제외 앞쪽 칸
            url = page_url if href.startswith(("javascript", "#")) or not href else urljoin(page_url, href)
            reason = ""
            if has_kw(row_text):
                reason = "목록"
            elif src.get("check_detail") and url != page_url and detail_n < MAX_DETAIL:
                key = url + title
                if key in old:                       # 이미 판정한 글은 재조회 안 함
                    items.append(old[key]); continue
                detail_n += 1
                try:
                    body = BeautifulSoup(fetch(url), "html.parser").get_text(" ")
                    if has_kw(body):
                        reason = "본문"
                except Exception:
                    pass
            if reason:
                items.append({"school": src["name"], "title": title, "url": url,
                              "date": find_date(row_text), "reason": reason})
    return items


def main():
    sources = json.load(open("sources.json", encoding="utf-8"))
    try:
        old = {j["url"] + j["title"]: j for j in json.load(open(OUT, encoding="utf-8"))["jobs"]}
    except Exception:
        old = {}
    now = datetime.datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    jobs, errors = {}, []
    for src in sources:
        if not src.get("urls"):
            errors.append(f"{src['name']}: URL 미설정")
            continue
        try:
            for it in crawl(src, old):
                key = it["url"] + it["title"]
                it["first_seen"] = old.get(key, {}).get("first_seen", today)
                jobs[key] = it
        except Exception as e:
            errors.append(f"{src['name']}: {e}")
    for k, v in old.items():      # 목록에서 밀려난 공고도 30일 유지
        if k not in jobs and (now.date() - datetime.date.fromisoformat(v["first_seen"])).days <= 30:
            jobs[k] = v
    result = sorted(jobs.values(), key=lambda j: (j["date"] or j["first_seen"]), reverse=True)
    json.dump({"updated": now.strftime("%Y-%m-%d %H:%M KST"), "errors": errors, "jobs": result},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(result)}건 저장, 오류 {len(errors)}건")
    for e in errors:
        print(" -", e)


if __name__ == "__main__":
    sys.exit(main())
