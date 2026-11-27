import unittest
from datetime import date, datetime
from sync_lottery import query_months, expected_date, merge, normalize, index_rows, validate_sequence, TZ

def draw(p,d,nums=None):
    return {"period":p,"date":d,"numbers":nums or [1,2,3,4,5]}

class SyncTests(unittest.TestCase):
    def test_normal_months(self):
        self.assertEqual(query_months(date(2026,11,26),date(2026,11,27)),["2026-10","2026-11"])
    def test_catchup_year_boundary(self):
        self.assertEqual(query_months(date(2025,11,29),date(2026,2,1)),["2025-11","2025-12","2026-01","2026-02"])
    def test_excessive_catchup(self):
        with self.assertRaises(ValueError): query_months(date(2020,1,1),date(2026,2,1))
    def test_expected_cutoff(self):
        self.assertEqual(expected_date("lotto649",datetime(2026,11,27,20,tzinfo=TZ)),date(2026,11,24))
        self.assertEqual(expected_date("lotto649",datetime(2026,11,27,23,tzinfo=TZ)),date(2026,11,27))
    def test_append_preserves(self):
        a=draw("115000001","2026-01-01")
        b=draw("115000002","2026-01-02")
        c=draw("114000001","2025-01-01")
        result,added,overlap=merge("daily539",{a["period"]:a,c["period"]:c},[a,b],["2026-01"])
        self.assertEqual(result,[c,a,b])
        self.assertEqual((added,overlap),(1,1))
    def test_conflict(self):
        a=draw("115000001","2026-01-01")
        with self.assertRaises(ValueError): merge("daily539",{a["period"]:a},[draw(a["period"],a["date"],[1,2,3,4,6])],["2026-01"])
    def test_missing_overlap(self):
        a=draw("115000001","2026-01-01")
        with self.assertRaises(ValueError): merge("daily539",{a["period"]:a},[],["2026-01"])
    def test_duplicate(self):
        a=draw("115000001","2026-01-01")
        with self.assertRaises(ValueError): merge("daily539",{},[a,a],["2026-01"])
        with self.assertRaises(ValueError): index_rows("daily539",[a,a])
    def test_invalid_future_and_numbers(self):
        raw={"period":115000001,"lotteryDate":"2026-01-02","drawNumberSize":[1,2,3,4,5]}
        with self.assertRaises(ValueError): normalize("daily539",raw,"2026-01",date(2026,1,1))
        raw["drawNumberSize"]=[1,2,3,4,40]
        with self.assertRaises(ValueError): normalize("daily539",raw,"2026-01",date(2026,1,3))
    def test_missing_year(self):
        with self.assertRaises(ValueError): validate_sequence("daily539",[draw("115000001","2026-01-01")],date(2026,11,27))

if __name__=="__main__": unittest.main()
