"""나무위키 문서를 가져와 텍스트와 구조(프로필, 섹션)로 정리한다."""

from __future__ import annotations

import hashlib
import html as htmlmod
import re
import time
import urllib.parse
from pathlib import Path

from .model import Page, Source
from .works import Work

BASE = "https://namu.wiki/w/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
REQUEST_DELAY = 1.0  # 요청 사이 대기 시간(초). 위키에 부담을 주지 않기 위해 둔다.

HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\. (.+?)\[편집\]$")
FOOTNOTE_RE = re.compile(r"\[\d+\]")
DATE_RE = re.compile(r"최근 수정 시각: (\d{4}-\d\d-\d\d)")
# 프로필 표에서 "키" 다음 줄에 "값"이 오는 항목 (블루 아카이브 등)
PROFILE_KEYS = ["이명", "소속 학원", "동아리", "나이", "생일", "키", "취미", "디자인", "일러스트",
                "성별", "출생", "세력", "속성", "무기", "소속", "종족", "신장"]

_last_request = 0.0


class FetchError(RuntimeError):
    pass


def page_url(title: str) -> str:
    return BASE + urllib.parse.quote(title)


def _cache_path(cache_dir: Path, title: str) -> Path:
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{digest}.html"


def fetch_html(title: str, cache_dir: Path | None = None, refresh: bool = False) -> str:
    """문서 HTML을 가져온다. cache_dir가 있으면 캐시를 먼저 쓴다."""
    global _last_request
    if cache_dir is not None:
        path = _cache_path(cache_dir, title)
        if path.exists() and not refresh:
            return path.read_text(encoding="utf-8")
    import requests  # 네트워크가 필요할 때만 불러온다

    wait = REQUEST_DELAY - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = requests.get(page_url(title), headers={"User-Agent": USER_AGENT}, timeout=30)
    except requests.RequestException as exc:  # 네트워크 오류
        raise FetchError(f"{title}: 요청 실패 ({exc})") from exc
    finally:
        _last_request = time.monotonic()
    if resp.status_code == 404:
        raise FetchError(f"{title}: 문서가 없습니다 (404)")
    if resp.status_code != 200:
        raise FetchError(f"{title}: HTTP {resp.status_code}")
    resp.encoding = "utf-8"
    text = resp.text
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache_path(cache_dir, title).write_text(text, encoding="utf-8")
    return text


def html_to_lines(html: str) -> list[str]:
    """스크립트와 스타일을 지우고, 블록 단위로 줄을 나눈 텍스트를 돌려준다."""
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S | re.I)
    t = re.sub(r"<(br|/p|/div|/li|/h\d|/tr|/td|/th)[^>]*>", "\n", t, flags=re.I)
    t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t ]+", " ", t)
    return [line.strip() for line in t.split("\n") if line.strip()]


def _clean(value: str) -> str:
    return FOOTNOTE_RE.sub("", value).strip()


def parse_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            current = m.group(2).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def _first_heading_index(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        if HEADING_RE.match(line):
            return i
    return len(lines)


def parse_profile(lines: list[str]) -> tuple[dict[str, str], list[str], list[str]]:
    """본문 첫 헤딩 앞의 프로필 영역에서 (프로필, 이름들, 성우)를 뽑는다."""
    head = lines[: _first_heading_index(lines)]
    # 목차 줄("1. 개요2. 인물 소개...")은 프로필 영역 끝을 알려준다
    end = next((i for i, l in enumerate(head) if re.match(r"^1\. \S.*2\. ", l)), len(head))
    start = max((i for i, l in enumerate(head[:end]) if l == "프로필"), default=0)
    block = head[start:end]

    profile: dict[str, str] = {}
    for line in block:  # "키: 값" 형식 (명조 등)
        m = re.match(r"^([가-힣 ]{1,10}): (.+)$", line)
        if m and m.group(1) not in profile:
            profile[m.group(1).strip()] = _clean(m.group(2))
    for i, line in enumerate(block[:-1]):  # "키" 다음 줄 "값" 형식 (블루 아카이브 등)
        key = _clean(line)
        if key in PROFILE_KEYS and key not in profile:
            nxt = block[i + 1]
            if nxt not in PROFILE_KEYS and not nxt.startswith("["):
                profile[key] = _clean(nxt)

    names: list[str] = []
    han = next((l for l in block if re.search(r" \| [A-Z][a-z]", l) and len(l) < 100), None)
    if han:  # 명조: "白芷(báizhǐ) | 白芷(ビャクシ) | Baizhi"
        parts = [p.strip() for p in han.split("|")]
        names = [re.sub(r"\(.*?\)", "", parts[0]).strip(), parts[-1]]
    elif "이름" in block:  # 블루 아카이브: "이름" 아래 여러 줄
        i = block.index("이름")
        for l in block[i + 1:i + 6]:
            if _clean(l) in PROFILE_KEYS:
                break
            names.append(re.sub(r"\(.*?\)", "", l).strip())
        names = names[1:]  # 첫 줄은 한국어 이름

    voices: list[str] = []
    for key in ("성우 정보", "성우"):
        idx = next((i for i, l in enumerate(block) if _clean(l) == key), None)
        if idx is not None:
            for l in block[idx + 1:idx + 6]:
                if _clean(l) in PROFILE_KEYS or HEADING_RE.match(l):
                    break
                voices.append(_clean(l))
            break
    return profile, [n for n in names if n], [v for v in voices if v]


def canonical_title(html: str, fallback: str) -> str:
    """리다이렉트를 거친 경우에도 실제 문서 제목을 <title>에서 읽는다."""
    m = re.search(r"<title>(.*?) - 나무위키</title>", html, flags=re.S)
    return htmlmod.unescape(m.group(1)).strip() if m else fallback


def parse_page(html: str, title: str) -> Page:
    title = canonical_title(html, title)
    lines = html_to_lines(html)
    text = "\n".join(lines)
    m = DATE_RE.search(text)
    profile, names, voices = parse_profile(lines)
    return Page(
        title=title,
        url=page_url(title),
        source_date=m.group(1) if m else "",
        text=text,
        lines=lines,
        profile=profile,
        names=names,
        voice_actors=voices,
        sections=parse_sections(lines),
    )


def find_page(name: str, work: Work, cache_dir: Path | None = None, refresh: bool = False) -> Page:
    """작품 구분자가 붙은 문서부터 찾고, 없으면 이름만으로 찾는다."""
    errors = []
    for title in (f"{name}({work.namu_suffix})", name):
        try:
            html = fetch_html(title, cache_dir, refresh)
        except FetchError as exc:
            errors.append(str(exc))
            continue
        page = parse_page(html, title)
        if work.keyword in page.text and page.sections:
            return page
        errors.append(f"{title}: {work.title} 문서가 아닙니다")
    raise FetchError("; ".join(errors))


def to_source(page: Page) -> Source:
    """나무위키 문서를 출처 목록에 넣을 형태로 바꾼다."""
    return Source(key="namu", label="나무위키", title=page.title, url=page.url, date=page.source_date,
                  grade=2, text=page.text, sections=page.sections)
