"""특징 속성(머리·눈·성격) 테스트. 네트워크를 쓰지 않는다."""
import datetime as dt
import json
import unittest

from the_archive import namu, traits
from the_archive.model import Character, Trait
from the_archive.render import render
from the_archive.works import get_work

from test_archive import SAMPLE, FakeClient
from test_sources import official_source


class TraitsTest(unittest.TestCase):
    def setUp(self):
        self.page = namu.parse_page(SAMPLE, "x")
        self.sources = [namu.to_source(self.page), official_source()]

    def test_validate(self):
        data = {
            "머리": [{"value": "은색", "source": 1, "quote": "머리카락은 은발이고"},
                   {"value": "검정", "source": 1, "quote": "머리카락은 은발이고"}],  # 머리는 하나만
            "눈": [{"value": "보라", "source": 1, "quote": "눈동자는 보라색이다"}],  # 출처에 없음
            "성격": [{"value": "냉철", "source": 3, "quote": "남쪽 마을을 오가며 수련한다"},  # 없는 번호 → 2번 출처로 고침
                   {"value": "차갑고 침착함", "source": 2, "quote": "차갑고 침착한 성격의 검사이다"}],
        }
        kept, dropped = traits.validate(data, self.sources)
        self.assertEqual([(t.key, t.value, t.source) for t in kept], [("머리", "은색", 0), ("성격", "냉철", 1)])
        self.assertEqual(len(dropped), 2)

    def test_extract_with_fake_client(self):
        data = {"머리": [{"value": "은색", "source": 1, "quote": "머리카락은 은발이고"}], "눈": [], "성격": []}
        client = FakeClient(data)
        kept, _, used = traits.extract(self.sources, "테스트캐릭터", model="m", client=client)
        self.assertEqual(used, "m")
        self.assertEqual(kept[0].value, "은색")
        self.assertIn("머리카락의 주된 색", client.prompt)

    def test_render_properties(self):
        work = get_work("명조")
        char = Character("테스트캐릭터", work.title, self.page, sources=self.sources,
                         traits=[Trait("머리", "은발", "머리카락은 은발이고", 0),
                                 Trait("성격", "냉철", "차갑고 침착한 성격의 검사이다", 1),
                                 Trait("성격", "침착", "차갑고 침착한 성격의 검사이다", 1)])
        md = render(char, work, dt.date(2026, 11, 28))
        fm = md.split("\n---\n")[0]
        self.assertIn("취향:\n머리: 은발\n눈:\n성격:\n  - 냉철\n  - 침착", fm)
        self.assertIn('> - [ ] [핵심] 성격: 냉철 (속성)[^1] — "차갑고 침착한 성격의 검사이다"', md)
        self.assertIn('> - [ ] [보조] 머리: 은발 (속성)[^2] — "머리카락은 은발이고"', md)

    def test_render_empty_keys(self):
        work = get_work("명조")
        char = Character("t", work.title, self.page)
        fm = render(char, work, dt.date(2026, 11, 28)).split("\n---\n")[0]
        self.assertIn("취향:\n머리:\n눈:\n성격:", fm)


class AliasTest(unittest.TestCase):
    def test_alias_order(self):
        from the_archive.model import Page
        from the_archive.render import aliases

        ba = Page("t", "u", "", "", [], {}, ["砂狼 シロコ", "砂狼 白子", "Sunaookami Shiroko"], [], {})
        self.assertEqual(aliases(Character("스나오오카미 시로코", "블루 아카이브", ba)),
                         ["시로코", "Sunaookami Shiroko", "砂狼シロコ"])
        ww = Page("t", "u", "", "", [], {}, ["千咲", "Chisa"], [], {})
        self.assertEqual(aliases(Character("치사", "명조", ww, full_name="쿠치바 치사")),
                         ["쿠치바 치사", "Chisa", "千咲"])
        self.assertEqual(aliases(Character("치사", "명조", ww)), ["Chisa", "千咲"])
        hsin = Page("t", "u", "", "", [], {}, ["心", "Hsin"], [], {})  # 띄어쓰기가 있어도 성+이름이 아님
        self.assertEqual(aliases(Character("여우의 별자리", "명조", hsin)), ["Hsin", "心"])


if __name__ == "__main__":
    unittest.main()
