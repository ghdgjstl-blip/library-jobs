# 대전권 대학 사서 채용공고 모음

## 구성
- `crawler.py` : 게시판에서 '사서/도서관' 관련 공고 수집 → `docs/jobs.json`
- `sources.json` : 대학별 게시판 목록 URL (**직접 채워야 함**)
- `docs/index.html` : 결과 페이지
- `.github/workflows/crawl.yml` : 하루 2번 자동 실행

## 설정 순서
1. 각 대학 홈페이지에서 **채용/공지 게시판 목록 URL**을 찾아 `sources.json`의 `urls`에 넣기
   (대학 본부 '채용공고' 게시판 + 도서관 '공지사항' 둘 다 넣는 것을 권장)
   필요하면 `"selector": "table.board a"` 처럼 링크 CSS 선택자 지정 가능
2. 로컬 테스트: `pip install -r requirements.txt && python crawler.py`
3. GitHub 저장소에 올리고 Settings → Pages → Branch `main` / `/docs` 선택
4. Actions 탭에서 `crawl`을 한 번 수동 실행(Run workflow)

## 문제 해결
- 링크가 `javascript:view(123)` 형태면 URL을 알 수 없어 목록 페이지로 연결됩니다.
  → 해당 사이트의 실제 상세 URL 규칙을 알려주시면 코드에 규칙 추가 가능
- 결과가 비어 있으면 게시판이 JS로 렌더링되는 경우일 수 있습니다(내부 API 주소 확인 필요)
- 일부 대학은 크롤링 시 robots.txt/이용약관을 확인하고 요청 빈도를 낮게 유지하세요
