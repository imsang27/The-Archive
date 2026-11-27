import datetime as dt
import json
import unittest

import tempfile
from pathlib import Path

from the_archive import dotenv, gemini, namu, rules
from the_archive.model import Character
from the_archive.render import recency_score, render
from the_archive.works import get_work

# 나무위키 문서 구조를 흉내 낸 작은 HTML (실제 문서 내용이 아님)
SAMPLE = """<html><head><title>테스트캐릭터(명조: 워더링 웨이브) - 나무위키</title>
<script>var x = 1;</script></head><body>
<div>최근 수정 시각: 2026-11-20 10:00:00</div>
<div>테스트캐릭터</div>
<div>測試(cèshì) | テスト | Tester</div>
<div>성별: 여성</div><div>생일: 1월 1일</div><div>속성: 응결</div><div>무기: 직검</div>
<div>공명 어빌리티: 시험의 칼날</div>
<div>성우 정보</div><div>가나다</div><div>라마바</div>
<div>1. 개요2. 공식 소개3. 여담</div>
<h2>1. 개요[편집]</h2>
<div>"따옴표로 시작하는 대사는 건너뛴다."</div>
<div>테스트캐릭터는 차갑고 침착한 성격의 검사이다. 그녀는 북쪽 마을에서 왔다.</div>
<div>《명조: 워더링 웨이브》의 플레이어블 캐릭터.</div>
<h2>2. 공식 소개[편집]</h2>
<div>〈영상 제목〉 - 테스트캐릭터</div>
<h2>3. 여담[편집]</h2>
<div>머리카락은 은발이고 눈동자는 푸른색이다.[1]</div>
</body></html>"""


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.page = namu.parse_page(SAMPLE, "테스트캐릭터(명조: 워더링 웨이브)")

    def test_title_date_profile(self):
        p = self.page
        self.assertEqual(p.title, "테스트캐릭터(명조: 워더링 웨이브)")
        self.assertEqual(p.source_date, "2026-11-20")
        self.assertEqual(p.profile["속성"], "응결")
        self.assertEqual(p.profile["공명 어빌리티"], "시험의 칼날")
        self.assertEqual(p.names, ["測試", "Tester"])
        self.assertEqual(p.voice_actors, ["가나다", "라마바"])
        self.assertNotIn("var x", p.text)

    def test_sections(self):
        self.assertIn("개요", self.page.sections)
        self.assertIn("머리카락은 은발이고 눈동자는 푸른색이다.[1]", self.page.sections["여담"])


class RulesTest(unittest.TestCase):
    def test_facts_are_verbatim(self):
        page = namu.parse_page(SAMPLE, "x")
        facts = rules.extract(page)
        by = {f.section: f for f in facts}
        self.assertIn("성격", by)
        self.assertIn("외형", by)
        for f in facts:
            self.assertIn(f.quote, page.text, f)  # 인용은 반드시 원문에 있어야 한다
            self.assertNotIn("[1]", f.text)
            self.assertFalse(f.text.startswith('"'))
            self.assertNotIn("영상 제목", f.text)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeClient:
    def __init__(self, items):
        self.items = items
        self.models = self

    def generate_content(self, model, contents, config):
        self.prompt = contents
        return FakeResponse(json.dumps(self.items, ensure_ascii=False))


class GeminiTest(unittest.TestCase):
    def test_drops_quotes_not_in_source(self):
        page = namu.parse_page(SAMPLE, "x")
        client = FakeClient([
            {"section": "성격", "text": "차갑고 침착하다.", "summary": "차갑고 침착함",
             "quote": "차갑고 침착한 성격의 검사이다"},
            {"section": "외형", "text": "금발이다.", "summary": "금발", "quote": "머리카락은 금발이다"},
            {"section": "잘못", "text": "x", "summary": "x", "quote": "북쪽 마을에서 왔다"},
        ])
        kept, dropped = gemini.summarize(page, "테스트캐릭터", client=client)
        self.assertEqual([f.section for f in kept], ["성격"])
        self.assertEqual(len(dropped), 2)
        self.assertIn("[출처]", client.prompt)


class RenderTest(unittest.TestCase):
    def test_note_format(self):
        page = namu.parse_page(SAMPLE, "x")
        work = get_work("명조")
        char = Character("테스트캐릭터", work.title, page, facts=rules.extract(page))
        md = render(char, work, dt.date(2026, 11, 28))
        self.assertTrue(md.startswith("---\nDate_of_creation: <% tp.file.creation_date"))
        self.assertIn("Confidence: 40", md)
        self.assertNotIn("Author:", md)  # 규칙 기반은 AI가 쓴 내용이 아니다
        self.assertNotIn("Review_status", md)
        self.assertIn("> [!check]- 대조 체크리스트", md)
        self.assertNotIn("- [x]", md)
        self.assertIn('"성별: 여성"', md)
        self.assertTrue(md.endswith("%%\n"))

    def test_author_and_review_with_ai(self):
        page = namu.parse_page(SAMPLE, "x")
        work = get_work("명조")
        char = Character("t", work.title, page, author=["Gemini (test)"])
        md = render(char, work, dt.date(2026, 11, 28))
        self.assertIn("Author:\n  - Gemini (test)", md)
        self.assertIn("Review_status: 미검토", md)

    def test_recency(self):
        today = dt.date(2026, 11, 28)
        self.assertEqual(recency_score("2026-05-01", today)[0], 10)  # 6개월
        self.assertEqual(recency_score("2026-04", today)[0], 5)  # 7개월
        self.assertEqual(recency_score("2025-11-30", today)[0], 5)  # 12개월
        self.assertEqual(recency_score("2025-10-01", today)[0], 0)
        self.assertEqual(recency_score("", today)[0], 0)


class WorksTest(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(get_work("블루아카이브").key, "블루 아카이브")
        self.assertEqual(get_work("WW").key, "명조")
        with self.assertRaises(KeyError):
            get_work("없는 작품")


class DotenvTest(unittest.TestCase):
    def test_parse(self):
        text = "\n".join([
            "# 주석",
            "GEMINI_API_KEY=abc123",
            'export GEMINI_MODEL="gemini-x"  ',
            "A=1 # 끝 주석",
            "BAD LINE",
            "EMPTY=",
        ])
        self.assertEqual(dotenv.parse(text),
                         {"GEMINI_API_KEY": "abc123", "GEMINI_MODEL": "gemini-x", "A": "1", "EMPTY": ""})

    def test_load_does_not_override(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".env"
            path.write_text("GEMINI_API_KEY=from-file\nGEMINI_MODEL=m-file\nEMPTY=\n", encoding="utf-8")
            env = {"GEMINI_API_KEY": "from-system"}
            loaded = dotenv.load([path, Path(d) / "missing.env"], env)
            self.assertEqual(env["GEMINI_API_KEY"], "from-system")  # 시스템 값이 우선
            self.assertEqual(env["GEMINI_MODEL"], "m-file")
            self.assertNotIn("EMPTY", env)
            self.assertEqual(loaded, ["GEMINI_MODEL"])

    def test_bom(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".env"
            path.write_bytes("﻿GEMINI_API_KEY=k\n".encode("utf-8"))  # 메모장이 붙이는 BOM
            env = {}
            dotenv.load([path], env)
            self.assertEqual(env, {"GEMINI_API_KEY": "k"})


if __name__ == "__main__":
    unittest.main()
