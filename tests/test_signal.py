import unittest
from signal_bus import SignalBus

class SignalTests(unittest.TestCase):
    def test_history_seed_and_bounds(self):
        a,b=SignalBus(42),SignalBus(42)
        first,_=a.frame(10)
        second,_=a.frame(10+1/48)
        self.assertEqual(first[1:],second[:-1])
        self.assertEqual(first,b.frame(10)[0])
        self.assertNotEqual(first,SignalBus(43).frame(10)[0])
        for i in range(4000):
            self.assertTrue(all(abs(v)<1.1 for v in a.sample(i)))
        self.assertLessEqual(a.sample.cache_info().currsize,1024)

    def test_energy_tracks_signal(self):
        a=SignalBus(42)
        self.assertEqual(a.levels([(0,0,0)]*100),[0]*25)
        self.assertEqual(a.levels([(1,1,1)]*100),[1]*25)
