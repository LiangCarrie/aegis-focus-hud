import unittest
from terrain_scanner import CaveScanner

class CaveTests(unittest.TestCase):
    def test_seed_and_continuous_route(self):
        a,b=CaveScanner(42),CaveScanner(42)
        self.assertEqual(a.section(10),b.section(10))
        self.assertNotEqual(a.section(10),CaveScanner(43).section(10))
        for z in (-22,0,22,44,220):
            left,right=a.center(z-0.0001),a.center(z+0.0001)
            self.assertLess(sum(abs(x-y) for x,y in zip(left,right)),.001)

    def test_bounded_geometry_and_motion(self):
        cave=CaveScanner(42)
        args=((220,80),0,(66,218,255),(161,113,255))
        first=cave.render(*args)
        self.assertEqual(first.tobytes(),cave.render(*args).tobytes())
        self.assertNotEqual(first.tobytes(),cave.render(args[0],5,*args[2:]).tobytes())
        for i in range(1000): cave.section(i)
        self.assertLessEqual(cave.section.cache_info().currsize,256)
