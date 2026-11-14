"""대학 사서 채용공고 크롤러 (2단계 필터, v2)
1) 목록에서 제목에 채용/모집/초빙이 있는 글만 후보로 선택
2) 후보의 행 텍스트에 사서 관련 표현이 있으면 채택,
   없으면 상세 페이지 본문(메뉴/하단 제거)을 열어 확인 (check_detail: true 인 학교만)
"""
import json, re, sys, time, datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

VERSION = 2
RECRUIT = ["채용", "모집", "초빙"]
EXCLUDE_TITLE = ["결과", "발표", "합격", "친인척", "현황", "계획 사전", "입찰", "교섭", "근로학생"]
PAT = re.compile(r"사서|도서관\s*(직원|근무|업무|운영|사무)|학술정보(지원)?팀|학술정보처")
NOISE_SEL = ("nav,header,footer,aside,script,style,"
             "[id*=gnb],[id*=snb],[id*=menu],[id*=footer],"
             "[class*=gnb],[class*=snb],[class*=menu],[class*=footer],[class*=sitemap]")
OUT = "docs/jobs.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (library-job-watcher)"}
KST = datetime.timezone(datetime.timedelta(hours=9))
MAX_DETAIL = 25
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
    time.sleep(0.7)
    return r.text


def find_date(text):
    m = re.search(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    return f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}" if m else ""


def body_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select(NOISE_SEL):
        tag.decompose()
    return soup.get_text(" ")


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
                title = " · ".join(c for c in cells[1:6] if c)
            url = page_url if (not href or href.startswith(("javascript", "#"))) else urljoin(page_url, href)

            reason = ""
            if PAT.search(row_text):
                reason = "목록"
            elif src.get("check_detail") and url != page_url:
                key = url + title
                if key in old:
                    items.append(old[key])
                    continue
                if detail_n < MAX_DETAIL:
                    detail_n += 1
                    try:
                        if PAT.search(body_text(fetch(url))):
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
        prev = json.load(open(OUT, encoding="utf-8"))
        old = {j["url"] + j["title"]: j for j in prev["jobs"]} if prev.get("v") == VERSION else {}
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
    for k, v in old.items():
        if k not in jobs and (now.date() - datetime.date.fromisoformat(v["first_seen"])).days <= 30:
            jobs[k] = v
    result = sorted(jobs.values(), key=lambda j: (j["date"] or j["first_seen"]), reverse=True)
    json.dump({"v": VERSION, "updated": now.strftime("%Y-%m-%d %H:%M KST"),
               "errors": errors, "jobs": result},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(result)}건 저장, 오류 {len(errors)}건")
    for e in errors:
        print(" -", e)


if __name__ == "__main__":
    sys.exit(main())
