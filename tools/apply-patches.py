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


def patch_paths(patches):
    names = set()
    for patch in patches:
        for line in patch.read_text().splitlines():
            if line.startswith(("--- a/", "+++ b/")):
                names.add(str(relative(line[6:])))
    return names


def validate_series(tree, patches):
    # Only materialize files touched by patches; never copy an entire AOSP tree.
    names = patch_paths(patches)
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
        return {name: ((stage / name).read_bytes(), (stage / name).stat().st_mode & 0o111)
                if (stage / name).is_file() else None for name in names}


def source_files(root):
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("Missing or symlinked local source: " + str(root))
    result = []
    for source in sorted(root.rglob("*")):
        if source.is_symlink():
            raise RuntimeError("Unexpected source symlink: " + str(source))
        if "__pycache__" in source.parts or source.suffix == ".pyc" or source.name == ".DS_Store":
            continue
        if source.is_file():
            result.append(source)
    return result


def safe_destination(destination, root):
    if destination.is_symlink() or not destination.parent.resolve().is_relative_to(root):
        raise RuntimeError("Source destination escapes Android tree: " + str(destination))
    if destination.exists() and not destination.is_file():
        raise RuntimeError("Destination is not a regular file: " + str(destination))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path, help="Fresh Android source root")
    parser.add_argument("--apply", action="store_true", help="Apply after all checks pass")
    args = parser.parse_args()
    root = args.tree.resolve(strict=True)
    series = json.loads((REPOSITORY / "patches/series.json").read_text())
    projects = []
    copies = []
    deletions = []
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
            if (not sub.is_dir() or sub.resolve() != sub or
                    Path(git(sub, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve() != sub or
                    git(sub, "status", "--porcelain", "--untracked-files=all").stdout or
                    git(sub, "rev-parse", "HEAD").stdout.decode().strip() != revision):
                raise RuntimeError("Wrong/missing submodule: " + name)
        patches = [REPOSITORY / relative(p) for p in entry["patches"]]
        validate_series(tree, patches)
        if "source" in entry:
            source_root = REPOSITORY / relative(entry["source"])
            files = source_files(source_root)
            local_names = {p.relative_to(source_root).as_posix() for p in files}
            tracked = set(git(tree, "ls-files", "-z").stdout.decode().split("\0"))
            removed = {str(relative(name)) for name in entry.get("remove", [])}
            if removed & local_names or any(name not in tracked for name in removed):
                raise RuntimeError("Invalid explicit source deletions: " + entry["path"])
            for name in removed:
                destination = tree / name
                safe_destination(destination, root)
                deletions.append(destination)
            if any(name and name not in local_names | removed for name in tracked):
                raise RuntimeError("Local device tree omits upstream files; review deletions explicitly")
            for source in files:
                destination = tree / source.relative_to(source_root)
                safe_destination(destination, root)
                if destination.exists() and source.relative_to(source_root).as_posix() not in tracked:
                    raise RuntimeError("Refusing to overwrite untracked/ignored device input: " + str(destination))
                copies.append((source, destination))
        projects.append((tree, patches))
        print("Checked", entry["path"])
    # Only vendor integration files are copied here. Proprietary extraction
    # output remains an external input and is never silently overwritten.
    for source in source_files(REPOSITORY / "vendor"):
        destination = root / source.relative_to(REPOSITORY)
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("Refusing to overwrite source input: " + str(destination))
        safe_destination(destination, root)
        copies.append((source, destination))
    if not args.apply:
        print("All checks passed. No source changes. Use --apply to apply patches and copy inputs.")
        return
    # All validation happens first. If an external interruption occurs, inspect
    # git status; do not rerun against a partially modified tree or reset blindly.
    for tree, patches in projects:
        for patch in patches:
            git(tree, "apply", str(patch))
    for destination in deletions:
        destination.unlink()
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    print("Platform patches, local device tree and vendor integration inputs applied. No images built or flashed.")
    print("Generate and verify the pinned vendor/kernel inputs before the standard Android build.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        raise SystemExit(str(error))
