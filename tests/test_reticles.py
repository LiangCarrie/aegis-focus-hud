import unittest
from PIL import ImageChops
from reticles import STYLES,render_reticle
from hud_renderer import VisorRenderer,HUDConfig,HUDState

class ReticleTests(unittest.TestCase):
    def test_distinct_styles_transparent_margins_and_sizes(self):
        signatures=set()
        for style in STYLES.values():
            for size in [.6,1,1.6]:
                im=render_reticle(style,size=size)
                box=im.getchannel('A').getbbox()
                self.assertIsNotNone(box)
                self.assertGreater(box[0],0)
                self.assertLess(box[2],im.width)
            signatures.add(render_reticle(style).tobytes())
        self.assertEqual(len(signatures),8)

    def test_optional_motion_preserves_center(self):
        for style in ['ring','orbit']:
            first=render_reticle(style,t=0,animate=True)
            second=render_reticle(style,t=5,animate=True)
            self.assertNotEqual(first.tobytes(),second.tobytes())
            mid=first.width//2
            region=(mid-5,mid-5,mid+6,mid+6)
            self.assertEqual(first.crop(region).tobytes(),second.crop(region).tobytes())
            self.assertEqual(render_reticle(style,t=0).tobytes(),render_reticle(style,t=5).tobytes())

    def test_style_changes_do_not_rebuild_visor(self):
        r=VisorRenderer(960,540)
        for style in STYLES.values():r.render(HUDConfig(reticle_style=style),HUDState(),10)
        self.assertEqual(r.build_count,1)
