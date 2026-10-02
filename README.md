# hotlists

Daily DJ hot-lists (house / tech house / melodic / techno / disco) as CSV files,
published for the **hotlist-downloader** daemon, which polls `index.json` and
downloads new lists into rekordbox-ready, ID3v2.3-tagged MP3s.

This repo holds data only.

## Layout

```
index.json                 list of all hot-lists, newest first
lists/YYYY-MM-DD.csv       the hot-list
lists/YYYY-MM-DD-urls.txt  plain list of the YouTube URLs in that CSV (one per line)
lists/YYYY-MM-DD-NAME.csv  a named list (e.g. 2026-10-02-techno-essentials.csv), + -urls.txt
scripts/publish.py         adds a list + rebuilds index.json + commits + pushes
```

Raw URLs (what the daemon reads):

* `https://raw.githubusercontent.com/reikaas/hotlists/main/index.json`
* `https://raw.githubusercontent.com/reikaas/hotlists/main/lists/YYYY-MM-DD.csv`

## index.json

```json
{
  "schema": 1,
  "updated": "2026-10-02T22:15:00+02:00",
  "lists": [
    {"date": "2026-10-02", "csv": "lists/2026-10-02.csv", "urls": "lists/2026-10-02-urls.txt",
     "tracks": 44, "sha256": "<sha256 of the CSV bytes>"}
  ]
}
```

* `name` (optional) tells apart several lists published on the same date, e.g.
  `"name": "techno-essentials"`. Unnamed entries are the daily hot-list.
* `csv` / `urls` are paths relative to the repo root (resolve them against the URL of `index.json`).
* `tracks` = number of CSV rows with a YouTube URL in `youtube_url`.
* `sha256` = hex SHA-256 of the exact CSV bytes. Clients must verify it.
  (`.gitattributes` disables line-ending conversion so the bytes never change.)
* `schema` is bumped only for incompatible changes.

## CSV columns

`genre, artist, title, mix, label, chart_source, youtube_url, yt_title, yt_channel, duration, why, notes`
(UTF-8, header row, order does not matter; optional `release`, `year`).
`artist` may hold several artists separated by `, `. `youtube_url` may say `no URL found`.

## Publishing a new list

```
python scripts/publish.py /path/to/2026-10-03.csv /path/to/2026-10-03-urls.txt
```

The date is taken from the file name (or `--date YYYY-MM-DD`). Use `--no-push` to commit
locally only, `--no-commit` to just rebuild `index.json`. Re-publishing a date replaces it.

Named list (several per date are fine):

```
python scripts/publish.py /path/to/techno-essentials.csv --date 2026-10-02 --name techno-essentials
```

This writes `lists/2026-10-02-techno-essentials.csv` (+ `-urls.txt` if present next to the CSV)
and adds an index entry with `"name": "techno-essentials"`. Re-publishing the same date + name replaces it.
