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

from . import bawiki, dotenv, gemini, namu, rules
from .naver_db import NaverDBError, NaverLoungeDB
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
    p.add_argument("--model", help=f"Gemini 모델. 쉼표로 여러 개를 적으면 실패 시 다음 모델로 넘어감 (기본: GEMINI_MODEL 또는 {gemini.DEFAULT_MODEL})")
    p.add_argument("--json", action="store_true", help="JSON 파일도 함께 저장")
    p.add_argument("--overwrite", action="store_true", help="같은 이름의 노트가 있으면 덮어쓰기")
    p.add_argument("--dry-run", action="store_true", help="저장하지 않고 화면에 출력")
    p.add_argument("--cache", default=".cache/namu", help="HTML 캐시 폴더")
    p.add_argument("--refresh", action="store_true", help="캐시를 무시하고 다시 받기")
    p.add_argument("--today", help="신뢰도 R 계산 기준 날짜 (YYYY-MM-DD)")
    p.add_argument("--no-extra", action="store_true",
                   help="나무위키만 쓰기 (네이버 라운지 DB, Blue Archive Wiki를 쓰지 않음)")
    p.add_argument("--no-browser", action="store_true",
                   help="브라우저(Playwright)가 필요한 출처(네이버 라운지 DB)를 쓰지 않음")
    return p


def collect_extra(name: str, page, args, work, lounge_db) -> list:
    """나무위키 말고 추가 출처를 모은다. 실패해도 나무위키만으로 계속한다."""
    extra = []
    if args.no_extra:
        return extra
    if lounge_db is not None:
        try:
            src = lounge_db.source(name, page.names + [page.title])
            if src:
                extra.append(src)
            else:
                print(f"[알림] {name}: 네이버 라운지 DB에 없음", file=sys.stderr)
        except NaverDBError as exc:
            print(f"[알림] {name}: 네이버 라운지 DB를 읽지 못함 ({exc})", file=sys.stderr)
    if work.bawiki:
        try:
            src = bawiki.fetch(page.names)
            if src:
                extra.append(src)
            else:
                print(f"[알림] {name}: Blue Archive Wiki 문서를 찾지 못함", file=sys.stderr)
        except bawiki.BAWikiError as exc:
            print(f"[알림] {name}: Blue Archive Wiki를 읽지 못함 ({exc})", file=sys.stderr)
    return extra


def run_one(name: str, args, work, out: Path, today: dt.date, lounge_db=None) -> bool:
    try:
        page = namu.find_page(name, work, Path(args.cache), args.refresh)
    except namu.FetchError as exc:
        print(f"[실패] {name}: {exc}", file=sys.stderr)
        return False

    char = Character(name=name, work=work.title, page=page)
    char.sources = [namu.to_source(page)] + collect_extra(name, page, args, work, lounge_db)
    if args.llm == "gemini":
        try:
            def report(model_name, err):
                print(f"[알림] {name}: {model_name} 실패 → 다음 모델 시도 ({err[:60]})", file=sys.stderr)

            def skipped(model_name, target):
                print(f"[알림] {name}: {model_name} 건너뜀 (실패한 별칭과 같은 모델 {target})", file=sys.stderr)

            aliases = gemini.AliasCache(Path(args.cache).parent / "gemini_aliases.json", today)
            facts, dropped, model = gemini.summarize(char.sources, name, model=args.model, on_fail=report,
                                                     on_skip=skipped, aliases=aliases)
            char.facts = facts
            char.author = [f"Gemini ({model})"]
            if dropped:
                print(f"[알림] {name}: 인용을 원문에서 찾지 못한 {len(dropped)}줄을 버렸습니다", file=sys.stderr)
        except Exception as exc:  # API 오류, 키 없음, 응답 형식 오류
            print(f"[알림] {name}: Gemini 요약 실패 → 규칙 기반으로 진행 ({exc})", file=sys.stderr)
    if not char.facts:
        char.facts = rules.extract(page)
        official = []
        for i, src in enumerate(char.sources[1:], 1):
            official += rules.extract_official(src, i)
        char.facts = rules.dedupe(official + char.facts)  # 같은 문장은 추가 출처(공식) 쪽을 남긴다

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
    labels = ", ".join(s.label for s in char.sources)
    print(f"[저장] {path} (줄 {len(char.facts)}개, 출처: {labels})")
    return True


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    dotenv.load()  # .env의 GEMINI_API_KEY 등을 읽는다 (이미 있는 환경 변수가 우선)
    try:
        work = get_work(args.work)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 2
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    use_lounge = work.lounge and not (args.no_extra or args.no_browser)
    lounge_db = NaverLoungeDB(work.lounge, Path(args.cache).parent) if use_lounge else None
    try:
        ok = [run_one(n, args, work, Path(args.out), today, lounge_db) for n in args.names]
    finally:
        if lounge_db is not None:
            lounge_db.close()
    return 0 if all(ok) else 1
