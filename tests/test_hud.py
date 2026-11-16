import unittest
from hud_renderer import HUDConfig, HUDState, VisorRenderer

class VisorTests(unittest.TestCase):
    def test_work_aperture_is_transparent_in_all_modes(self):
        renderer=VisorRenderer(960,540)
        state=HUDState()
        for theme in ['blue','red','yellow','green']:
            for density in range(3):
                for deep in [False,True]:
                    frame=renderer.render(HUDConfig(theme=theme,density=density,deep=deep,crosshair=False),state,8)
                    # The central 54% width / 60% height is genuinely alpha=0.
                    self.assertEqual(frame.getchannel('A').crop((220,110,740,430)).getbbox(),None)
                    self.assertGreater(frame.getchannel('A').getextrema()[1],200)

    def test_motion_freeze_and_static_cache(self):
        renderer=VisorRenderer(960,540)
        state=HUDState()
        config=HUDConfig(motion=False)
        first=renderer.render(config,state,1)
        second=renderer.render(config,state,20)
        self.assertEqual(first.tobytes(),second.tobytes())
        self.assertEqual(renderer.build_count,1)
        config=HUDConfig(motion=True)
        first=renderer.render(config,state,1)
        second=renderer.render(config,state,20)
        self.assertNotEqual(first.tobytes(),second.tobytes())
        self.assertEqual(renderer.build_count,1)

    def test_short_and_tall_layouts_do_not_overlap(self):
        for size in [(1920,1080),(1280,800),(1720,720)]:
            renderer=VisorRenderer(*size)
            renderer.render(HUDConfig(),HUDState(),4)
            self.assertGreater(renderer.radar_y-renderer.radius-44,202)
            self.assertGreater(renderer.globe_y-renderer.radius-48,246)
            if renderer.has_aux:
                self.assertLess(renderer.buffer_y+118,renderer.signal_y)
                self.assertLess(renderer.reserve_y+87,renderer.terrain_y)
