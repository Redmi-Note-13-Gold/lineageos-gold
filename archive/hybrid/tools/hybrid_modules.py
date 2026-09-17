#!/usr/bin/env python3
"""Stage the SYSTEM module compatibility link in fresh gold hybrid target-files.

This gate does not build images, change policy, copy modules, or contact a device.
Run after final overlays; the caller must exclusively own the staging directory.
"""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

from hybrid_zygote import confined, require


SOURCE_ROOT = Path(__file__).resolve().parents[3]
LINK_PATH = "/system/lib/modules"
LINK_TARGET = "/system_dlkm/lib/modules"
LINK_CONTEXT = "u:object_r:system_lib_file:s0"
LINK_MODE = 0o120644
FS_ROW = "system/lib/modules 0 0 644 capabilities=0x0\n"
STALE_IMAGES = ("IMAGES/system.img", "IMAGES/system.map", "IMAGES/vbmeta_system.img",
                "PREBUILT_IMAGES/system.img", "PREBUILT_IMAGES/vbmeta_system.img")
CONTEXT_SIDECARS = (".bin", ".local", ".local.bin", ".homedirs", ".homedirs.bin",
                    ".subs", ".subs_dist")


def file_state(path):
    require(not path.is_symlink(), f"Symlink is not allowed here: {path}")
    if not path.exists():
        return None
    require(path.is_file(), f"Expected a regular file: {path}")
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_mode, path.read_bytes())


def effective_contexts(target, misc_data):
    """Mirror LoadInfoDict(repacking=True)'s META basename relocation, not policy regexes."""
    values = []
    for line in misc_data.decode().splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key == "system_selinux_fc":
            values.append(value)
    require(len(values) == 1 and re.fullmatch(r"[A-Za-z0-9_./-]+", values[0]),
            "Expected one literal system_selinux_fc in META/misc_info.txt")
    name = PurePosixPath(values[0]).name
    require(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", name), "Invalid contexts basename")
    return confined(target, "META/" + name)


def lookup_context(contexts, library):
    """Query the actual Android host libselinux for a symlink, without dereferencing it."""
    library = Path(library)
    libraries = []
    if library.suffix == ".dylib":
        libraries = [ctypes.CDLL(str(library.parent / name), mode=ctypes.RTLD_GLOBAL)
                     for name in ("libpcre2.dylib", "liblog.dylib")]
    libraries.append(ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL, use_errno=True))
    lib = libraries[-1]

    class Option(ctypes.Structure):
        _fields_ = [("type", ctypes.c_int), ("value", ctypes.c_char_p)]

    lib.selabel_open.argtypes = (ctypes.c_uint, ctypes.POINTER(Option), ctypes.c_uint)
    lib.selabel_open.restype = ctypes.c_void_p
    lib.selabel_lookup_raw.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
                                      ctypes.c_char_p, ctypes.c_int)
    lib.selabel_lookup_raw.restype = ctypes.c_int
    lib.selabel_close.argtypes = (ctypes.c_void_p,)
    lib.selabel_close.restype = None
    lib.freecon.argtypes = (ctypes.c_void_p,)
    lib.freecon.restype = None
    # SELABEL_CTX_FILE=0; PATH=3; BASEONLY=2. Sidecars are rejected by the gate.
    options = (Option * 2)(Option(3, os.fsencode(contexts)), Option(2, b"1"))
    handle = lib.selabel_open(0, options, 2)
    require(handle, f"libselinux could not read contexts: {contexts}")
    context = ctypes.c_void_p()
    try:
        require(lib.selabel_lookup_raw(handle, ctypes.byref(context), LINK_PATH.encode(),
                                       LINK_MODE) == 0,
                f"libselinux found no symlink context for {LINK_PATH}: {contexts}")
        return ctypes.string_at(context).decode()
    finally:
        if context.value:
            lib.freecon(context)
        lib.selabel_close(handle)


def metadata_present(data):
    records = {}
    for line in data.decode().splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        path = fields[0]
        require(path not in records, f"Duplicate filesystem record: {path}")
        require(not path.startswith("system/lib/modules/"),
                f"Metadata describes descendants of a module symlink: {path}")
        records[path] = fields
    require(records.get("system/lib") == ["system/lib", "0", "0", "755", "capabilities=0x0"],
            "Unexpected or missing system/lib directory metadata")
    record = records.get(LINK_PATH.lstrip("/"))
    require(record is None or record == FS_ROW.split(), "Unexpected module symlink metadata")
    return record is not None


def link_state(path):
    if path.is_symlink():
        require(str(path.readlink()) == LINK_TARGET, f"Existing module symlink is wrong: {path}")
        info = path.lstat()
        return (info.st_dev, info.st_ino)
    require(not path.exists(), f"Refusing to replace an existing module file/directory: {path}")
    return None


