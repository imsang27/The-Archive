"""여러 출처(나무위키 + 공식 라운지 DB + 영문 위키)를 다루는 부분의 테스트. 네트워크를 쓰지 않는다."""
import datetime as dt
import unittest

from the_archive import bawiki, gemini, namu, rules
from the_archive.model import Character, Fact, Source
from the_archive.naver_db import description_to_lines, _norm_name
from the_archive.render import choose_core, render
from the_archive.works import get_work

from test_archive import SAMPLE


def official_source() -> Source:
    lines = description_to_lines(
        "〈유니버스 인류 기록: 뒤얽힌 별들〉 - 테스트<BR/><BR/>"
        "\"따옴표 대사는 건너뛴다.\" —— 테스트<BR/><BR/>"
        "◆아카이브>><BR/>테스트캐릭터는 차갑고 침착한 성격의 검사이다.<BR/>"
        "그녀는 북쪽 마을에서 &amp; 남쪽 마을을 오가며 수련한다.")
    return Source("naver_db", "네이버 게임 공식 라운지 DB", "테스트", "https://game.naver.com/x", "", 1,
                  "\n".join(lines), {"공식 소개": lines}, "공식 소개문")


class NaverDBTest(unittest.TestCase):
    def test_description_lines(self):
        lines = official_source().sections["공식 소개"]
        self.assertEqual(lines[0], "〈유니버스 인류 기록: 뒤얽힌 별들〉 - 테스트")
        self.assertIn("그녀는 북쪽 마을에서 & 남쪽 마을을 오가며 수련한다.", lines)
        self.assertNotIn("", lines)

    def test_name_normalize(self):
        self.assertEqual(_norm_name("양양 · 현령"), _norm_name("양양·현령"))


class BAWikiTest(unittest.TestCase):
    def test_title_candidates(self):
        self.assertEqual(bawiki.title_candidates(["砂狼 シロコ", "Sunaookami Shiroko"]),
                         ["Shiroko", "Sunaookami Shiroko"])
        self.assertEqual(bawiki.title_candidates(["小鳥遊ホシノ"]), [])


class MultiSourceTest(unittest.TestCase):
    def setUp(self):
        self.page = namu.parse_page(SAMPLE, "x")
        self.sources = [namu.to_source(self.page), official_source()]

    def test_validate_reassigns_source(self):
        items = [
            # 출처 번호를 1(나무위키)로 잘못 적었지만 인용은 공식 소개문에만 있다 → 2번 출처로 고친다
            {"section": "기타", "text": "남북을 오가며 수련한다.", "summary": "수련", "source": 1,
             "quote": "남쪽 마을을 오가며 수련한다"},
            {"section": "성격", "text": "침착하다.", "summary": "침착", "source": 2,
             "quote": "차갑고 침착한 성격의 검사이다"},
            {"section": "성격", "text": "x", "summary": "x", "source": 9, "quote": "어디에도 없는 문장입니다"},
        ]
        kept, dropped = gemini.validate(items, self.sources, 4)
        self.assertEqual([f.source for f in kept], [1, 1])
        self.assertEqual(len(dropped), 1)

    def test_prompt_marks_official(self):
        text = gemini.build_source(self.sources)
        self.assertIn("[출처 1] 나무위키", text)
        self.assertIn("[출처 2 (공식)] 네이버 게임 공식 라운지 DB", text)

    def test_core_is_official_and_footnotes(self):
        facts = [Fact("성격", "침착하다.", "침착", "차갑고 침착한 성격의 검사이다", 1),
                 Fact("외형", "은발이다.", "은발", "머리카락은 은발이고", 0)]
        self.assertEqual(choose_core(self.sources, facts), 1)
        work = get_work("명조")
        char = Character("테스트캐릭터", work.title, self.page, facts=facts, sources=self.sources)
        md = render(char, work, dt.date(2026, 11, 28))
        ref_block = md.split("Reference:")[1].split("Source_date")[0]
        self.assertLess(ref_block.index("네이버 게임 공식 라운지 DB"), ref_block.index("나무위키"))
        self.assertIn("- 침착하다.[^1]", md)  # 핵심 출처(공식)가 [^1]
        self.assertIn("- 은발이다.[^2]", md)
        self.assertIn("> - [ ] [핵심] 침착 (2.)[^1]", md)
        self.assertIn("> - [ ] [보조] 은발 (3.)[^2]", md)
        self.assertIn("Confidence: 60", md)  # S=40, C=20, R=0 (공식 DB에 날짜 없음)
        self.assertIn("Source_date:\n", md)

    def test_namu_only_core(self):
        facts = [Fact("외형", "은발이다.", "은발", "머리카락은 은발이고", 0)]
        self.assertEqual(choose_core(self.sources[:1], facts), 0)

    def test_extract_official_and_dedupe(self):
        facts = rules.extract_official(self.sources[1], 1)
        texts = [f.text for f in facts]
        self.assertTrue(all(f.source == 1 for f in facts))
        self.assertIn("테스트캐릭터는 차갑고 침착한 성격의 검사이다.", texts)
        self.assertFalse(any("따옴표" in t or t.startswith("〈") for t in texts))
        for f in facts:
            self.assertIn(f.quote, self.sources[1].text)
        dup = Fact("성격", "테스트캐릭터는 차갑고  침착한 성격의 검사이다", "x", "y", 0)
        self.assertEqual(len(rules.dedupe(facts + [dup])), len(facts))


if __name__ == "__main__":
    unittest.main()
