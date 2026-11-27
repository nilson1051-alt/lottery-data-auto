import unittest
from calculate_stats import statistics, structure, percentile
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
        self.assertIsNone(s["lift_high_threshold"])
if __name__=="__main__":unittest.main()
