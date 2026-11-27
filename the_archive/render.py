"""캐릭터 정보를 Obsidian 노트(Markdown)로 만든다.

형식은 볼트의 Rules.md(프론트메터, 헤딩 번호, 대조 체크리스트, 신뢰도 계산)를 따른다.
"""

from __future__ import annotations

import datetime as dt
import json

from .model import SECTIONS, Character, Source
from .namu import to_source
from .works import Work

PROFILE_ORDER = ["이명", "소속 학원", "동아리", "소속", "나이", "성별", "생일", "키", "신장", "출생",
                 "세력", "종족", "속성", "무기", "공명 어빌리티", "취미"]
SECTION_TITLES = {"성격": "2. 성격", "외형": "3. 외형", "기타": "4. 기타 특징"}
SECTION_NUM = {"성격": "2.", "외형": "3.", "기타": "4."}
EMPTY = "%% 출처에서 따로 다룬 내용을 찾지 못해 비워 둠 %%"


def recency_score(source_date: str, today: dt.date) -> tuple[int, str]:
    """Rules.md 1.1.2.의 R. Source_date만 있고 Verified_date는 없는 상태로 계산한다."""
    if not source_date:
        return 0, "Source_date 없음"
    y, m = int(source_date[:4]), int(source_date[5:7]) if len(source_date) >= 7 else 1
    months = 12 * (today.year - y) + (today.month - m)
    score = 10 if months <= 6 else 5 if months <= 12 else 0
    return score, f"Source_date {source_date}, Δt={months}"


def _yaml_list(key: str, values: list[str]) -> str:
    if not values:
        return f"{key}:"
    return f"{key}:\n" + "\n".join(f"  - {v}" for v in values)


def _q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def choose_core(sources: list[Source], facts) -> int:
    """Rules.md의 핵심 출처 기준: (1) 원출처(1차) → (2) 가장 많은 줄을 받치는 출처 → (3) 날짜가 있는 출처."""
    counts = {i: 0 for i in range(len(sources))}
    counts[0] += 1  # 나무위키는 기본 정보 표를 받친다
    for f in facts:
        counts[f.source] = counts.get(f.source, 0) + 1
    used = [i for i, c in counts.items() if c > 0]
    return min(used, key=lambda i: (sources[i].grade, -counts[i], 0 if sources[i].date else 1, i))


def render(char: Character, work: Work, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    page = char.page
    sources = char.sources or [to_source(page)]
    used = sorted({0} | {f.source for f in char.facts})
    core = choose_core(sources, char.facts)
    order = [core] + [i for i in used if i != core]
    fn = {src: n for n, src in enumerate(order, 1)}  # 출처 번호 → 각주 번호
    core_src = sources[core]

    def ref(i: int) -> str:
        s = sources[i]
        return f"[{s.label} - {s.title}]({s.url})"

    r_score, r_note = recency_score(core_src.date, today)
    s_score = 40 if core_src.grade == 1 else 20
    c_score = 20 if len(used) >= 2 else 10
    confidence = s_score + c_score + r_score
    has_ai = bool(char.author)

    fm = [
        "---",
        "Date_of_creation: <% tp.file.creation_date('YYYY-MM-DD ddd HH:mm:ss') %>",
        "Last_modified:",
        "  - <% tp.file.last_modified_date('YYYY-MM-DD ddd HH:mm:ss') %>",
        _yaml_list("aliases", page.names),
        _yaml_list("tags", [work.tag] + char.tags),
        "Reference:",
        *[f"  - {_q(ref(i))}" for i in order],
    ]
    if has_ai:
        fm.append(_yaml_list("Author", char.author))
    fm += [
        f"Source_date: {core_src.date}".rstrip(),
        "Verified_date:",
        f"Confidence: {confidence}",
    ]
    if has_ai:
        fm += ["Review_status: 미검토", "Reviewed_date:"]
    fm += [f"작품: {_q(work.link)}", "취향:", "---"]

    nf = f"[^{fn[0]}]"  # 기본 정보 표는 나무위키가 받친다
    rows = [f"| 이름 | {char.name}" + (f" ({', '.join(page.names)})" if page.names else "") + f"{nf} |",
            f"| 작품 | {work.title}{nf} |"]
    for key in PROFILE_ORDER:
        if page.profile.get(key):
            rows.append(f"| {key} | {page.profile[key]}{nf} |")
    if page.voice_actors:
        rows.append(f"| 성우 | {', '.join(page.voice_actors)} (나무위키 표기 순){nf} |")

    body = ["# 1. 기본 정보", "---", "", "| 항목 | 내용 |", "| :-- | :-- |", *rows, ""]
    for sec in SECTIONS:
        lines = [f"- {f.text}[^{fn[f.source]}]" for f in char.facts if f.section == sec]
        body += [f"# {SECTION_TITLES[sec]}", "---", *(lines or [EMPTY]), ""]

    def tag(i: int) -> str:
        return "[핵심]" if i == core else "[보조]"

    checks = []
    profile_keys = [k for k in PROFILE_ORDER if page.profile.get(k)]
    if profile_keys:
        anchor = next((f"{k}: {page.profile[k]}" for k in profile_keys
                       if f"{k}: {page.profile[k]}" in page.text), None)
        quote = f'"{anchor}"' if anchor else f"검색어: {page.profile[profile_keys[-1]]}"
        checks.append(f"> - [ ] {tag(0)} {'·'.join(profile_keys[:6])} (1.){nf} — {quote}")
    facts = sorted(char.facts, key=lambda f: f.source != core)  # 핵심 줄을 먼저
    for f in facts:
        checks.append(f'> - [ ] {tag(f.source)} {f.summary} ({SECTION_NUM[f.section]})[^{fn[f.source]}] — "{f.quote}"')
    if checks:
        body += ["> [!check]- 대조 체크리스트", *checks, ""]

    notes = []
    for i in order:
        s = sources[i]
        extra = [x for x in (f"최근 수정 {s.date}" if s.date else "", s.note) if x]
        notes.append(f"[^{fn[i]}]: {ref(i)}" + (f" ({', '.join(extra)})" if extra else ""))
    grade_note = (f"핵심 출처가 1차({core_src.label})" if core_src.grade == 1
                  else "1차 출처 없음, 위키(2차)")
    tail = [
        "---",
        *notes,
        "",
        f"%% Confidence: S={s_score}, V=0, C={c_score}, R={r_score} → {confidence} | "
        f"S: {grade_note} | C: 줄을 받치는 독립 출처 {len(used)}개 | R: {r_note} %%",
    ]
    return "\n".join(fm + body + tail) + "\n"
