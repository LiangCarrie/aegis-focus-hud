import json
import tempfile
import unittest
from pathlib import Path
import app

class LanguageTests(unittest.TestCase):
    def test_switch_preserves_session_and_selects_matching_story(self):
        with tempfile.TemporaryDirectory() as folder:
            old_base,old_data=app.BASE,app.DATA
            app.BASE=Path(folder);app.DATA=app.BASE/'profile.json'
            (app.BASE/'storylines/en').mkdir(parents=True)
            (app.BASE/'audio').mkdir()
            for lang,title in [('','中文故事'),('en','English Story')]:
                (app.BASE/'storylines'/lang/'shared.json').write_text(json.dumps({'title':title,'missions':[{'title':title+' 1','briefing':title+' briefing','objective':'original text'}]}),encoding='utf-8')
            gui=app.App()
            try:
                gui.root.withdraw()
                self.assertEqual(gui.language,'zh')
                gui.story.set(next(iter(gui.stories)));gui.select_story()
                gui.start();gui.pause()
                timer=gui.timer;remaining=timer.left()
                gui.language_choice.set('English');gui.change_language()
                self.assertIs(gui.timer,timer)
                self.assertEqual(timer.left(),remaining)
                self.assertEqual(gui.selected_mission()[0],'shared.json')
                self.assertIn('English Story',gui.brief.get('1.0','end'))
                self.assertEqual(gui.profile['settings']['language'],'en')
                gui.language_choice.set('中文');gui.change_language()
                self.assertIn('中文故事',gui.brief.get('1.0','end'))
                self.assertEqual(gui.noise.get(),'High')
                self.assertEqual(gui.root.getvar(str(gui.noise)),'高')
                gui.abort()
            finally:
                gui.close();app.BASE,app.DATA=old_base,old_data