def prepare(target, source, fs_config, libselinux, check_only=False):
    target, source = Path(target), Path(source).resolve()
    require(not target.is_symlink(), "Target-files root must not be a symlink")
    target = target.resolve()
    require(target.is_dir() and source.is_dir() and not target.is_relative_to(source)
            and not source.is_relative_to(target),
            "Use isolated target-files staging outside and separate from the source tree")
    libdir = confined(target, "SYSTEM/lib")
    require(libdir.is_dir(), "Missing real SYSTEM/lib staging directory")
    destination = libdir / "modules"
    original_link = link_state(destination)
    for relative in STALE_IMAGES:
        path = confined(target, relative)
        require(not os.path.lexists(path), f"Stale image must be excluded from NEW staging: {path}")
    snapshots = {}

    def remember(relative, required=True):
        path = confined(target, relative)
        state = file_state(path)
        require(state is not None or not required, f"Missing staging input: {path}")
        snapshots[path] = state
        return path

    config = remember("META/filesystem_config.txt")
    original = snapshots[config][-1]
    has_metadata = metadata_present(original)
    misc = remember("META/misc_info.txt")
    contexts = effective_contexts(target, snapshots[misc][-1])
    contexts = remember(contexts.relative_to(target))
    platform = remember("SYSTEM/etc/selinux/plat_file_contexts")
    for path in (contexts, platform):
        for suffix in CONTEXT_SIDECARS:
            sidecar = remember(path.relative_to(target).as_posix() + suffix, required=False)
            require(snapshots[sidecar] is None, f"Ambiguous contexts sidecar: {sidecar}")
    for name in ("fs_config_files", "fs_config_dirs"):
        remember("SYSTEM/etc/" + name, required=False)
    labels = {}
    for path in (contexts, platform):
        actual = lookup_context(path, libselinux)
        require(actual == LINK_CONTEXT, f"Unexpected module symlink context in {path}: {actual}")
        labels[path.relative_to(target).as_posix()] = {
            "context": actual, "sha256": hashlib.sha256(snapshots[path][-1]).hexdigest()}
    require(not check_only or (original_link is not None and has_metadata),
            "Check-only requires the canonical symlink and metadata to be staged already")

    created, temporary = None, None
    try:
        if original_link is None:
            destination.symlink_to(LINK_TARGET)
            created = link_state(destination)
        expected_link = created if created is not None else original_link
        if not has_metadata:
            result = subprocess.run(
                [str(fs_config), "-D", str(target / "SYSTEM"), "-C"],
                input=LINK_PATH.lstrip("/") + "\n", text=True, capture_output=True, check=True)
            require(result.stdout == FS_ROW, "Native fs_config returned unexpected symlink metadata")

        def unchanged():
            require(confined(target, "SYSTEM/lib") == libdir
                    and link_state(destination) == expected_link, "Module link changed while staging")
            for path, state in snapshots.items():
                confined(target, path.relative_to(target))
                require(file_state(path) == state, f"Staging input changed concurrently: {path}")
            for relative in STALE_IMAGES:
                require(not os.path.lexists(confined(target, relative)),
                        f"Stale image appeared while staging: {relative}")

        unchanged()
        if not has_metadata:
            separator = b"" if original.endswith(b"\n") else b"\n"
            with tempfile.NamedTemporaryFile(dir=config.parent, prefix=".modules-fs-",
                                             delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(original + separator + FS_ROW.encode())
            temporary.chmod(snapshots[config][2] & 0o777)
            unchanged()
            temporary.replace(config)
    except Exception:
        # Never remove a pre-existing link or another writer's replacement.
        if created is not None and destination.is_symlink():
            info = destination.lstat()
            if (info.st_dev, info.st_ino) == created and str(destination.readlink()) == LINK_TARGET:
                destination.unlink()
        raise
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return {"link": LINK_PATH, "target": LINK_TARGET, "mode": "0120644", "uid": 0, "gid": 0,
            "context": LINK_CONTEXT, "context_inputs": labels,
            "added_symlink": original_link is None, "added_fs_config": not has_metadata,
            "check_only": check_only, "images_built": False, "policy_modified": False}


def host_tools(source):
    require(sys.platform in ("darwin", "linux"), "Expected an Android Darwin/Linux host toolchain")
    host = Path(source) / "out/host" / ("darwin-x86" if sys.platform == "darwin" else "linux-x86")
    library = "libselinux.dylib" if sys.platform == "darwin" else "libselinux.so"
    return host / "bin/fs_config", host / "lib64" / library


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-files", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--fs-config", type=Path, help="Android host fs_config override")
    parser.add_argument("--libselinux", type=Path, help="Android host libselinux library override")
    parser.add_argument("--check-only", action="store_true",
                        help="Read-only validation; fail if the link or metadata is missing")
    args = parser.parse_args()
    try:
        fs_config, libselinux = host_tools(args.source_root)
        result = prepare(args.target_files, args.source_root, args.fs_config or fs_config,
                         args.libselinux or libselinux, args.check_only)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Module pre-image gate failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
