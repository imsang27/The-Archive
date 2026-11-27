"""특징 속성(머리·눈·성격)을 출처에서 뽑는다.

노트 프론트메터에 `머리: 은발`, `눈: 오드아이(노랑·파랑)`, `성격: [냉철, 다혈질]`처럼 Key: Value로 넣는다.
값마다 출처 원문 인용을 받고, 인용이 출처에 그대로 없으면 그 값은 버린다.
"""

from __future__ import annotations

import re

from . import gemini
from .model import Trait

KEYS = ("머리", "눈", "성격")
# 같은 특징이 같은 값으로 모이도록, 정해 둔 낱말 안에서만 고르게 한다 (JSON 스키마 enum으로 강제)
COLORS = ["검정", "갈색", "금색", "은색", "흰색", "회색", "빨강", "주황", "노랑", "초록",
          "하늘색", "파랑", "남색", "보라", "분홍"]
VOCAB = {
    "머리": COLORS,
    "눈": COLORS + ["오드아이"],
    "성격": ["냉철", "냉담", "까칠", "무뚝뚝", "초연", "진지", "엄격", "이성적", "차분", "신중",
             "다정", "상냥", "온화", "친절", "순수", "순진", "수줍음", "소심", "내성적",
             "활발", "명랑", "쾌활", "장난기", "사교적", "열정적", "야성적", "호전적", "다혈질",
             "대담", "강인", "당당", "자신감", "직설적", "집요", "성실", "책임감", "정의감",
             "느긋", "게으름", "낭만적", "감정적", "신비로움", "오만", "교활", "엉뚱"],
}
LIMITS = {"머리": 1, "눈": 1, "성격": 4}

PROMPT = """너는 캐릭터의 특징을 분류하는 아키비스트다. 아래 [출처 N]들에서 캐릭터 "{name}"의 특징을 뽑아라.

뽑을 것 (value는 반드시 아래 목록의 낱말 중에서만 고른다):
- 머리: 머리카락의 주된 색. 최대 1개. 목록: {hair}
- 눈: 눈동자 색. 양쪽 색이 다르면 "오드아이". 최대 1개. 목록: {eyes}
- 성격: 성격을 가장 잘 나타내는 낱말. 최대 4개. 목록: {mind}

규칙:
- [출처]에 근거가 있는 것만 뽑는다. 근거가 없으면 그 항목은 빈 목록으로 둔다. 짐작하지 않는다.
- 머리 모양(트윈 테일 등)이나 장식은 머리 색이 아니다. 색이 출처에 없으면 머리는 빈 목록으로 둔다.
- source는 근거가 된 [출처 N]의 번호 N이다.
- quote는 그 [출처 N] 원문을 한 글자도 바꾸지 않고 옮긴 조각이다 (번역하지 않는다). 8~60자.
- "{name}" 본인에 대한 서술만 근거로 쓴다. 다른 인물, 초기 디자인, 다른 모습(변신·의상)의 묘사는 쓰지 않는다.

{source}
"""

_ITEM = {
    "type": "object",
    "properties": {"value": {"type": "string"}, "source": {"type": "integer"}, "quote": {"type": "string"}},
    "required": ["value", "source", "quote"],
}


def _item(key: str) -> dict:
    item = {**_ITEM, "properties": {**_ITEM["properties"], "value": {"type": "string", "enum": VOCAB[key]}}}
    return {"type": "array", "items": item}


SCHEMA = {
    "type": "object",
    "properties": {k: _item(k) for k in KEYS},
    "required": list(KEYS),
}


def validate(data: dict, sources) -> tuple[list[Trait], list[dict]]:
    sources = gemini._as_sources(sources)
    texts = [gemini._norm(s.text) for s in sources]
    kept: list[Trait] = []
    dropped: list[dict] = []
    for key in KEYS:
        seen: set[str] = set()
        for it in (data.get(key) or [])[: LIMITS[key] * 2]:
            value = re.sub(r"\s+", " ", str(it.get("value", ""))).strip().strip(".")
            quote = gemini._norm(str(it.get("quote", ""))).strip("\"'“”")
            try:
                idx = int(it.get("source", 1)) - 1
            except (TypeError, ValueError):
                idx = 0
            if not (0 <= idx < len(texts)) or quote not in texts[idx]:
                idx = next((i for i, t in enumerate(texts) if quote and quote in t), -1)
            if value not in VOCAB[key] or len(quote) < 8 or idx < 0 or value in seen:
                dropped.append({"key": key, **it})
                continue
            if len([t for t in kept if t.key == key]) >= LIMITS[key]:
                continue
            seen.add(value)
            kept.append(Trait(key, value, quote, idx))
    return kept, dropped


def extract(sources, name: str, model: str | None = None, client=None, on_fail=None, on_skip=None,
            aliases=None) -> tuple[list[Trait], list[dict], str]:
    source = gemini.build_source(sources)
    if not source:
        raise gemini.GeminiError("특징을 뽑을 본문을 찾지 못했습니다")
    contents = PROMPT.format(name=name, source=source, hair=", ".join(VOCAB["머리"]),
                             eyes=", ".join(VOCAB["눈"]), mind=", ".join(VOCAB["성격"]))
    data, used = gemini.run(contents, SCHEMA, dict, model=model, client=client,
                            on_fail=on_fail, on_skip=on_skip, aliases=aliases)
    kept, dropped = validate(data, sources)
    return kept, dropped, used
