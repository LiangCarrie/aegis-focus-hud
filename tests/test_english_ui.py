import unittest
from english_ui import migrate_settings, translate

class EnglishUITests(unittest.TestCase):
    def test_legacy_settings_migrate_without_changing_other_data(self):
        old={'color':'红 · 危机','noise':'中','cover':'深度','reticle_style':'轨道核心','brightness':73}
        new=migrate_settings(old)
        self.assertEqual(new,dict(color='Red · Critical',noise='Medium',cover='Deep',reticle_style='Orbital Core',brightness=73))
        self.assertEqual(old['noise'],'中')
        self.assertEqual(migrate_settings(new),new)
        self.assertEqual(translate('标准'),'Standard')
