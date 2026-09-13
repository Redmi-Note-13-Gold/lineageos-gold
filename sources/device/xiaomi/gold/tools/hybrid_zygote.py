#!/usr/bin/env python3
"""Stage the selected zygote RC closure in a fresh gold hybrid target-files tree.

This pre-image gate does not build images, sign packages, or contact a device.
The caller supplies the property file containing the final ro.zygote selection.
"""

import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


SOURCE_ROOT = Path(__file__).resolve().parents[4]
INIT_DIR = "system/etc/init/hw/"
VARIANTS = {"zygote32", "zygote64", "zygote64_32"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def selected_zygote(property_file):
    """Read one explicitly selected property source, not Android's boot property loader."""
    values = []
    for line in Path(property_file).read_text().splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key.strip() == "ro.zygote":
            values.append(value.strip())
    require(len(values) == 1 and values[0] in VARIANTS,
            "Expected exactly one supported literal ro.zygote in the final property source")
    return values[0]


def confined(root, relative):
    root = Path(root).resolve()
    path = root / relative
    require(path.resolve().is_relative_to(root), f"Path escapes tree: {path}")
    for item in (path, *path.parents):
        if item == root:
            break
        require(not item.is_symlink(), f"Symlink is not allowed here: {item}")
    return path


def rc_plan(target, rootdir, variant):
    """Validate the whole canonical import graph before adding any files."""
    require(variant in VARIANTS, f"Unsupported ro.zygote: {variant}")
    rootdir = Path(rootdir).resolve()
    system = confined(target, "SYSTEM")
    visiting, complete, additions = set(), {}, {}
    executable_modes = {}
    # Extracted target-files can be host-mode 0644; Android modes live in META.
    config = confined(target, "META/filesystem_config.txt")
    for line in config.read_text().splitlines():
        fields = line.split()
        if fields and fields[0].startswith("system/bin/"):
            require(len(fields) >= 4 and re.fullmatch(r"[0-7]{3,4}", fields[3])
                    and fields[0] not in executable_modes,
                    f"Invalid or duplicate executable filesystem metadata: {line}")
            executable_modes[fields[0]] = int(fields[3], 8)

    def visit(name):
        require(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.rc", name),
                f"Unsupported canonical RC name: {name}")
        require(name not in visiting, f"RC import cycle: {name}")
        if name in complete:
            return
        visiting.add(name)
        source = confined(rootdir, name)
        require(source.is_file(), f"Missing canonical RC: {source}")
        data = source.read_bytes()
        destination = confined(system, "etc/init/hw/" + name)
        if destination.exists():
            require(destination.is_file() and destination.read_bytes() == data,
                    f"Existing RC differs from canonical source; review required: {destination}")
        else:
            additions[name] = data
        for line in data.decode().splitlines():
            tokens = shlex.split(line, comments=True)
            if not tokens:
                continue
            if tokens[0] == "import":
                prefix = "/" + INIT_DIR
                require(len(tokens) == 2 and tokens[1].startswith(prefix),
                        f"Unsupported RC import: {line}")
                visit(tokens[1][len(prefix):])
            elif tokens[0] == "service":
                require(len(tokens) >= 3 and tokens[2].startswith("/system/bin/"),
                        f"Unsupported service executable: {line}")
                executable = tokens[2][len("/system/"):]
                # Android absolute app_process symlinks must resolve inside SYSTEM, not the host.
                binary = system / executable
                if binary.is_symlink():
                    link = binary.readlink()
                    binary = (system / str(link)[len("/system/"):]
                              if str(link).startswith("/system/") else binary.parent / link)
                binary = confined(system, binary.relative_to(system))
                record = "system/" + binary.resolve().relative_to(system).as_posix()
                require(binary.is_file() and executable_modes.get(record, 0) & 0o111,
                        f"Missing executable required by selected RC: {binary}")
        visiting.remove(name)
        complete[name] = data

    visit(f"init.{variant}.rc")
    return complete, additions


def prepare(target, source, property_file, fs_config):
    target, source = Path(target).resolve(), Path(source).resolve()
    require(target.is_dir() and not target.is_relative_to(source),
            "Use an isolated target-files staging directory outside the source tree")
    property_file = Path(property_file).resolve()
    require(property_file.is_relative_to(target), "Property source must belong to staging")
    variant = selected_zygote(property_file)
    closure, additions = rc_plan(target, source / "system/core/rootdir", variant)
    config = confined(target, "META/filesystem_config.txt")
    require(config.is_file(), "Missing baseline META/filesystem_config.txt")
    original = config.read_bytes()
    records = {}
    for line in original.decode().splitlines():
        fields = line.split()
        if fields and fields[0].startswith(INIT_DIR):
            require(fields[0] not in records, f"Duplicate filesystem record: {fields[0]}")
            records[fields[0]] = fields
    missing_records = []
    for name in closure:
        path = INIT_DIR + name
        expected = [path, "0", "0", "644", "capabilities=0x0"]
        if path in records:
            require(records[path] == expected, f"Unexpected RC filesystem metadata: {path}")
        else:
            missing_records.append(path)
    for relative in ("IMAGES/system.img", "IMAGES/system.map", "IMAGES/vbmeta_system.img",
                     "PREBUILT_IMAGES/system.img", "PREBUILT_IMAGES/vbmeta_system.img"):
        stale = target / relative
        require(not stale.exists() and not stale.is_symlink(),
                f"Stale image must be excluded from the NEW staging copy: {stale}")
    destinations = []
    try:
        for name, data in additions.items():
            destination = confined(target, "SYSTEM/etc/init/hw/" + name)
            require(destination.parent.is_dir(), "Missing SYSTEM/etc/init/hw staging directory")
            with destination.open("xb") as stream:
                stream.write(data)
            destinations.append(destination)
            destination.chmod(0o644)
        # Query the same Android fs_config used by the historical assembler, after staging RCs.
        if missing_records:
            result = subprocess.run(
                [str(fs_config), "-D", str(target / "SYSTEM"), "-C"],
                input="".join(path + "\n" for path in missing_records),
                text=True, capture_output=True, check=True)
            expected = "".join(path + " 0 0 644 capabilities=0x0\n" for path in missing_records)
            require(result.stdout == expected, "Native fs_config returned unexpected RC metadata")
            require(config.read_bytes() == original, "Filesystem config changed while staging")
            separator = b"" if not original or original.endswith(b"\n") else b"\n"
            replacement = None
            try:
                with tempfile.NamedTemporaryFile(dir=config.parent, prefix=".zygote-fs-",
                                                 delete=False) as stream:
                    replacement = Path(stream.name)
                    stream.write(original + separator + expected.encode())
                replacement.chmod(config.stat().st_mode & 0o777)
                require(config.read_bytes() == original, "Filesystem config changed while staging")
                replacement.replace(config)
            finally:
                if replacement is not None and replacement.exists():
                    replacement.unlink()
    except Exception:
        for path in destinations:
            path.unlink()
        raise
    return {"ro.zygote": variant, "rc_closure": sorted(closure),
            "added_rcs": sorted(additions), "added_fs_config": missing_records,
            "images_built": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-files", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--zygote-property-file", type=Path, required=True,
                        help="File providing the final ro.zygote after all stock/property overlays")
    parser.add_argument("--fs-config", type=Path,
                        help="Android host fs_config; defaults to the source's Darwin host tool")
    args = parser.parse_args()
    fs_config = args.fs_config or args.source_root / "out/host/darwin-x86/bin/fs_config"
    try:
        result = prepare(args.target_files, args.source_root, args.zygote_property_file, fs_config)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Zygote pre-image gate failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
