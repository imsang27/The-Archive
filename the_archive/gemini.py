"""Gemini API로 성격·외형·기타 특징을 요약한다.

AI가 쓴 줄마다 출처 원문 인용(quote)을 함께 받고, 인용이 페이지에 실제로 없으면 그 줄을 버린다.
API 키는 환경 변수 GEMINI_API_KEY(또는 GOOGLE_API_KEY)에서 읽는다.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

from .model import SECTIONS, Fact, Page, Source

DEFAULT_MODEL = "gemini-flash-latest"


def default_model() -> str:
    """환경 변수(.env 포함) GEMINI_MODEL이 있으면 그 값을 쓴다. 쉼표로 여러 개를 적을 수 있다."""
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def model_candidates(model: str | None = None) -> list[str]:
    """"a, b, c" 형식을 시도할 순서대로 나눈다. 비어 있으면 기본 모델 하나."""
    names = [m.strip() for m in (model or default_model()).split(",")]
    out: list[str] = []
    for n in names:
        if n and n not in out:
            out.append(n)
    return out or [DEFAULT_MODEL]


# 앞에 둔 섹션일수록 잘리지 않는다. 섹션마다 MAX_SECTION_CHARS까지만 넣는다.
SOURCE_SECTIONS = ("개요", "인물 소개", "공식 소개", "정보", "여담", "기타", "외모", "디자인", "캐릭터성")
MAX_SECTION_CHARS = 8000
MAX_SOURCE_CHARS = 40000
# "정보" 섹션에서 이 줄부터는 캐릭터 스토리(소설 같은 서술)라서 뺀다
STORY_MARKERS = ("캐릭터 스토리", "[ 캐릭터 스토리")

PROMPT = """너는 캐릭터 기록을 정리하는 아키비스트다. 아래 [출처 N]들은 캐릭터 "{name}"에 관한 자료다.
캐릭터 "{name}"의 성격, 외형, 기타 특징을 한국어로 정리하라.

규칙:
- [출처]에 있는 내용만 쓴다. 출처에 없는 지식, 추측, 평가를 더하지 않는다.
- 각 항목은 한 문장, "~다."로 끝나는 평서문으로 쓴다. 출처가 외국어여도 노트 문장은 한국어로 쓴다.
- section은 "성격", "외형", "기타" 중 하나다. 각 section은 최대 {limit}개.
- summary는 대조 체크리스트용 15자 안팎의 짧은 한국어 요약이다.
- source는 그 문장의 근거가 된 [출처 N]의 번호 N이다.
- quote는 그 [출처 N] 원문을 한 글자도 바꾸지 않고 그대로 옮긴 조각이다 (번역하지 않는다).
  8~60자, 각주 번호([1] 등)와 따옴표가 들어간 부분은 피한다.
- 같은 내용이 여러 출처에 있으면 (공식)이라고 표시된 출처를 source로 쓴다.
- "외형"에는 머리카락, 눈, 체형, 복장, 장신구, 성흔처럼 눈에 보이는 모습만 넣는다.
  성격이나 행동을 말하는 문장은 외형이 아니다.
- "{name}" 본인에 대한 서술만 쓴다. 다른 인물을 묘사하는 문장이나 대사는 쓰지 않는다.
- 줄거리 스포일러, 게임 성능·수치, 밈은 넣지 않는다.

