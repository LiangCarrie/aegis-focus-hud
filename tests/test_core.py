import tempfile
import unittest
from pathlib import Path
from core import Timer, load_story, reward, rank, save_json

class CoreTests(unittest.TestCase):
    def test_pause_and_resume_excludes_paused_time(self):
        now = [0]
        t = Timer(1500, lambda: now[0]); t.start()
        now[0] = 60; t.pause(); self.assertEqual(t.left(), 1440)
        now[0] = 600; t.start(); now[0] = 660
        self.assertEqual(t.left(), 1380)
        now[0] = 10000; self.assertEqual(t.display(), '00:00')

    def test_story_formats_and_reject_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'story.md'; p.write_text('# 主线\n## 一\n背景\n## 二\n后续', encoding='utf-8')
            self.assertEqual(len(load_story(p)['missions']), 2)
            p = Path(d)/'story.json'; save_json(p, {'title':'主线','missions':[{'title':'一','briefing':'背景'}]})
            self.assertEqual(load_story(p)['missions'][0]['briefing'], '背景')
            save_json(p, {'missions': [1]})
            with self.assertRaises(ValueError): load_story(p)

    def test_rewards_and_ranks(self):
        self.assertEqual(reward(1500, '标准'), 75)
        self.assertEqual(reward(0, '挑战'), 0)
        self.assertEqual(reward(59, '轻度'), 1)
        self.assertEqual(rank(100), '黄阶 · 行动员')

if __name__ == '__main__': unittest.main()
