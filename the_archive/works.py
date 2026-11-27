"""작품별 설정: 나무위키 문서 이름 규칙, 노트의 작품 링크와 태그."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Work:
    key: str
    title: str  # 노트에 쓸 작품 이름
    namu_suffix: str  # 동명이인 문서 구분자. 예: "명조: 워더링 웨이브" -> "설지(명조: 워더링 웨이브)"
    keyword: str  # 문서가 이 작품의 문서인지 확인할 때 찾을 단어
    tag: str  # 노트 태그
    link: str  # Preference 노트의 작품 헤딩 링크
    lounge: str = ""  # 네이버 게임 라운지 이름 (DB에서 공식 소개문을 가져옴)
    bawiki: bool = False  # Blue Archive Wiki를 출처로 쓸지


WORKS = {
    w.key: w
    for w in [
        Work("블루 아카이브", "블루 아카이브", "블루 아카이브", "블루 아카이브",
             "캐릭터/블루_아카이브", "[[Preference#1. Blue Archive]]", lounge="Blue_Archive", bawiki=True),
        Work("원신", "원신", "원신", "원신", "캐릭터/원신", "[[Preference#2. Genshin Impact]]"),
        Work("스타레일", "붕괴: 스타레일", "붕괴: 스타레일", "스타레일",
             "캐릭터/붕괴_스타레일", "[[Preference#3. Honkai: StarRail]]"),
        Work("명조", "명조: 워더링 웨이브", "명조: 워더링 웨이브", "명조",
             "캐릭터/명조", "[[Preference#4. Wuthering Waves]]", lounge="WutheringWaves"),
        Work("니케", "승리의 여신: 니케", "승리의 여신: 니케", "니케",
             "캐릭터/니케", "[[Preference#5. GODDESS OF VICTORY: NIKKE]]"),
    ]
}

ALIASES = {
    "블아": "블루 아카이브", "bluearchive": "블루 아카이브", "blue archive": "블루 아카이브",
    "genshin": "원신", "starrail": "스타레일", "붕괴 스타레일": "스타레일",
    "wuthering waves": "명조", "ww": "명조", "nikke": "니케",
}


def get_work(name: str) -> Work:
    raw = name.strip().lower()
    key = ALIASES.get(raw, name.strip())
    if key not in WORKS:  # 띄어쓰기를 무시하고 한 번 더 찾는다 (예: 블루아카이브)
        squeezed = {k.replace(" ", ""): k for k in WORKS}
        key = squeezed.get(raw.replace(" ", ""), key)
    if key not in WORKS:
        raise KeyError(f"알 수 없는 작품: {name} (사용 가능: {', '.join(WORKS)})")
    return WORKS[key]
