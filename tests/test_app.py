"""Windows integration smoke test. Creates a temporary, non-user profile."""
import os
import tempfile
import unittest
from pathlib import Path

@unittest.skipUnless(os.name == 'nt', 'Windows overlay only')
class AppTests(unittest.TestCase):
    def test_overlay_and_task_lifecycle(self):
        import app
        with tempfile.TemporaryDirectory() as folder:
            original = app.DATA
            app.DATA = Path(folder) / 'profile.json'
            gui = app.App()
            try:
                gui.root.withdraw()
                gui.start()
                gui.root.update()
                hwnd = app.user32.GetAncestor(gui.hud.winfo_id(), 2)
                style = app.get_style(hwnd, -20)
                self.assertTrue(style & 0x20, 'Mouse passthrough missing')
                self.assertTrue(style & 0x08000000, 'No-activation style missing')
                gui.pause()
                self.assertIsNone(gui.timer.deadline)
                gui.pause()
                self.assertIsNotNone(gui.timer.deadline)
                for color in app.COLORS:
                    gui.color.set(color)
                    for noise in ['Low', 'Medium', 'High']:
                        gui.noise.set(noise)
                        for cover in ['Light', 'Deep']:
                            gui.cover.set(cover); gui.draw()
                gui.timer.deadline = gui.timer.clock() - 1
                gui.tick()
                self.assertTrue(gui.awaiting)
                gui.finish()
                self.assertEqual(gui.profile['points'], 75)
                gui.finish()
                self.assertEqual(len(gui.profile['history']), 1)
                gui.start_break(5); gui.finish()
                self.assertEqual(gui.profile['points'], 75)
                gui.start(); gui.abort()
                self.assertEqual(len(gui.profile['history']), 1)
                self.assertTrue(app.DATA.exists())
                gui.profile['pending_session']={'total':1500,'remaining':1033,'task':{
                    'goal':'恢复测试','difficulty':'标准','story':None,'break':False,'started':'2026-10-20 20:00:00'}}
                gui.restore_session()
                self.assertEqual(gui.timer.display(),'17:13')
                self.assertIsNone(gui.timer.deadline)
                self.assertEqual(gui.active['goal'],'恢复测试')
                gui.abort()
                self.assertIsNone(gui.profile['pending_session'])
            finally:
                gui.close()
                app.DATA = original
