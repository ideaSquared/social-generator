# Brand kit

`python brandkit.py --out <dir> [--brand NAME]` writes `<dir>/<Brand>/brandkit/*.png` for AdoptDontShop, ideaSquared and CreatrGrid. Logos, lock-ups and backgrounds come from the helpers in `render.py`. Generated images are not committed.

Banners keep their content inside a safe area: clear of the profile picture overlapping the bottom-left and of the mobile crops.

| File | Size | Brands | Upload to |
|---|---|---|---|
| `linkedin_company_banner.png` | 1128x191 | ideaSquared | LinkedIn company page, cover image |
| `linkedin_company_banner@2x.png` | 2256x382 | ideaSquared | Same slot, higher resolution (use if LinkedIn accepts it) |
| `linkedin_personal_banner.png` | 1584x396 | ideaSquared | LinkedIn personal profile, background photo |
| `x_header.png` | 1500x500 | CreatrGrid | X profile header |
| `facebook_cover.png` | 1640x624 | AdoptDontShop, ideaSquared | Facebook page cover photo |
| `avatar.png` | 1080x1080 | all | Profile picture on Instagram, Facebook, TikTok, LinkedIn, X (platforms crop to a circle) |
| `avatar_circle_preview.png` | 1080x1080 | all | Not uploaded; preview of the circular crop |
| `highlight_<pillar>.png` | 1080x1920 | all | Instagram story highlight covers, one per pillar |
| `link_preview.png` | 1200x630 | all | Website Open Graph image (`og:image`) shown when the link is shared |

Highlight covers: AdoptDontShop `know-how`, `rescues`, `the-build`; ideaSquared `how-we-build`, `updates`, `notes`; CreatrGrid `why`, `how-it-works`, `updates`. Upload each as a highlight cover and crop to the circle; the label sits in the centre.

Banners are generated only for the platforms each brand uses: AdoptDontShop (Instagram, Facebook, TikTok), ideaSquared (LinkedIn, Instagram, Facebook, TikTok), CreatrGrid (Instagram, TikTok, X).