{source}
"""

SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "section": {"type": "string", "enum": list(SECTIONS)},
            "text": {"type": "string"},
            "summary": {"type": "string"},
            "source": {"type": "integer"},
            "quote": {"type": "string"},
        },
        "required": ["section", "text", "summary", "source", "quote"],
    },
}


class GeminiError(RuntimeError):
    pass


def _section_text(name: str, lines: list[str]) -> str:
    if name == "정보":
        cut = next((i for i, l in enumerate(lines) if l.strip().startswith(STORY_MARKERS)), len(lines))
        lines = lines[:cut]
    return "\n".join(lines)[:MAX_SECTION_CHARS]


def _source_body(src: Source) -> str:
    parts = []
    names = SOURCE_SECTIONS if src.key == "namu" else list(src.sections)
    for name in names:
        lines = src.sections.get(name)
        if lines:
            text = _section_text(name, lines)
            if text.strip():
                parts.append(f"## {name}\n{text}")
    return "\n\n".join(parts)


def build_source(sources) -> str:
    """여러 출처를 [출처 N] 머리말을 붙여 하나의 글로 만든다. Page 하나만 줘도 된다."""
    sources = _as_sources(sources)
    blocks, total = [], 0
    for i, src in enumerate(sources, 1):
        body = _source_body(src)
        if not body:
            continue
        mark = " (공식)" if src.grade == 1 else ""
        block = f"[출처 {i}{mark}] {src.label} - {src.title}\n{body}"
        block = block[: max(0, MAX_SOURCE_CHARS - total)]
        if block:
            blocks.append(block)
            total += len(block)
    return "\n\n".join(blocks)


def _as_sources(sources) -> list[Source]:
    if isinstance(sources, Page):
        from .namu import to_source

        return [to_source(sources)]
    return list(sources)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def validate(items: list[dict], sources, limit: int) -> tuple[list[Fact], list[dict]]:
    """인용이 해당 출처에 그대로 있는 항목만 남긴다. (남긴 것, 버린 것)

    AI가 출처 번호를 잘못 적었어도, 인용이 다른 출처에 그대로 있으면 그 출처로 고쳐서 남긴다.
    """
    sources = _as_sources(sources)
    texts = [_norm(s.text) for s in sources]
    kept: list[Fact] = []
    dropped: list[dict] = []
    count = {s: 0 for s in SECTIONS}
    for it in items:
        sec = it.get("section")
        quote = _norm(str(it.get("quote", ""))).strip("\"'“”")
        body = _norm(str(it.get("text", "")))
        try:
            idx = int(it.get("source", 1)) - 1
        except (TypeError, ValueError):
            idx = 0
        if not (0 <= idx < len(texts)) or quote not in texts[idx]:
            idx = next((i for i, t in enumerate(texts) if quote and quote in t), -1)
        if sec not in count or not body or len(quote) < 8 or idx < 0:
            dropped.append(it)
            continue
        if count[sec] >= limit:
            continue
        count[sec] += 1
        kept.append(Fact(sec, body, _norm(str(it.get("summary", ""))) or body[:20], quote, idx))
    return kept, dropped


ALIAS_TTL_DAYS = 7  # 별칭이 가리키는 모델은 Google이 바꿀 수 있으므로 이 기간이 지나면 다시 확인한다


def _bare(name: str | None) -> str:
    return (name or "").strip().removeprefix("models/")


class AliasCache:
    """"gemini-flash-lite-latest → gemini-3.5-flash-lite"처럼 별칭이 실제로 가리킨 모델을 기억한다.

    성공한 응답의 model_version으로 배우고, 파일(JSON)에 저장해 다음 실행에서도 쓴다.
    """

    def __init__(self, path: Path | None = None, today: dt.date | None = None):
        self.path = path
        self.today = today or dt.date.today()
        self.data: dict[str, dict] = {}
        if path is not None and path.is_file():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.data = {}

    def target(self, model: str) -> str:
        """알고 있는 실제 모델 이름. 모르거나 오래됐으면 이름 그대로."""
        entry = self.data.get(model)
        if not entry:
            return model
        try:
            seen = dt.date.fromisoformat(entry.get("seen", ""))
        except ValueError:
            return model
        if (self.today - seen).days > ALIAS_TTL_DAYS:
            return model
        return entry.get("model") or model

    def learn(self, model: str, actual: str | None) -> None:
        actual = _bare(actual)
        if not actual or actual == model:
            return
        self.data[model] = {"model": actual, "seen": self.today.isoformat()}
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")


def _call(client, model: str, contents: str, types) -> tuple[list[dict], str | None]:
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    try:
        items = json.loads(resp.text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise GeminiError(f"응답을 JSON으로 읽지 못했습니다: {exc}") from exc
    if not isinstance(items, list):
        raise GeminiError("응답이 목록 형식이 아닙니다")
    return items, getattr(resp, "model_version", None)


def _short(exc: Exception) -> str:
    return " ".join(str(exc).split())[:120]


def summarize(page, name: str, model: str | None = None, limit: int = 4,
              client=None, on_fail=None, on_skip=None,
              aliases: AliasCache | None = None) -> tuple[list[Fact], list[dict], str]:
    """(남긴 줄, 버린 항목, 실제로 쓴 모델)을 돌려준다.

    model에 "a, b, c"처럼 여러 모델을 적으면 앞에서부터 시도하고,
    한도 초과(429)·없는 모델(404) 같은 오류가 나면 다음 모델로 넘어간다.
    별칭(예: gemini-flash-lite-latest)이 실패했고 그 별칭이 가리키는 모델이 목록 뒤에 또 있으면,
    같은 모델이라 결과가 같으므로 건너뛰고 그다음 모델로 내려간다.
    """
    aliases = aliases or AliasCache()
    candidates = model_candidates(model)
    source = build_source(page)
    if not source:
        raise GeminiError("요약할 본문을 찾지 못했습니다")
    if client is None:
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise GeminiError("환경 변수 GEMINI_API_KEY가 없습니다")
        from google import genai

        client = genai.Client()
    from google.genai import types

    contents = PROMPT.format(name=name, source=source, limit=limit)
    errors = []
    failed: set[str] = set()  # 실패한 실제 모델 이름
    for m in candidates:
        target = aliases.target(m)
        if target in failed:
            if on_skip is not None:
                on_skip(m, target)
            continue
        try:
            items, actual = _call(client, m, contents, types)
        except Exception as exc:  # API 오류(429, 404 등)나 응답 형식 오류 → 다음 모델
            errors.append(f"{m}: {_short(exc)}")
            failed.update({m, target})
            if on_fail is not None:
                on_fail(m, _short(exc))
            continue
        aliases.learn(m, actual)
        kept, dropped = validate(items, page, limit)
        return kept, dropped, _bare(actual) or m
    raise GeminiError("모든 모델이 실패했습니다 - " + " / ".join(errors))
