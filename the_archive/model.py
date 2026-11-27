"""수집한 캐릭터 정보를 담는 자료 구조."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

SECTIONS = ("성격", "외형", "기타")


@dataclass
class Fact:
    """노트 본문 한 줄과, 그 줄을 받치는 출처 원문 인용."""

    section: str  # 성격, 외형, 기타 중 하나
    text: str  # 노트에 쓸 문장
    summary: str  # 대조 체크리스트에 쓸 짧은 요약
    quote: str  # 출처 페이지에서 Ctrl+F로 찾을 수 있는 원문 조각


@dataclass
class Page:
    """나무위키 문서 하나를 텍스트로 정리한 결과."""

    title: str
    url: str
    source_date: str  # 최근 수정 날짜 (YYYY-MM-DD), 모르면 ""
    text: str  # 페이지 전체 텍스트 (인용 검증용)
    lines: list[str]
    profile: dict[str, str]
    names: list[str]  # 원어 이름, 로마자 이름 등 (별칭 후보)
    voice_actors: list[str]
    sections: dict[str, list[str]]  # 헤딩 제목 -> 본문 줄


@dataclass
class Character:
    name: str
    work: str
    page: Page
    facts: list[Fact] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    author: list[str] = field(default_factory=list)  # 내용을 쓴 AI 모델 (규칙 기반만 썼으면 비움)

    def to_json(self) -> dict:
        data = asdict(self)
        data["page"].pop("text")
        data["page"].pop("lines")
        return data
