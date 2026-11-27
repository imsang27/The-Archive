"""Gemini API로 성격·외형·기타 특징을 요약한다.

AI가 쓴 줄마다 출처 원문 인용(quote)을 함께 받고, 인용이 페이지에 실제로 없으면 그 줄을 버린다.
API 키는 환경 변수 GEMINI_API_KEY(또는 GOOGLE_API_KEY)에서 읽는다.
"""

from __future__ import annotations

import json
import os
import re

from .model import SECTIONS, Fact, Page

DEFAULT_MODEL = "gemini-flash-latest"


def default_model() -> str:
    """환경 변수(.env 포함) GEMINI_MODEL이 있으면 그 값을 쓴다."""
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
SOURCE_SECTIONS = ("개요", "인물 소개", "공식 소개", "정보", "캐릭터성", "여담", "디자인")
MAX_SOURCE_CHARS = 15000

PROMPT = """너는 캐릭터 기록을 정리하는 아키비스트다. 아래 [출처]는 나무위키 문서 "{title}"의 일부다.
캐릭터 "{name}"의 성격, 외형, 기타 특징을 한국어로 정리하라.

규칙:
- [출처]에 있는 내용만 쓴다. 출처에 없는 지식, 추측, 평가를 더하지 않는다.
- 각 항목은 한 문장, "~다."로 끝나는 평서문으로 쓴다.
- section은 "성격", "외형", "기타" 중 하나다. 각 section은 최대 {limit}개.
- summary는 대조 체크리스트용 15자 안팎의 짧은 요약이다.
- quote는 그 문장의 근거가 되는 [출처] 원문을 한 글자도 바꾸지 않고 그대로 옮긴 조각이다.
  8~60자, 각주 번호([1] 등)와 따옴표가 들어간 부분은 피한다.
- 줄거리 스포일러, 게임 성능·수치, 밈은 넣지 않는다.

[출처]
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
            "quote": {"type": "string"},
        },
        "required": ["section", "text", "summary", "quote"],
    },
}


class GeminiError(RuntimeError):
    pass


def build_source(page: Page) -> str:
    parts = []
    for name in SOURCE_SECTIONS:
        lines = page.sections.get(name)
        if lines:
            parts.append(f"## {name}\n" + "\n".join(lines))
    return "\n\n".join(parts)[:MAX_SOURCE_CHARS]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def validate(items: list[dict], page: Page, limit: int) -> tuple[list[Fact], list[dict]]:
    """인용이 페이지에 그대로 있는 항목만 남긴다. (남긴 것, 버린 것)"""
    text = _norm(page.text)
    kept: list[Fact] = []
    dropped: list[dict] = []
    count = {s: 0 for s in SECTIONS}
    for it in items:
        sec = it.get("section")
        quote = _norm(it.get("quote", "")).strip("\"'“”")
        body = _norm(it.get("text", ""))
        if sec not in count or not body or len(quote) < 8 or quote not in text:
            dropped.append(it)
            continue
        if count[sec] >= limit:
            continue
        count[sec] += 1
        kept.append(Fact(sec, body, _norm(it.get("summary", "")) or body[:20], quote))
    return kept, dropped


def summarize(page: Page, name: str, model: str | None = None, limit: int = 4,
              client=None) -> tuple[list[Fact], list[dict]]:
    model = model or default_model()
    source = build_source(page)
    if not source:
        raise GeminiError("요약할 본문을 찾지 못했습니다")
    if client is None:
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise GeminiError("환경 변수 GEMINI_API_KEY가 없습니다")
        from google import genai

        client = genai.Client()
    from google.genai import types

    resp = client.models.generate_content(
        model=model,
        contents=PROMPT.format(title=page.title, name=name, source=source, limit=limit),
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
        ),
    )
    try:
        items = json.loads(resp.text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise GeminiError(f"응답을 JSON으로 읽지 못했습니다: {exc}") from exc
    if not isinstance(items, list):
        raise GeminiError("응답이 목록 형식이 아닙니다")
    return validate(items, page, limit)
