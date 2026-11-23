# One folder per post and platform

```
python package.py out --csv posts.csv
```

Run it after `render.py`. It reads the sheet and the rendered assets and writes `out/posts/`:

```
out/posts/
  schedule.csv                     every post in calendar order, with its check note
  ADS-C01/
    Instagram/  ADS-C01_Instagram_01.png ... _caption.txt  _alt.txt
    Facebook/   ADS-C01_Facebook_01.png  ... _caption.txt  _alt.txt
  ISQ-C01/
    LinkedIn/   ISQ-C01_LinkedIn.pdf  _caption.txt  _alt.txt
    Instagram/  ...
  ADS-V01/
    TikTok/     ADS-V01_TikTok.mp4  _cover.png  _caption.txt  _alt.txt
  CG-X01/
    X/          CG-X01_X_post.txt
```

A row gets one folder for its **Platform** and one for each platform in **Also post to**. Every file name
starts with the post and platform, so a file is still identifiable after it has been moved to a phone.

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

So list hashtags in the sheet with the most important first.

To write a different caption for one platform, add a block after the general one in the Content cell.
It is used exactly as written:

```
Caption: The general caption.
https://ideasquared.co.uk

#BuildInPublic #SoloFounder

Caption for TikTok: A shorter one for TikTok. #BuildInPublic
```

## Options

- `--only ADS-C01,CG-X03` rebuilds just those posts.

A post's folder is deleted and rebuilt each run, so removing a platform from the sheet removes its folder.
Rows that have not been rendered yet are skipped with a warning.
