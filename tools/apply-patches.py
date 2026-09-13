#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check pinned clean projects; apply reviewed patches only with --apply.

Does not download, build, sign, install or flash. Requires Git and Python 3.9+.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile

REPOSITORY = Path(__file__).resolve().parents[1]


def git(tree, *args, check=True):
    result = subprocess.run(["git", "-C", str(tree), *args], capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result


def relative(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or ".git" in path.parts:
        raise ValueError("Unsafe relative path: " + name)
    return path


def validate_series(tree, patches):
    # Only materialize files touched by patches; never copy an entire AOSP tree.
    names = set()
    for patch in patches:
        for line in patch.read_text().splitlines():
            if line.startswith(("--- a/", "+++ b/")):
                names.add(str(relative(line[6:])))
    with tempfile.TemporaryDirectory(prefix="gold-patch-check-") as tmp:
        stage = Path(tmp)
        git(stage, "init", "-q")
        for name in sorted(names):
            result = git(tree, "show", "HEAD:" + name, check=False)
            if result.returncode:
                continue  # A new file can be supplied by an earlier patch.
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(result.stdout)
            mode = git(tree, "ls-tree", "HEAD", "--", name).stdout.split()[0]
            target.chmod(0o755 if mode == b"100755" else 0o644)
        for patch in patches:
            git(stage, "apply", "--check", str(patch))
            git(stage, "apply", str(patch))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path, help="Fresh Android source root")
    parser.add_argument("--apply", action="store_true", help="Apply after all checks pass")
    args = parser.parse_args()
    root = args.tree.resolve(strict=True)
    series = json.loads((REPOSITORY / "patches/series.json").read_text())
    projects = []
    for entry in series:
        tree = root / relative(entry["path"])
        if not tree.is_dir() or tree.resolve() != tree:
            raise RuntimeError("Missing or symlinked project: " + entry["path"])
        if Path(git(tree, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve() != tree:
            raise RuntimeError("Not a separate Git project: " + entry["path"])
        if git(tree, "rev-parse", "HEAD").stdout.decode().strip() != entry["revision"]:
            raise RuntimeError("Wrong base revision: " + entry["path"])
        if git(tree, "status", "--porcelain", "--untracked-files=all").stdout:
            raise RuntimeError("Project is not clean: " + entry["path"])
        for name, revision in entry.get("submodules", {}).items():
            sub = tree / relative(name)
            if git(sub, "rev-parse", "HEAD").stdout.decode().strip() != revision:
                raise RuntimeError("Wrong/missing submodule: " + name)
        patches = [REPOSITORY / relative(p) for p in entry["patches"]]
        validate_series(tree, patches)
        projects.append((tree, patches))
        print("Checked", entry["path"])
    copies = []
    source_root = REPOSITORY / "sources"
    for source in sorted(source_root.rglob("*")):
        if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc" or source.name == ".DS_Store":
            continue
        if source.is_symlink():
            raise RuntimeError("Unexpected source symlink")
        destination = root / source.relative_to(source_root)
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("Refusing to overwrite source input: " + str(destination))
        if not destination.parent.resolve().is_relative_to(root):
            raise RuntimeError("Source destination escapes Android tree")
        copies.append((source, destination))
    if not args.apply:
        print("All checks passed. No source changes. Use --apply to apply patches and copy inputs.")
        return
    # All validation happens first. If an external interruption occurs, inspect
    # git status; do not rerun against a partially modified tree or reset blindly.
    for tree, patches in projects:
        for patch in patches:
            git(tree, "apply", str(patch))
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    print("Source patches and integration inputs applied. No images built or flashed.")
    print("IMS payload, vendor/kernel inputs and hybrid assembly remain separate prerequisites.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        raise SystemExit(str(error))
