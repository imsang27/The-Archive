""".env 파일을 읽어 환경 변수로 넣는다 (외부 패키지 없이).

찾는 순서: 현재 폴더의 .env → 저장소 폴더(the_archive의 상위 폴더)의 .env
이미 설정된 환경 변수는 덮어쓰지 않는다. 시스템/사용자 환경 변수가 항상 우선한다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
REPO_ROOT = Path(__file__).resolve().parent.parent


def parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]  # 따옴표로 감싼 값
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()  # 줄 끝 주석
        values[key] = value
    return values


def candidates(cwd: Path | None = None) -> list[Path]:
    paths = [(cwd or Path.cwd()) / ".env", REPO_ROOT / ".env"]
    seen, out = set(), []
    for p in paths:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def load(paths: list[Path] | None = None, environ=None) -> list[str]:
    """찾은 .env를 읽어 비어 있는 환경 변수만 채운다. 새로 넣은 변수 이름을 돌려준다."""
    environ = os.environ if environ is None else environ
    loaded: list[str] = []
    for path in paths if paths is not None else candidates():
        if not path.is_file():
            continue
        for key, value in parse(path.read_text(encoding="utf-8-sig")).items():
            if not environ.get(key) and value:
                environ[key] = value
                loaded.append(key)
    return loaded
