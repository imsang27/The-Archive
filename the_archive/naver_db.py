"""네이버 게임 라운지 DB(캐릭터·학생)에서 공식 소개문을 가져온다.

라운지 DB 페이지는 자바스크립트로 그려지므로, 설치된 Chrome을 Playwright로 띄워 페이지를 연 뒤
그 페이지가 받아 오는 것과 같은 공개 데이터(로그인 불필요)를 읽는다.
- game.naver.com robots.txt: 일반 수집 허용 (네이버 검색 로봇만 /lounge/ 제외)
- comm-api.game.naver.com: robots.txt 없음
- apis.naver.com(댓글)은 robots.txt가 수집을 금지하므로 쓰지 않는다.
"""

from __future__ import annotations

import datetime as dt
import html as htmlmod
import json
import re
import time
from pathlib import Path

from .model import Source

LOUNGE = "https://game.naver.com/lounge/"
API = "https://comm-api.game.naver.com/nng_main/v1"
PAGE_SIZE = 30
INDEX_TTL_DAYS = 7
REQUEST_DELAY = 0.5


class NaverDBError(RuntimeError):
    pass


def _norm_name(s: str) -> str:
    return re.sub(r"[\s·・]", "", s)


def description_to_lines(desc: str) -> list[str]:
    t = re.sub(r"<br\s*/?>", "\n", desc or "", flags=re.I)
    t = htmlmod.unescape(re.sub(r"<[^>]+>", "", t))
    return [line.strip() for line in t.split("\n") if line.strip()]


class NaverLoungeDB:
    """라운지 하나의 DB. with 문으로 쓰면 브라우저를 한 번만 띄운다."""

    def __init__(self, lounge: str, cache_dir: Path | None = None, headless: bool = True):
        self.lounge = lounge
        self.cache_dir = cache_dir
        self.headless = headless
        self._pw = self._browser = self._page = None
        self._game = None  # (gameId, dataType)
        self.official = False  # 게임사가 운영하는 "공식" 라운지인지

    # --- 브라우저 ---
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _ensure(self):
        if self._page is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise NaverDBError("playwright가 없습니다 (pip install playwright)") from exc
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(channel="chrome", headless=self.headless)
        except Exception as exc:
            self.close()
            raise NaverDBError(f"설치된 Chrome을 열지 못했습니다: {exc}") from exc
        self._page = self._browser.new_page(locale="ko-KR")
        self._page.goto(f"{LOUNGE}{self.lounge}/db", wait_until="domcontentloaded", timeout=60000)
        self._page.wait_for_timeout(2000)

    def close(self):
        for obj, meth in ((self._browser, "close"), (self._pw, "stop")):
            if obj is not None:
                try:
                    getattr(obj, meth)()
                except Exception:
                    pass
        self._pw = self._browser = self._page = None

    def _get(self, url: str) -> dict:
        self._ensure()
        time.sleep(REQUEST_DELAY)
        resp = self._page.request.get(url, headers={"Referer": f"{LOUNGE}{self.lounge}/db"})
        if not resp.ok:
            raise NaverDBError(f"HTTP {resp.status}: {url}")
        return resp.json()

    # --- 데이터 ---
    def game(self) -> tuple[str, str]:
        """(gameId, 캐릭터 DB의 dataType)."""
        if self._game is None:
            info = self._get(f"{API}/lounge/info/{self.lounge}")
            content = info.get("content") or info
            game_id = content.get("gameId")
            self.official = str(content.get("officialLounge")).lower() in ("true", "y", "yes", "1")
            cats = self._get(f"{API}/game/category/{game_id}?mid=db").get("result", [])
            cat = next((c for c in cats if c.get("categoryType") == "캐릭터"), None)
            if not game_id or not cat:
                raise NaverDBError(f"{self.lounge}: 캐릭터 DB를 찾지 못했습니다")
            self._game = (game_id, cat["dataType"])
        return self._game

    def _index_path(self) -> Path | None:
        return self.cache_dir / f"naver_db_{self.lounge}.json" if self.cache_dir else None

    def index(self, refresh: bool = False) -> dict[str, str]:
        """캐릭터 이름 → objectId. 7일 동안 캐시한다."""
        path = self._index_path()
        if path and path.exists() and not refresh:
            data = json.loads(path.read_text(encoding="utf-8"))
            saved = dt.date.fromisoformat(data.get("saved", "2000-01-01"))
            if (dt.date.today() - saved).days <= INDEX_TTL_DAYS:
                return data["items"]
        game_id, data_type = self.game()
        items: dict[str, str] = {}
        offset, total = 0, None
        while total is None or offset < total:
            res = self._get(f"{API}/game/db/character/{game_id}/dataType/{data_type}"
                            f"?order=ranking&offset={offset}&limit={PAGE_SIZE}")
            total = res.get("totalCount") or 0
            chars = (res.get("result") or {}).get("character") or []
            if not chars:
                break
            for c in chars:
                items[c["name"]] = c["objectId"]
            offset += PAGE_SIZE
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"saved": dt.date.today().isoformat(), "items": items},
                                       ensure_ascii=False, indent=1), encoding="utf-8")
        return items

    def find(self, name: str, aliases: list[str] | None = None) -> str | None:
        idx = self.index()
        cands = [name] + list(aliases or [])
        norm = {_norm_name(k): v for k, v in idx.items()}
        for c in cands:  # 정확히 같은 이름 (띄어쓰기·가운뎃점 무시)
            if _norm_name(c) in norm:
                return norm[_norm_name(c)]
        for c in cands:  # "시로코" → "스나오오카미 시로코"처럼 성이 붙은 경우
            hits = [v for k, v in idx.items() if k.split()[-1] == c.strip()]
            if len(hits) == 1:
                return hits[0]
        return None

    def source(self, name: str, aliases: list[str] | None = None) -> Source | None:
        object_id = self.find(name, aliases)
        if not object_id:
            return None
        game_id, data_type = self.game()
        detail = self._get(f"{API}/game/db/character/objectId/{object_id}")
        intro = detail.get("intro") or {}
        lines = description_to_lines(intro.get("description", ""))
        if not lines:
            return None
        title = intro.get("name") or name
        return Source(
            key="naver_db",
            label="네이버 게임 공식 라운지 DB" if self.official else "네이버 게임 라운지 DB",
            title=title,
            url=f"{LOUNGE}{self.lounge}/db/{data_type}/{object_id}",
            date="",
            grade=1 if self.official else 2,  # 공식 라운지의 공식 소개문만 1차 출처로 본다
            text="\n".join(lines),
            sections={"공식 소개": lines},
            note="공식 소개문",
        )
