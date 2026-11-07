"""Run: .venv/bin/python -m unittest discover app/tests   (no network, no mock server needed)"""
import os
import tempfile
import unittest

os.environ.setdefault("APP_SECRET", "test-secret")

from app import links, messages  # noqa: E402
from app.engine import Engine, NotAllowed  # noqa: E402
from app.hours import is_valid, merge_holiday_hours  # noqa: E402
from app.learning import Learning  # noqa: E402

SECRET = b"unit-test"


class Links(unittest.TestCase):
    def test_roundtrip(self):
        t = links.sign({"c": "case1"}, secret=SECRET, now=1000)
        self.assertEqual(links.verify(t, secret=SECRET, now=1001)["c"], "case1")

    def test_tampered(self):
        t = links.sign({"c": "case1"}, secret=SECRET, now=1000)
        raw, sig = t.split(".")
        with self.assertRaises(links.TokenError):
            links.verify(raw[:-2] + "AA." + sig, secret=SECRET, now=1001)

    def test_expired(self):
        t = links.sign({"c": "case1"}, ttl=10, secret=SECRET, now=1000)
        with self.assertRaises(links.TokenError):
            links.verify(t, secret=SECRET, now=2000)


class Hours(unittest.TestCase):
    base = {"monday": {"openIntervals": [{"start": "09:00", "end": "17:00"}]},
            "holidayHours": [{"date": "2026-01-01", "isClosed": True},
                             {"date": "2026-12-31", "openIntervals": [{"start": "10:00", "end": "14:00"}]}]}

    def test_merge_keeps_future_drops_past_sorts(self):
        out = merge_holiday_hours(self.base, {"2026-12-24": "closed", "2026-12-06": "10:00-15:00"}, today="2026-11-06")
        self.assertEqual([h["date"] for h in out["holidayHours"]], ["2026-12-06", "2026-12-24", "2026-12-31"])
        self.assertEqual(out["monday"], self.base["monday"])
        self.assertTrue(out["holidayHours"][1]["isClosed"])

    def test_merge_replaces_same_date_and_undo_removes(self):
        out = merge_holiday_hours(self.base, {"2026-12-31": "closed"}, today="2026-11-06")
        self.assertEqual(sum(h["date"] == "2026-12-31" for h in out["holidayHours"]), 1)
        out2 = merge_holiday_hours(out, {"2026-12-31": None}, today="2026-11-06")
        self.assertNotIn("2026-12-31", [h["date"] for h in out2["holidayHours"]])

    def test_valid(self):
        for ok in ("closed", "09:00-17:00", "10:00-14:00,17:00-22:00", "18:00-02:00"):
            self.assertTrue(is_valid(ok), ok)
        for bad in ("9-17", "", "25:00-26:00"):
            self.assertFalse(is_valid(bad), bad)


ITEM = {"date": "2026-12-24", "day_key": "XMAS_EVE", "action": "SUGGEST", "hours": "10:00-14:00",
        "shown_hours": "09:00-18:00", "confidence": 0.9, "mode": "suggest", "basis": "LAST_YEAR",
        "reasons": ["Last season the owner entered 10:00-14:00."], "evidence": {"last_year": "10:00-14:00"},
        "public_holiday": False}


class Messages(unittest.TestCase):
    def test_four_languages(self):
        for lang in ("fi", "sv", "nb", "en"):
            m = messages.compose({"lang": lang, "first": "Aino", "name": "Kahvila Testi", "views": 1234}, [ITEM],
                                 "https://x/s/abc")
            self.assertIn("https://x/s/abc", m["text"])
            self.assertEqual(len(m["buttons"]), 3)
            self.assertIn("Aino", m["text"])


class Learn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.l = Learning(os.path.join(self.tmp, "l.json"))

    def test_decline_open_as_usual_suppresses(self):
        self.l.learn("X1", ITEM, "decline", reason="open_as_usual")
        s = self.l.adjust("X1", dict(ITEM))
        self.assertNotEqual(s["action"], "SUGGEST")

    def test_edit_is_remembered(self):
        self.l.learn("X1", ITEM, "edit", final_hours="10:00-13:00")
        s = self.l.adjust("X1", dict(ITEM))
        self.assertEqual(s["hours"], "10:00-13:00")


