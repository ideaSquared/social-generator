# Roadmap

What to build next, in rough priority order. Nothing here needs AI unless it says so.

**Built:** PDF export, 9:16 story versions, text, stat and quote cards, video covers, alt text, motion in videos,
product screenshots, the brand kit, the review gallery, visual checks and the claims check.

**Decided against for now:** subtitles (the videos have no speech), 1:1 and 16:9 sizes (4:5 covers the feeds in use),
pricing card from the live site (prices are already in the sheet), design tokens sync (the design systems are not in this repo).

**Still open in sections 1 to 4:** scripted walkthrough videos and "What shipped" cards.

## 1. More asset types from the same sheet

| Idea | What it gives you | Notes |
|---|---|---|
| PDF export for carousels | LinkedIn carousels are uploaded as a PDF document, not images | Stitch each carousel's slides into one PDF |
| Extra sizes per asset | 1:1, 4:5, 9:16 and 16:9 from one row | Story versions of carousels come free with 9:16 |
| Text-post cards | Turn a LinkedIn or X text post into an image so it can also go on Instagram | New format value, for example `Text card` |
| Stat cards | One big number with its source footnote | Uses the existing footnote field |
| Quote cards | One line and an attribution | Good for founder quotes |
| Video cover images | A cover frame per video for Reels and TikTok | Reuse the title frame at the cover size |
| Subtitles and alt text | An `.srt` per video and an alt-text file per asset | The script already has all the text |
| Motion in videos | Text that animates in, a progress bar, slide transitions | Still ffmpeg only |

## 2. Product visuals without recording anything

| Idea | What it gives you | Notes |
|---|---|---|
| Automated product screenshots | Real CreatrGrid creator pages and AdoptDontShop screens, framed in a phone or browser | Headless Chrome against the demo creator pages and the component catalogue |
| Scripted walkthrough videos | A "screen recording" made by a script clicking through a demo | Playwright against demo data; replaces the Screen recording format |
| Pricing card from the live site | A plans graphic that cannot drift from the pricing page | Read the pricing page at build time |
| "What shipped" cards | A card per public changelog entry | Reads the Changelog tab |

## 3. Brand kit assets

| Idea | What it gives you |
|---|---|
| Profile banners and headers | LinkedIn, X and Facebook covers per brand, at the right sizes |
| Avatars and highlight covers | Consistent profile images and Instagram highlight icons |
| Link preview images | Share images for each site and changelog page |

## 4. Quality and workflow

| Idea | What it gives you |
|---|---|
| Review gallery | One HTML page showing every asset for the week, to approve at a glance |
| Visual checks in CI | Fail the build on clipped text, wrong sizes or unrendered corners |
| Claims check | Fail the build when a row has a figure, price, percentage or date with no footnote, or a banned word such as "waitlist" |
| Design tokens sync | Read colours and fonts from each design system's tokens so templates stay in step |

## 5. Wider social automation (beyond asset building)

1. Publishing from the sheet: a scheduler posts rows that have a date and writes the link back to "Posted URL". Postiz is the likely fit. Needs a decision.
2. Changelog to draft posts: each public changelog entry becomes a draft row from a fixed template.
3. Rescue lead alerts: forward new Instagram and Facebook messages to the existing alerts channel.
4. Tracked links: tag each CreatrGrid link per post and platform from the Asset ID.
5. Results back into the sheet: weekly views and engagement per posted link.
6. Drift checks: compare prices and plan features in posts against the live pricing page.
7. Recycling evergreen posts: re-queue the best "adoption know-how" posts every few months.

Keep manual: approving each post before it goes out, and replying to people.
