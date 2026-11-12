"""Fetch icd-11 index terms from the who api into a resumable cache.

Credentials are read from the environment (ICD_CLIENT_ID, ICD_CLIENT_SECRET); nothing is
stored in the repository. Each thread keeps one http connection open, which is roughly
three times faster than a connection per request against this api.

usage:
    ICD_CLIENT_ID=... ICD_CLIENT_SECRET=... python3 scripts/fetch_terms.py --langs en,es,fr,pt

cache: data/.cache/terms_<lang>.jsonl, one row per code: {"code", "lang", "terms"}
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import queue
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "public/data/mms-2026-01.json"
CACHE_DIR = ROOT / "data/.cache"
HOST = "id.who.int"
PREFIX = "/icd/release/11/2026-01/mms/"


class Tokens:
    """Thread-safe bearer token, refreshed before the one hour expiry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value = ""
        self._fetched_at = 0.0

    def get(self) -> str:
        with self._lock:
            if not self._value or time.time() - self._fetched_at > 3000:
                body = urllib.parse.urlencode(
                    {
                        "client_id": os.environ["ICD_CLIENT_ID"],
                        "client_secret": os.environ["ICD_CLIENT_SECRET"],
                        "scope": "icdapi_access",
                        "grant_type": "client_credentials",
                    }
                ).encode()
                request = urllib.request.Request(
                    "https://icdaccessmanagement.who.int/connect/token",
                    data=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with urllib.request.urlopen(request, timeout=40) as response:
                    self._value = json.loads(response.read())["access_token"]
                self._fetched_at = time.time()
            return self._value


TOKENS = Tokens()
LOCAL = threading.local()
WRITE_LOCK = threading.Lock()
COUNTS = {"done": 0, "failed": 0, "cached": 0}
STATE = {"lang": "en", "cache": CACHE_DIR / "terms_en.jsonl"}


def connection() -> http.client.HTTPSConnection:
    conn = getattr(LOCAL, "conn", None)
    if conn is None:
        conn = http.client.HTTPSConnection(HOST, timeout=40)
        LOCAL.conn = conn
    return conn


def fetch(path_suffix: str) -> dict:
    delay = 1.0
    for attempt in range(5):
        conn = connection()
        try:
            conn.request(
                "GET",
                PREFIX + path_suffix,
                headers={
                    "Authorization": f"Bearer {TOKENS.get()}",
                    "Accept": "application/json",
                    "Accept-Language": STATE["lang"],
                    "API-Version": "v2",
                },
            )
            response = conn.getresponse()
            body = response.read()
            if response.status == 200:
                return json.loads(body)
            if response.status == 404:
                return {}
            if response.status in (401, 403, 429, 500, 502, 503, 504) and attempt < 4:
                retry_after = response.getheader("Retry-After")
                LOCAL.conn = None
                conn.close()
                time.sleep(float(retry_after) if retry_after else delay)
                delay = min(delay * 2, 20.0)
                continue
            raise RuntimeError(f"status {response.status}")
        except (http.client.HTTPException, OSError, TimeoutError):
            LOCAL.conn = None
            try:
                conn.close()
            except Exception:
                pass
            if attempt == 4:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 20.0)
    return {}


def labels(entity: dict, key: str) -> list[str]:
    values = []
    for item in entity.get(key) or []:
        label = item.get("label", {}) if isinstance(item, dict) else {}
        value = label.get("@value")
        if value:
            values.append(value.strip())
    return values


def work(item: tuple[str, str]) -> None:
    code, path_suffix = item
    try:
        entity = fetch(path_suffix)
        if not entity:
            raise RuntimeError("empty entity")
        terms = {entity.get("title", {}).get("@value", "")}
        terms.update(labels(entity, "indexTerm"))
        terms.update(labels(entity, "synonym"))
        row = {
            "code": entity.get("code", code),
            "lang": STATE["lang"],
            "terms": sorted(term for term in terms if term and term.strip()),
        }
        with WRITE_LOCK:
            with STATE["cache"].open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            COUNTS["done"] += 1
            if COUNTS["done"] % 1000 == 0:
                print(f"[{STATE['lang']}] {COUNTS['done']} fetched, {COUNTS['failed']} failed", flush=True)
    except Exception:
        with WRITE_LOCK:
            COUNTS["failed"] += 1


def run_language(lang: str, workers: int) -> None:
    STATE["lang"] = lang
    STATE["cache"] = CACHE_DIR / f"terms_{lang}.jsonl"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    COUNTS.update({"done": 0, "failed": 0, "cached": 0})

    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    done: set[str] = set()
    if STATE["cache"].exists():
        for line in STATE["cache"].read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)["code"])
                except json.JSONDecodeError:
                    continue

    pending: queue.Queue = queue.Queue()
    for row in catalogue:
        if row["code"] in done:
            COUNTS["cached"] += 1
            continue
        pending.put((row["code"], row["uri"].split("/mms/", 1)[1].strip("/")))

    print(f"[{lang}] cached={COUNTS['cached']} pending={pending.qsize()}", flush=True)
    if pending.qsize() == 0:
        return

    started = time.monotonic()
    LOCAL.conn = None

    def runner() -> None:
        while True:
            try:
                item = pending.get_nowait()
            except queue.Empty:
                return
            work(item)
            pending.task_done()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in range(workers):
            pool.submit(runner)
    print(f"[{lang}] finished in {(time.monotonic() - started) / 60:.1f} min, failed={COUNTS['failed']}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", default="en")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if "ICD_CLIENT_ID" not in os.environ or "ICD_CLIENT_SECRET" not in os.environ:
        raise SystemExit("set ICD_CLIENT_ID and ICD_CLIENT_SECRET")
    for lang in [item.strip() for item in args.langs.split(",") if item.strip()]:
        run_language(lang, args.workers)


if __name__ == "__main__":
    main()
