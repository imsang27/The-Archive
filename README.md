# The Archive - 캐릭터 특징 자동 수집 및 저장 시스템

> `수많은 세계를 넘나들며 캐릭터의 특징과 개성을 수집하고 보존하는 디지털 아키비스트.  
> 아키비스트가 집필한 이 고대의 필사본은, 정체성들의 마지막 아카이브이자  
> 캐릭터의 본질과 원형(archetype)을 탐색하고, 기록하며, 연결하는 인격의 기록서입니다.`

---

## 📖 소개

**The Archive**는 사용자가 애니/게임 캐릭터의 이름 또는 특정 특징(예: '여우귀', '핑크색 머리')으로 검색하면, 인터넷에서 해당 정보를 자동 수집하고 요약하며, 사용자 검토(RUD)를 거쳐 Markdown 파일로 저장할 수 있는 도구입니다.

단순한 정보 수집을 넘어, **캐릭터의 본질과 서사**, 그리고 **개성의 맥락**까지 담아내는 **캐릭터 중심 데이터 아카이브**입니다.

---

## 🚀 주요 기능

### ✅ 현재 구현 예정 (1단계: MVP)
- **캐릭터 이름으로 정보 검색**
  - 나무위키, Wikipedia 등에서 자동 크롤링
  - 등장 작품, 성격, 외형, 기타 요소 정리

- **LLM 기반 요약 및 템플릿 정리**
  - GPT 또는 Claude API를 활용한 요약 기능
  - 항목별 Markdown 포맷으로 변환

- **사용자 검토 및 수정 (RUD)**
  - 요약된 정보에 대한 편집 UI 제공
  - 최종 수정을 반영한 파일 저장

- **Markdown / JSON 저장**
  - Obsidian 호환 `.md`로 저장 가능
  - 태그 및 연결 링크 자동 삽입

### 🔜 향후 구현 예정
- **특징 기반 검색** (2단계)
  - '핑크색 머리', '여우귀' 같은 특징으로 캐릭터 검색 가능
  - 키워드 기반 필터 및 태그 매칭 기능

- **태그 자동 생성** (3단계)
  - GPT 기반 태그 자동 생성기
  - 결과 파일에 태그 삽입 (`tags: [여우귀, 핑크색 머리]`)

- **Obsidian 호환 기능** (3단계)
  - 링크 구조 지원 (예: `[[카구야 신궁]]`)
  - 캐릭터 이미지 자동 수집 및 포함

---

## 🛠️ 기술 스택

| 구성 | 기술 |
|------|------|
| 백엔드 | Python (FastAPI / Flask) |
| 프론트엔드 | Streamlit (MVP) → React (확장 시) |
| 크롤링 | requests, BeautifulSoup, Wikipedia API, Google Custom Search API |
| 요약 | OpenAI GPT, Claude API, 또는 로컬 모델 |
| 저장 | Markdown + 태그 기반 파일 시스템, Json |
| 검색 | 키워드 매칭, 태그 인덱싱, keyword index (Whoosh / SQLite / ElasticSearch 등 선택) |

---

## 📂 예시 저장 결과 (Markdown)

```markdown
# 카구야 신궁 (Kaguya Shinomiya)
---

## 기본 정보
- 출처: 카구야님은 고백받고 싶어
- 성별: 여자
- 소속: 슈치인 학원 학생회

## 성격
- 겉으로는 냉정하고 완벽주의자이나, 내면은 순수함
- 상대의 반응에 민감한 츤데레 기질

## 외형
- 긴 흑발, 붉은 눈
- 단정한 교복 차림

## 기타 특징
- 재벌가 출신
- 높은 두뇌 회전과 전략적 사고 능력

## 태그
- #여고생 #흑발 #츤데레 #엘리트 #카구야님
```

---

## 🏛️ 사용 예시 (예정)

```bash
# 캐릭터 특징 자동 수집
$ python fetch_character.py --name "Lacus Clyne"

# 태그 기반 검색
$ python search.py --trait "pacifist"

# 정제된 프로필 출력
$ cat archive/Lacus_Clyne.md
```

---

## 🗂️ 프로젝트 구조

```
The-Archive/
├── archive/              # 저장된 캐릭터 기록들 (Markdown)
├── fetcher/              # 정보 수집 및 전처리 모듈
├── traits/               # 특징 / 개성 분류 기준
├── interface/            # CLI 또는 GUI 인터페이스
├── utils/                # 유틸리티 및 도우미 함수들
└── README.md             # 프로젝트 소개 문서
```

---

## 📌 사용 방법 (예정)

1. 캐릭터 이름을 입력합니다.
2. 자동으로 정보를 수집하고 요약합니다.
3. 편집기에서 내용을 확인하고 수정합니다.
4. Markdown 또는 JSON 파일로 저장합니다.

> 추후 CLI/GUI 버전과 특징 기반 검색도 추가될 예정입니다.

---

## 🎯 개발 목표

- 기록을 넘어 **의미 있는 연결**을 만든다.
- 정보의 수집보다, **본질의 보존**을 추구한다.
- 기능보다 먼저 **세계관과 정체성**이 살아 있는 아카이브를 구축한다.

---

## 📎 프로젝트 상태

### 🔹1단계: 기본 기능 (MVP)
- [ ] 캐릭터 이름 입력 UI 구현 (CLI / Streamlit)
- [ ] 위키 기반 크롤러 구현 (나무위키, Wikipedia)
- [ ] 텍스트 정리/요약 기능 구현 (OpenAI API 연동)
- [ ] Markdown 템플릿 설계 및 저장 기능
- [ ] 사용자 검토 기능 (텍스트 창 or 간단한 웹 UI)

### 🔹2단계: 특징 기반 검색
- [ ] 캐릭터 특징 DB 구조 설계 (예: JSON or SQLite)
- [ ] 특징 키워드 기반 검색 알고리즘
- [ ] 태그/특징 추출 자동화 (LLM 또는 rule-based)
- [ ] UI에 검색 필터 추가 (예: "핑크색", "여우귀", "츤데레")

### 🔹3단계: 보완 기능
- [ ] 태그 자동 생성기 (GPT 기반)
- [ ] 결과 파일에 태그 삽입 (`tags: [여우귀, 핑크색 머리]`)
- [ ] Obsidian 호환 링크 구조 (예: `[[카구야 신궁]]`)
- [ ] 캐릭터 이미지 자동 수집 및 포함 (선택 기능)

### 🔹4단계: 기술적 안정화
- [ ] 예외 처리 및 네트워크 오류 대응
- [ ] 캐시 또는 중복 처리 로직
- [ ] 저장된 데이터 재활용 (기록 검색/수정)

### 🔹5단계: 배포 및 고도화
- [ ] GitHub에 프로젝트 공개
- [ ] 사용법 README 작성
- [ ] 로컬 GUI or Electron 앱화 고려

---

## 👥 타겟 사용자

- 캐릭터 정보를 정리하는 위키 운영자
- 창작 캐릭터와 비교 분석하려는 작가/창작자
- 모에 요소 기반 캐릭터를 탐색하려는 팬/연구자

---

## 🪶 크레딧

- Designed by [the Archivist](https://github.com/imsang27?tab=repositories).
- Inspired by stories, characters, and the infinite worlds they live in.

---

## 📜 라이선스

This project is licensed under the **MIT License**.  
Feel free to expand, fork, or contribute to the Archive.
