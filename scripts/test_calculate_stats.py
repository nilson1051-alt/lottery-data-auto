import unittest
from calculate_stats import statistics, structure, percentile, build
class StatsTests(unittest.TestCase):
    def test_frequency_skip_lift(self):
        s=statistics([[1,2],[1,3],[2,3],[1,2]],3,2)
        self.assertEqual(s["numbers"]["1"]["count"],3)
        self.assertEqual(s["numbers"]["3"]["skip"],1)
        self.assertAlmostEqual(s["pair_lift"]["1-2"]["lift"],8/9)
        self.assertAlmostEqual(s["numbers"]["1"]["ewma"],1+.5+2**(-1.5))
    def test_zero_pairs(self):
        s=statistics([[1,2],[3,4]],4,2)
        self.assertEqual(s["pair_lift"]["1-3"]["lift"],0)
    def test_separate_zone(self):
        s=statistics([[1],[2],[1]],8,None,pairs=False)
        self.assertIsNone(s["pair_lift"])
        self.assertIsNone(s["hot"])
        self.assertIsNone(s["numbers"]["8"]["skip"])
    def test_structure(self):
        s=structure([1,2,4,7,11],39)
        self.assertEqual(s["sum"],25)
        self.assertEqual(s["span"],10)
        self.assertEqual(s["adjacent_pairs"],1)
        self.assertEqual(s["max_same_tail"],2)
        self.assertEqual(s["ac"],len({1,3,6,10,2,5,9,3,7,4})-4)
    def test_percentile(self):
        self.assertAlmostEqual(percentile([0,10],.3),3)
    def test_coverage(self):
        s=statistics([[1,2],[2,3],[3,4]],4,2)
        self.assertGreaterEqual(s["coverage_actual"],.65)
        self.assertEqual(s["lift_high_threshold"],1.20)
        self.assertEqual(s["lift_min_pair_count"],30)
    def test_high_lift_and_support(self):
        s=statistics([[1,2]]*30+[[3,4]]*30,4,240)
        self.assertEqual(s["high_lift_pairs"],["1-2","3-4"])
        self.assertTrue(s["pair_lift"]["1-2"]["high"])
        s=statistics([[1,2]]*29+[[3,4]]*29,4,240)
        self.assertEqual(s["high_lift_pairs"],[])
    def test_strong_triangle(self):
        s=statistics([[1,2,3]]*30+[[4,5,6]]*30,6,240)
        self.assertEqual(s["strong_triangles"],[[1,2,3],[4,5,6]])
    def test_superlotto_half_lives(self):
        r=build("superlotto638",[{"period":"115000001","date":"2026-01-01","first_zone":[1,2,3,4,5,6],"second_zone":1},{"period":"115000002","date":"2026-01-05","first_zone":[7,8,9,10,11,12],"second_zone":2}],"test")
        self.assertEqual(r["main"]["half_life"],240)
        self.assertEqual(r["second_zone"]["half_life"],240)
        self.assertIsNone(r["second_zone"]["pair_lift"])
        self.assertIsNone(r["second_zone"]["lift_high_threshold"])
        self.assertAlmostEqual(r["second_zone"]["numbers"]["1"]["ewma"],2**(-1/240))
if __name__=="__main__":unittest.main()
