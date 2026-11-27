# One folder per brand, platform and post

```
python package.py out --csv posts.csv
```

Run it after `render.py`. It reads the sheet and the rendered assets and writes `out/posts/`:

```
out/posts/
  schedule.csv                     every post in calendar order, with its check note
  AdoptDontShop/
    Instagram/
      ADS-C01/  ADS-C01_Instagram_01.png ... _caption.txt  _alt.txt
      ADS-V01/  ADS-V01_Instagram.mp4  _cover.png  _caption.txt  _alt.txt
    Facebook/
      ADS-C01/  ADS-C01_Facebook_01.png  ... _caption.txt  _alt.txt
    TikTok/
      ADS-V01/  ADS-V01_TikTok.mp4  _cover.png  _caption.txt  _alt.txt
  ideaSquared/
    LinkedIn/
      ISQ-C01/  ISQ-C01_LinkedIn.pdf  _caption.txt  _alt.txt
    Instagram/
      ISQ-C01/  ...
  CreatrGrid/
    X/
      CG-X01/   CG-X01_X_post.txt
```

The top level is the row's **Brand**, so everything for one account on one platform sits in one folder.
A row gets one post folder under its **Platform** and one under each platform in **Also post to**. Every file name
starts with the post and platform, so a file is still identifiable after it has been moved to a phone.
In `schedule.csv` the Post column is the same path: `AdoptDontShop/Instagram/ADS-C01`.

## What each platform gets

| Platform | Carousel | Video | Card | Text post |
|---|---|---|---|---|
| Instagram, Facebook, TikTok, X | numbered PNGs | MP4 and cover | PNG | `_post.txt` |
| LinkedIn | one PDF (uploaded as a document) | MP4 and cover | PNG | `_post.txt` |

## How the caption changes per platform

The sheet holds one caption per row. `package.py` adjusts it by fixed rules:

| Platform | Links | Hashtags kept |
|---|---|---|
| Instagram | removed, "Link in bio." added | first 5 |
| TikTok | removed, "Link in bio." added | first 4 |
| Facebook | kept | first 2 |
| LinkedIn | kept | first 3 |
| X | kept; a warning if the post is over 280 characters | first 2 |

So list hashtags in the sheet with the most important first, and put a link on a line of its own:
that whole line is dropped on Instagram and TikTok. A link inside a sentence is cut out of the sentence.

To write a different caption for one platform, add a block after the general one in the Content cell.
It is used exactly as written:

```
Caption: The general caption.
https://ideasquared.co.uk

#BuildInPublic #SoloFounder

Caption for TikTok: A shorter one for TikTok. #BuildInPublic
```

The sheet's posting tabs show the same text: `posting_tabs.py` writes it from these rules (see `docs/posting-tabs.md`).

## Options

- `--only ADS-C01,CG-X03` rebuilds just those posts.

A post's folders are deleted and rebuilt each run, so removing a platform from the sheet, or changing a row's brand,
leaves no old copy behind. A full run (no `--only`) also removes folders for rows that are no longer in the sheet,
removes the older `out/posts/<post>/<platform>/` layout, and rewrites `schedule.csv` in calendar order.
It only ever deletes folders shaped like its own output; anything else you put under `out/posts` is left alone.
Asset IDs and brand names may only use letters, numbers, `-` and `_`; a row with any other brand is skipped with a warning.
Rows that have not been rendered yet are skipped with a warning.
