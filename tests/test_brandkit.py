import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import brandkit as B


class PlanTests(unittest.TestCase):
    def sizes(self, brand):
        return {n: (w, h) for n, w, h, _k, _a in B.plan(brand)}

    def test_banners_only_where_used(self):
        banner = lambda b: {n for n in self.sizes(b) if 'banner' in n or n.endswith(('header.png', 'cover.png'))}
        self.assertEqual(banner('AdoptDontShop'), {'facebook_cover.png'})
        self.assertEqual(banner('CreatrGrid'), {'x_header.png'})
        self.assertEqual(banner('ideaSquared'), {'linkedin_company_banner.png', 'linkedin_company_banner@2x.png',
                                                 'linkedin_personal_banner.png', 'facebook_cover.png'})

    def test_banner_sizes(self):
        s = self.sizes('ideaSquared')
        self.assertEqual(s['linkedin_company_banner.png'], (1128, 191))
        self.assertEqual(s['linkedin_company_banner@2x.png'], (2256, 382))
        self.assertEqual(s['linkedin_personal_banner.png'], (1584, 396))
        self.assertEqual(s['facebook_cover.png'], (1640, 624))
        self.assertEqual(self.sizes('CreatrGrid')['x_header.png'], (1500, 500))

    def test_common_files(self):
        for b in B.BRANDS:
            s = self.sizes(b)
            self.assertEqual(s['avatar.png'], (1080, 1080))
            self.assertEqual(s['avatar_circle_preview.png'], (1080, 1080))
            self.assertEqual(s['link_preview.png'], (1200, 630))

    def test_highlights_per_pillar(self):
        expect = {'AdoptDontShop': {'highlight_know-how.png', 'highlight_rescues.png', 'highlight_the-build.png'},
                  'ideaSquared': {'highlight_how-we-build.png', 'highlight_updates.png', 'highlight_notes.png'},
                  'CreatrGrid': {'highlight_why.png', 'highlight_how-it-works.png', 'highlight_updates.png'}}
        for b, names in expect.items():
            s = self.sizes(b)
            self.assertEqual({n for n in s if n.startswith('highlight_')}, names)
            for n in names: self.assertEqual(s[n], (1080, 1920))

    def test_no_duplicates_and_safe_areas_inside_banners(self):
        for b in B.BRANDS:
            names = [i[0] for i in B.plan(b)]
            self.assertEqual(len(names), len(set(names)))
        for n, sp in B.BANNERS.items():
            x0, y0, x1, y1 = sp['safe']
            self.assertTrue(0 <= x0 < x1 <= sp['w'] // sp['k'] and 0 <= y0 < y1 <= sp['h'] // sp['k'], n)


if __name__ == '__main__':
    unittest.main()
