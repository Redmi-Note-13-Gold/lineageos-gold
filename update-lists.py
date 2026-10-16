#!/usr/bin/env python3
"""Write the lists the Updater app reads, one per published build.

The app asks for updates/<its own ro.build.version.incremental>.json. After this runs, the list
of every build published before the new one offers the new one: as an incremental package where
one was made from that build, as the full package otherwise. The list of the new build is empty.

    update-lists.py --url <where the packages are downloaded from> --version 24.0 \\
        full.zip [incremental.zip ...]

A build is "published" when its list exists, so to start offering updates to a build that has
none yet, create an empty list for it first.
"""

import argparse
import hashlib
import json
import pathlib
import sys
import zipfile


def metadata(path):
    with zipfile.ZipFile(path) as package:
        text = package.read("META-INF/com/android/metadata").decode()
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as package:
        for block in iter(lambda: package.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def entry(path, meta, args):
    return {
        "datetime": int(meta["post-timestamp"]),
        "files": [
            {
                "filename": path.name,
                "os_patch_level": meta["post-security-patch-level"],
                "os_sdk_level": int(meta["post-sdk-level"]),
                "ota_property_files": meta["ota-property-files"].strip(),
                "sha256": sha256(path),
                "size": path.stat().st_size,
                "url": args.url.rstrip("/") + "/" + path.name,
            }
        ],
        "type": args.type,
        "version": args.version,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", required=True, help="URL the packages are downloaded from, without the file name")
    parser.add_argument("--version", required=True, help="ro.lineage.build.version of the new build")
    parser.add_argument("--type", default="unofficial", help="ro.lineage.releasetype of the new build")
    parser.add_argument("--dir", default=pathlib.Path(__file__).resolve().parent / "updates", type=pathlib.Path)
    parser.add_argument("full", type=pathlib.Path)
    parser.add_argument("incremental", type=pathlib.Path, nargs="*")
    args = parser.parse_args()

    full = metadata(args.full)
    if "pre-build-incremental" in full:
        sys.exit(f"{args.full} is an incremental package")
    new = full["post-build-incremental"]

    offers = {}
    for path in args.incremental:
        meta = metadata(path)
        if meta.get("post-build-incremental") != new or "pre-build-incremental" not in meta:
            sys.exit(f"{path} is not an incremental package to {new}")
        offers[meta["pre-build-incremental"]] = entry(path, meta, args)
    full_entry = entry(args.full, full, args)

    args.dir.mkdir(exist_ok=True)
    earlier = sorted(path for path in args.dir.glob("*.json") if path.stem != new)
    unknown = set(offers) - {path.stem for path in earlier}
    if unknown:
        sys.exit("no list for " + ", ".join(sorted(unknown)) + "; create an empty one first")

    (args.dir / f"{new}.json").write_text("[]\n")
    for path in earlier:
        offer = offers.get(path.stem, full_entry)
        path.write_text(json.dumps([offer], indent=2) + "\n")
        print(f"{path.stem}: {offer['files'][0]['filename']}")


if __name__ == "__main__":
    main()
