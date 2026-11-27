"""Blue Archive Wiki(bluearchive.wiki, 영문)에서 학생 문서를 가져온다.

MediaWiki API(action=parse)로 렌더링된 본문을 받는다. 브라우저가 필요 없다.
"""

from __future__ import annotations

import re
import time
import urllib.parse

from .model import Source
from .namu import USER_AGENT, html_to_lines

API = "https://bluearchive.wiki/w/api.php"
WIKI = "https://bluearchive.wiki/wiki/"
REQUEST_DELAY = 1.0
STOP = ("How to Obtain", "Character Details", "Skills", "Resources")


class BAWikiError(RuntimeError):
    pass


def title_candidates(names: list[str]) -> list[str]:
    """별칭 중 로마자 이름에서 문서 제목 후보를 만든다. "Sunaookami Shiroko" → "Shiroko"."""
    out: list[str] = []
    for n in names:
        if re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", n.strip()):
            parts = n.split()
            for c in (parts[-1], n.strip()):
                if c not in out:
                    out.append(c)
    return out


def _get(params: dict) -> dict:
    import requests

    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(API, params={**params, "format": "json"},
                            headers={"User-Agent": USER_AGENT}, timeout=30)
    except requests.RequestException as exc:
        raise BAWikiError(f"요청 실패: {exc}") from exc
    if resp.status_code != 200:
        raise BAWikiError(f"HTTP {resp.status_code}")
    return resp.json()


def _sections(lines: list[str]) -> dict[str, list[str]]:
    """첫 문단(소개)과 Background(공식 소개·관계) 부분만 고른다."""
    lead = []
    for line in lines:
        if line in ("Background", "Contents") or line.startswith("Contents"):
            break
        if len(line) > 60 and line.endswith("."):
            lead.append(line)
    bg: list[str] = []
    if "Background" in lines:
        for line in lines[lines.index("Background") + 1:]:
            if line in STOP:
                break
            bg.append(line)
    out = {}
    if lead:
        out["Introduction"] = lead
    if bg:
        out["Background"] = bg
    return out


def fetch(names: list[str]) -> Source | None:
    for title in title_candidates(names):
        data = _get({"action": "parse", "page": title, "prop": "text|displaytitle", "redirects": 1})
        if "error" in data:
            continue
        html = data["parse"]["text"]["*"]
        lines = [l for l in html_to_lines(html) if l not in ("[edit]", "EnglishJapanese")]
        sections = _sections(lines)
        if not sections:
            continue
        page = data["parse"]["title"]
        rev = _get({"action": "query", "prop": "revisions", "titles": page, "rvprop": "timestamp"})
        pages = rev.get("query", {}).get("pages", {})
        stamp = next(iter(pages.values()), {}).get("revisions", [{}])[0].get("timestamp", "")
        return Source(
            key="bawiki",
            label="Blue Archive Wiki",
            title=page,
            url=WIKI + urllib.parse.quote(page.replace(" ", "_")),
            date=stamp[:10],
            grade=2,
            text="\n".join(lines),
            sections=sections,
        )
    return None
