#!/usr/bin/env python3
"""Verify and optionally acquire DosePilot's exact public Data S4 workbook."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
SOURCE = json.loads((HERE / "PUBLIC_SOURCE.json").read_text(encoding="utf-8"))
ACCEPT = "application/vnd.mendeley-public-dataset.1+json"
USER_AGENT = "von-dosepilot-public-reproduction/1.0"


def fetch_json(url: str, timeout: float) -> object:
    request = Request(url, headers={"Accept": ACCEPT, "User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return json.load(response)


def verify_metadata(timeout: float) -> dict:
    snapshot = fetch_json(SOURCE["snapshot_url"], timeout)
    if snapshot.get("id") != SOURCE["dataset_id"] or snapshot.get("version") != SOURCE["version"]:
        raise ValueError("Public dataset identity/version changed")
    if snapshot.get("doi") != SOURCE["doi"]:
        raise ValueError("Public dataset DOI changed")
    licence = snapshot.get("licence") or {}
    if licence.get("short_name") != SOURCE["licence_short_name"]:
        raise ValueError("Public dataset licence changed")

    files = fetch_json(SOURCE["files_url"], timeout)
    wanted = SOURCE["file"]
    matches = [item for item in files if item.get("filename") == wanted["filename"]]
    if len(matches) != 1:
        raise ValueError("Expected exactly one Data S4.xlsx file")
    item = matches[0]
    details = item.get("content_details") or {}
    observed = {
        "filename": item.get("filename"),
        "id": item.get("id"),
        "bytes": details.get("size"),
        "sha256": details.get("sha256_hash"),
        "download_url": details.get("download_url"),
    }
    for key in ("filename", "id", "bytes", "sha256", "download_url"):
        if observed[key] != wanted[key]:
            raise ValueError(f"Public source metadata changed: {key}")
    return {
        "dataset_id": snapshot["id"],
        "version": snapshot["version"],
        "doi": snapshot["doi"],
        "licence": licence.get("short_name"),
        "file": observed,
    }


def acquire(output: Path, timeout: float) -> dict:
    verified = verify_metadata(timeout)
    if output.exists():
        raise FileExistsError(f"Refusing existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    total = 0

    fd, temporary = tempfile.mkstemp(prefix=output.name + ".", suffix=".part", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary)
    try:
        request = Request(SOURCE["file"]["download_url"], headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as response, temporary.open("wb") as stream:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}: source download")
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                stream.write(block)
                h.update(block)
                total += len(block)
        if total != SOURCE["file"]["bytes"]:
            raise ValueError(f"Downloaded byte count changed: {total}")
        digest = h.hexdigest()
        if digest != SOURCE["file"]["sha256"]:
            raise ValueError(f"Downloaded SHA256 changed: {digest}")
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {**verified, "output": str(output), "downloaded_bytes": total, "downloaded_sha256": h.hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Verify public metadata without downloading the workbook.")
    parser.add_argument("--output", type=Path, help="Destination for the exact Data S4.xlsx workbook.")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.check_only == (args.output is not None):
        parser.error("choose exactly one of --check-only or --output")
    result = verify_metadata(args.timeout) if args.check_only else acquire(args.output, args.timeout)
    print(json.dumps({"status": "verified", **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
