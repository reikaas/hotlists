#!/usr/bin/env python3
"""
publish.py - add a hot-list to this repo and regenerate index.json.

Usage:
  python scripts/publish.py path/to/2026-10-02.csv [path/to/2026-10-02-urls.txt]
                            [--date YYYY-MM-DD] [--no-push] [--no-commit] [--message MSG]

* The date comes from --date or from the CSV file name (YYYY-MM-DD anywhere in it).
* The urls file defaults to <csv-stem>-urls.txt next to the CSV (optional).
* Files are copied byte-for-byte to lists/YYYY-MM-DD.csv and lists/YYYY-MM-DD-urls.txt.
* index.json is rebuilt from everything in lists/ (newest first) with sha256 and a
  track count (= CSV rows with a valid YouTube URL in the youtube_url column).
* Then: git add, commit and push (pull --rebase first). Re-publishing the same day
  overwrites that day's files; if nothing changed, nothing is committed.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTS = os.path.join(REPO, "lists")
INDEX = os.path.join(REPO, "index.json")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
YT_RE = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?[^\s,;)]*v=|shorts/|embed/|live/)|youtu\.be/)"
    r"[A-Za-z0-9_-]{11}"
)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def count_tracks(path: str) -> int:
    raw = open(path, "rb").read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    rd = csv.DictReader(io.StringIO(text, newline=""))
    if not rd.fieldnames:
        raise SystemExit(f"{path}: no header row")
    rd.fieldnames = [(f or "").strip().lower() for f in rd.fieldnames]
    if "youtube_url" not in rd.fieldnames:
        raise SystemExit(f"{path}: no youtube_url column")
    return sum(1 for r in rd if YT_RE.search((r.get("youtube_url") or "").strip()))


def build_index() -> dict:
    entries = []
    for name in os.listdir(LISTS) if os.path.isdir(LISTS) else []:
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.csv", name)
        if not m:
            continue
        date = m.group(1)
        csv_rel = f"lists/{date}.csv"
        e = {"date": date, "csv": csv_rel}
        urls = os.path.join(LISTS, f"{date}-urls.txt")
        if os.path.exists(urls):
            e["urls"] = f"lists/{date}-urls.txt"
        p = os.path.join(REPO, csv_rel)
        e["tracks"] = count_tracks(p)
        e["sha256"] = sha256(p)
        entries.append(e)
    entries.sort(key=lambda e: e["date"], reverse=True)
    updated = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    return {"schema": 1, "updated": updated, "lists": entries}


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", REPO, *args], check=check, text=True, capture_output=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("urls", nargs="?")
    ap.add_argument("--date")
    ap.add_argument("--message")
    ap.add_argument("--no-commit", action="store_true", help="only copy files + rebuild index.json")
    ap.add_argument("--no-push", action="store_true", help="commit but do not push")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.csv):
        raise SystemExit(f"CSV not found: {a.csv}")
    date = a.date
    if not date:
        m = DATE_RE.search(os.path.basename(a.csv))
        if not m:
            raise SystemExit("cannot infer date from CSV name; pass --date YYYY-MM-DD")
        date = m.group(1)
    dt.date.fromisoformat(date)  # validates
    urls = a.urls
    if not urls:
        cand = os.path.splitext(a.csv)[0] + "-urls.txt"
        urls = cand if os.path.isfile(cand) else None
    elif not os.path.isfile(urls):
        raise SystemExit(f"urls file not found: {urls}")

    n = count_tracks(a.csv)  # validate before touching the repo
    pushing = not (a.no_commit or a.no_push)
    if pushing and git("remote", check=False).stdout.strip():
        # get up to date first, so the push is a fast-forward
        if git("rev-parse", "--verify", "HEAD", check=False).returncode == 0:
            r = git("pull", "--rebase", "--quiet", check=False)
            if r.returncode != 0 and "couldn't find remote ref" not in r.stderr:
                print(r.stderr.strip(), file=sys.stderr)

    os.makedirs(LISTS, exist_ok=True)
    dst_csv = os.path.join(LISTS, f"{date}.csv")
    if os.path.abspath(a.csv) != os.path.abspath(dst_csv):
        shutil.copyfile(a.csv, dst_csv)
    if urls:
        dst_urls = os.path.join(LISTS, f"{date}-urls.txt")
        if os.path.abspath(urls) != os.path.abspath(dst_urls):
            shutil.copyfile(urls, dst_urls)

    idx = build_index()
    # keep "updated" stable if the list set did not change (avoids empty-diff commits)
    if os.path.exists(INDEX):
        try:
            old = json.load(open(INDEX, encoding="utf-8"))
            if old.get("lists") == idx["lists"]:
                idx["updated"] = old.get("updated", idx["updated"])
        except Exception:
            pass
    with open(INDEX, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(idx, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"lists/{date}.csv: {n} tracks with a YouTube URL, sha256 {sha256(dst_csv)}")

    if a.no_commit:
        return 0
    git("add", "index.json", "lists")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("nothing changed; no commit")
    else:
        git("commit", "-q", "-m", a.message or f"Hot-list {date} ({n} tracks)")
        print("committed")
    if not a.no_push:
        r = git("push", "-q", "-u", "origin", "HEAD", check=False)
        if r.returncode != 0:
            print(r.stderr.strip(), file=sys.stderr)
            return 1
        print("pushed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
