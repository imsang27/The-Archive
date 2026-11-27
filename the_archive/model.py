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
    source: int = 0  # Character.sources 안의 출처 번호


@dataclass
class Source:
    """노트의 근거가 되는 출처 하나 (나무위키, 공식 라운지 DB, 영문 위키 등)."""

    key: str  # namu, naver_db, bawiki
    label: str  # 각주에 쓸 이름. 예: "나무위키"
    title: str  # 문서 제목
    url: str
    date: str  # 작성·갱신 날짜 (YYYY-MM-DD), 모르면 ""
    grade: int  # 1 = 1차 출처(공식), 2 = 2차 출처(위키 등)
    text: str  # 인용 검증용 전체 텍스트
    sections: dict[str, list[str]] = field(default_factory=dict)  # AI에 보낼 섹션별 본문
    note: str = ""  # 각주 뒤에 붙일 설명


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
    sources: list[Source] = field(default_factory=list)  # [0]은 항상 나무위키

    def to_json(self) -> dict:
        data = asdict(self)
        data["page"].pop("text")
        data["page"].pop("lines")
        for s in data["sources"]:
            s.pop("text")
            s.pop("sections")
        return data
