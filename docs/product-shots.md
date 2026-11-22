# Product shots

`product_shots.py` turns your own product pages into on-brand social graphics without any recording or photography. It screenshots each page with headless Chrome, then places the capture in a phone bezel or a browser window on the AdoptDontShop, ideaSquared or CreatrGrid background, with the brand lock-up and an optional headline.

No AI and nothing invented: the only text on a graphic is the `headline` and `sub` from the config, the page host in the browser URL pill, and the brand lock-up.

## Usage

```
python product_shots.py shots.example.json --out out/product-shots
python product_shots.py shots.example.json --out out/product-shots --only creatrgrid-alex-phone
```

Output in `--out`:

- `raw/<name>.png`: the capture at device size times scale (phone 1170x2532, desktop 2880x1800)
- `<name>_post.png` (1080x1350), `<name>_story.png` (1080x1920), `<name>_landscape.png` (1600x900)

The exit code is 1 if any shot failed (each failure is printed with its reason), 2 for config errors. Other shots still complete.

Requirements: Python 3, Pillow, and Chrome (set `CHROME` if it is not on your path), the same as `render.py`.

## Needs internet access

Live pages are fetched by Chrome on the machine running the tool, so it needs internet access to reach them. Run it locally or in GitHub Actions. It cannot work from a sandbox with no outbound network. A quick reachability check runs first for http(s) URLs (skip it with `--no-preflight`).

Only point it at pages you own or have permission to show. It will happily screenshot any public page, but you should not publish other people's work as your product.

## Config format

A JSON list of shots (or `{"shots": [...]}`). Unknown keys are rejected so typos are caught.

| Key | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Letters, digits, `-`, `_`. Used in file names; must be unique. |
| `brand` | yes | `AdoptDontShop`, `ideaSquared` or `CreatrGrid`. |
| `url` | yes | `https://`, `http://` or `file://`. |
| `device` | yes | `phone` (390x844 CSS px, scale 3, mobile user agent) or `desktop` (1440x900, scale 2). |
| `wait_ms` | no | Virtual time Chrome allows for the page to settle. Default 4000. |
| `scroll_y` | no | CSS pixels to scroll down before the capture. Default 0. |
| `color_scheme` | no | `light` or `dark`. |
| `headline`, `sub` | no | Text for the composed graphics (max 160 characters). `sub` needs a `headline`. |
| `layouts` | no | Any of `post`, `story`, `landscape`. Default all three. |
| `check_blank` | no | Set `false` to disable blank detection for a deliberately sparse page. |

`shots.example.json` uses the real CreatrGrid demo pages and homepage. Headlines are brand text only: no statistics or claims.

## How it behaves

- **Waiting.** CreatrGrid is a client-rendered app, so the capture uses Chrome's `--virtual-time-budget=<wait_ms>`, which fast-forwards timers and lets network requests finish before the screenshot. If content is still missing, raise `wait_ms`. Content that needs real user interaction, or lazy-loads on scroll, will not appear.
- **Colour scheme.** Done through Chrome's `--blink-settings=preferredColorScheme` (0 dark, 1 light), so a page's `prefers-color-scheme` CSS responds. A site that stores its theme in local storage or a toggle will ignore it. Verified against a fixture page.
- **Scrolling.** Chrome's command line cannot scroll, so the window is made taller by `scroll_y` and the top `scroll_y` pixels are cropped off. Content using `100vh` or sticky headers can therefore differ slightly from a real scrolled view.
- **Sharpness.** The capture is only ever downscaled (with a high quality filter) to the displayed size. The planner asserts it never upscales.
- **No cropping of the page top.** Phone frames on post and story layouts run off the bottom edge of the canvas; the top of the page is always fully shown. Landscape layouts show the whole device.
- **Failing clearly.** A capture is rejected, with no composed output, when it is nearly uniform: a blank page, or Chrome's "This site can't be reached" page (which has about 3% non-background pixels; real pages are far above the 6% threshold). The rejected raw capture is kept in `raw/` for inspection. Unreachable hosts, HTTP errors, Chrome failures and timeouts are also reported per shot.

## Tests

`python -m unittest discover -s tests` covers config validation, layout planning and blank detection with generated images (no Chrome). The two pages under `tests/fixtures/` (`creator.html`, a masonry creator page with dark-mode CSS, and `client_rendered.html`, which only renders after 1.5 s of JavaScript) are for manual runs against a local Chrome, for example via `file://` URLs.