class FakeYext:
    is_mock = True

    def __init__(self):
        self.puts = []


class FakeApplier:
    def __init__(self):
        self.calls = []

    def apply(self, eid, changes):
        self.calls.append((eid, changes))
        return {"previous": {}, "warnings": []}


class NoWriteWithoutApproval(unittest.TestCase):
    def test_write_requires_authority(self):
        tmp = tempfile.mkdtemp()
        e = Engine(yext=FakeYext(), learning=Learning(os.path.join(tmp, "l.json")),
                   state_path=os.path.join(tmp, "s.json"), detect=FakeYext())
        e.applier = FakeApplier()
        for bad in ({}, {"kind": "system"}, {"kind": "owner_decision"}):
            with self.assertRaises(NotAllowed):
                e._write("X1", {"2026-12-24": "closed"}, bad)
        self.assertEqual(e.applier.calls, [])
        e._write("X1", {"2026-12-24": "closed"}, {"kind": "owner_decision", "decision_id": "d1"})
        self.assertEqual(len(e.applier.calls), 1)


if __name__ == "__main__":
    unittest.main()


class Reviews(unittest.TestCase):
    def test_bad_review_gets_reply_in_its_language(self):
        from app import reviews as rv
        r = {"rating": 1, "content": "Det sto åpent på nett, men det var stengt.", "publisherId": "G"}
        self.assertTrue(rv.is_bad(r))
        d = rv.draft_reply(r, "Bakeri Fjord", "fi")
        self.assertEqual(d["lang"], "nb")
        self.assertIn("closed", d["topics"])
        self.assertIn("Bakeri Fjord", d["reply"])


class ChatEdit(unittest.TestCase):
    def test_parse_hours(self):
        from app.chat_edit import parse_hours as p
        self.assertEqual(p("8-14"), "08:00-14:00")
        self.assertEqual(p("10am to 4pm"), "10:00-16:00")
        self.assertEqual(p("10-14, 17-22"), "10:00-14:00,17:00-22:00")
        self.assertEqual(p("Closed"), "closed")
        self.assertIsNone(p("maybe later"))


class ReviewUrgency(unittest.TestCase):
    def test_scores(self):
        from app.review_monitor import urgency
        now = 1_800_000_000_000
        bad = {"rating": 1, "content": "Google said open but the door was locked", "publisherDate": now}
        good = {"rating": 5, "content": "Lovely coffee", "publisherDate": now - 10 * 86400000}
        self.assertGreaterEqual(urgency(bad, 1000, now)[0], 3)
        self.assertLess(urgency(good, 1000, now)[0], 3)


class DecisionsAndBestTime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.L = Learning(os.path.join(self.tmp, "learning.json"))

    def test_decisions_go_to_sqlite(self):
        from app.learning import db_rows
        self.L.record({"entity_id": "E1", "type": "owner request", "date": "2026-12-03", "final_hours": "closed",
                       "channel": "whatsapp chat"})
        rows = db_rows("E1", path=self.L.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["final_hours"], "closed")
        self.L.clear()
        self.assertEqual(db_rows("E1", path=self.L.db), [])

    def test_best_time_needs_three_replies(self):
        self.assertEqual(self.L.reply_profile("E1", "12-16")["window"], "12-16")
        for at in ("2026-11-02T05:10:00+00:00", "2026-11-03T05:40:00+00:00", "2026-11-04T06:20:00+00:00"):
            self.L.data["decisions"].append({"at": at, "entity_id": "E1", "type": "decision", "channel": "whatsapp"})
        rp = self.L.reply_profile("E1", "12-16")
        self.assertEqual(rp["window"], "07-09")  # 05:10-06:20 UTC = 07:10-08:20 Helsinki
        self.assertIn("learned from 3 replies", rp["source"])
