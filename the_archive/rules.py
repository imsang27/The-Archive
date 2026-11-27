"""규칙 기반 추출: AI 없이 출처 문장을 그대로 골라 노트 줄로 만든다.

문장을 고쳐 쓰지 않으므로 지어낸 내용이 들어가지 않는다. 대신 문장이 길고 거칠 수 있다.
"""

from __future__ import annotations

import re

from .model import Fact, Page, Source

INTRO_SECTIONS = ("개요", "인물 소개", "공식 소개", "캐릭터성")
TRIVIA_SECTIONS = ("여담", "기타", "캐릭터성", "디자인")

PERSONALITY = re.compile(
    r"성격|성품|차갑|다정|상냥|활발|냉철|서툴|장난|온화|느긋|귀찮|무뚝뚝|호전|다혈질|열정|초연|"
    r"수줍|내성적|밝은|쾌활|침착|진지|엄격|이성|츤데레|낭만|순수|야성|고압|어리광"
)
APPEARANCE = re.compile(
    r"머리카락|머리색|흑발|백발|은발|금발|적발|녹발|장발|단발|포니테일|눈동자|오드아이|"
    r"외모|외형|복장|의상|체구|키가|귀를|꼬리|머리 장식|성흔의 위치"
)
SKIP = re.compile(r"플레이어블 캐릭터\.?$|등장 캐릭터\.?$|^\[ ?펼치기|^파일:|^\"|^「|^- 모모톡|^〈|모집 중|프로필 공개 \||^\[ ?(캐릭터 스토리|어빌리티 정보)")
SENTENCE_END = re.compile(r"(?<=[가-힣])\. ")

MAX_TEXT = 220
MAX_QUOTE = 60


def _sentences(line: str) -> list[str]:
    line = re.sub(r"\[\d+\]", "", line).strip()
    return [s.strip() for s in SENTENCE_END.split(line) if s.strip()]


def make_quote(sentence: str, page_text: str) -> str:
    """문장 앞부분에서, 페이지에 그대로 있는 짧은 조각을 고른다."""
    s = sentence.rstrip(".")
    if len(s) <= MAX_QUOTE and s in page_text:
        return s
    cut = s[:MAX_QUOTE]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    while cut and cut not in page_text:
        cut = cut[: cut.rfind(" ")] if " " in cut else ""
    return cut


def _summary(sentence: str) -> str:
    s = sentence.rstrip(".")
    return s if len(s) <= 24 else s[:24].rstrip() + "…"


def _candidates(page: Page, names: tuple[str, ...]) -> list[str]:
    out = []
    for name in names:
        for line in page.sections.get(name, []):
            if SKIP.search(line) or len(line) < 12:
                continue
            out.extend(_sentences(line))
    return out


def extract(page: Page, limit_per_section: int = 4) -> list[Fact]:
    facts: list[Fact] = []
    used: set[str] = set()

    def add(section: str, sentence: str) -> bool:
        if sentence in used or len(sentence) > MAX_TEXT:
            return False
        quote = make_quote(sentence, page.text)
        if len(quote) < 8:
            return False
        used.add(sentence)
        text = sentence if sentence.endswith((".", "다", "요")) else sentence + "."
        if not text.endswith("."):
            text += "."
        facts.append(Fact(section, text, _summary(sentence), quote))
        return True

    intro = _candidates(page, INTRO_SECTIONS)
    # 명조 등: "정보" 섹션의 "[ 기본 정보 ]" 줄만 쓴다 (나머지는 캐릭터 스토리라서 뺀다)
    basic = next((l for l in page.sections.get("정보", []) if l.startswith("[ 기본 정보 ]")), "")
    if basic:
        intro = _sentences(basic.replace("[ 기본 정보 ]", "", 1)) + intro
    trivia = _candidates(page, TRIVIA_SECTIONS)

    n = 0
    for s in intro + trivia:
        if n < limit_per_section and PERSONALITY.search(s) and add("성격", s):
            n += 1
    n = 0
    for s in trivia + intro:
        if n < limit_per_section and APPEARANCE.search(s) and add("외형", s):
            n += 1
    n = 0
    for s in intro:
        if n < limit_per_section and add("기타", s):
            n += 1
    return facts


OFFICIAL_SKIP = re.compile(r"^〈|^[\"“「]|>>\s*$|^[-─—]+")
HANGUL = re.compile(r"[가-힣]")


def extract_official(src: Source, index: int, limit: int = 3) -> list[Fact]:
    """공식 소개문 같은 추가 출처에서 한국어 문장 몇 개를 원문 그대로 고른다.

    외국어 출처(예: 영문 위키)는 규칙 기반으로는 번역할 수 없으므로 고르지 않는다.
    """
    facts: list[Fact] = []
    for lines in src.sections.values():
        for line in lines:
            line = re.sub(r"^[◆]?[가-힣]+>>\s*", "", line.strip())  # "아카이브>>" 같은 머리말
            if not line or OFFICIAL_SKIP.search(line) or not HANGUL.search(line):
                continue
            for sentence in _sentences(line):
                if len(facts) >= limit or len(sentence) < 12:
                    continue
                quote = make_quote(sentence, src.text)
                if len(quote) < 8:
                    continue
                section = "성격" if PERSONALITY.search(sentence) else "기타"
                text = sentence if sentence.endswith(".") else sentence + "."
                facts.append(Fact(section, text, _summary(sentence), quote, index))
    return facts


def _key(text: str) -> str:
    return re.sub(r"[\s.,·]", "", text)


def dedupe(facts: list[Fact]) -> list[Fact]:
    """띄어쓰기·문장부호만 다른 같은 문장은 먼저 나온 것 하나만 남긴다."""
    seen: set[str] = set()
    out = []
    for f in facts:
        k = _key(f.text)
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    return out
