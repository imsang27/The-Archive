"""명령줄 인터페이스.

예:
  python -m the_archive 설지 --work 명조
  python -m the_archive 시로코 호시노 --work 블루아카이브 --llm gemini --out "D:/vault/캐릭터"
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import gemini, namu, rules
from .model import Character
from .render import render
from .works import WORKS, get_work


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="the_archive", description="나무위키에서 캐릭터 정보를 모아 Obsidian 노트로 저장합니다.")
    p.add_argument("names", nargs="+", help="캐릭터 이름 (나무위키 문서 이름)")
    p.add_argument("--work", "-w", required=True, help=f"작품 ({', '.join(WORKS)})")
    p.add_argument("--out", "-o", default="archive", help="노트를 저장할 폴더 (기본: archive)")
    p.add_argument("--llm", choices=["none", "gemini"], default="none",
                   help="성격·외형 요약에 쓸 AI (기본: none = 규칙 기반)")
    p.add_argument("--model", default=gemini.DEFAULT_MODEL, help="Gemini 모델 이름")
    p.add_argument("--json", action="store_true", help="JSON 파일도 함께 저장")
    p.add_argument("--overwrite", action="store_true", help="같은 이름의 노트가 있으면 덮어쓰기")
    p.add_argument("--dry-run", action="store_true", help="저장하지 않고 화면에 출력")
    p.add_argument("--cache", default=".cache/namu", help="HTML 캐시 폴더")
    p.add_argument("--refresh", action="store_true", help="캐시를 무시하고 다시 받기")
    p.add_argument("--today", help="신뢰도 R 계산 기준 날짜 (YYYY-MM-DD)")
    return p


def run_one(name: str, args, work, out: Path, today: dt.date) -> bool:
    try:
        page = namu.find_page(name, work, Path(args.cache), args.refresh)
    except namu.FetchError as exc:
        print(f"[실패] {name}: {exc}", file=sys.stderr)
        return False

    char = Character(name=name, work=work.title, page=page)
    if args.llm == "gemini":
        try:
            facts, dropped = gemini.summarize(page, name, model=args.model)
            char.facts = facts
            char.author = [f"Gemini ({args.model})"]
            if dropped:
                print(f"[알림] {name}: 인용을 원문에서 찾지 못한 {len(dropped)}줄을 버렸습니다", file=sys.stderr)
        except Exception as exc:  # API 오류, 키 없음, 응답 형식 오류
            print(f"[알림] {name}: Gemini 요약 실패 → 규칙 기반으로 진행 ({exc})", file=sys.stderr)
    if not char.facts:
        char.facts = rules.extract(page)

    md = render(char, work, today)
    if args.dry_run:
        print(md)
        return True
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.md"
    if path.exists() and not args.overwrite:
        print(f"[건너뜀] {path} 이(가) 이미 있습니다 (--overwrite로 덮어쓰기)", file=sys.stderr)
        return False
    path.write_text(md, encoding="utf-8", newline="\n")
    if args.json:
        (out / f"{name}.json").write_text(
            json.dumps(char.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[저장] {path} (줄 {len(char.facts)}개, 출처 {page.url})")
    return True


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        work = get_work(args.work)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 2
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    ok = [run_one(n, args, work, Path(args.out), today) for n in args.names]
    return 0 if all(ok) else 1
