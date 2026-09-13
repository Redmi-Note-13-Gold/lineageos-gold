#!/usr/bin/env python3
"""Check and repair property initialization in the OS3/Lineage gold hybrid.

All modifications are confined to a new output directory. No device commands
are executed, and neither the source tree nor existing packages are modified.
"""

import argparse
import configparser
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile


SOURCE_ROOT = Path(__file__).resolve().parents[4]
PROPERTY_FILES = {
    "SYSTEM": "plat_property_contexts",
    "SYSTEM_EXT": "system_ext_property_contexts",
    "VENDOR": "vendor_property_contexts",
    "PRODUCT": "product_property_contexts",
    "ODM": "odm_property_contexts",
}
# Keep the stock vendor's ownership. Do not change shared Lineage/MTK policy.
CONFLICTS = {
    "persist.vendor.pco5.radio.ctrl": (
        "u:object_r:system_mtk_pco_prop:s0",
        "u:object_r:vendor_mtk_radio_prop:s0",
    ),
    "vendor.camera.aux.packagelist": (
        "u:object_r:vendor_persist_camera_prop:s0",
        "u:object_r:vendor_persist_camera_prop:s0",
    ),
}
OVERLAY_IMAGES = {"system", "vendor_boot", "vbmeta_system", "vbmeta"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def repair_contexts(system_ext, vendor):
    """Remove only the two audited, untyped prefix rules, with vendor proof."""
    def entries(text, name):
        return [line.split() for line in text.splitlines()
                if line.split() and line.split()[0] == name]

    removed = []
    for name, (system_context, vendor_context) in CONFLICTS.items():
        system_rules = entries(system_ext, name)
        if not system_rules:
            continue
        for rules, context in ((system_rules, system_context),
                               (entries(vendor, name), vendor_context)):
            require(len(rules) == 1 and rules[0] in (
                [name, context], [name, context, "prefix"]),
                f"{name}: expected exactly one audited untyped prefix rule")
        removed.append(name)
    return "".join(line for line in system_ext.splitlines(keepends=True)
                   if not line.split() or line.split()[0] not in removed), removed


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeTools:
    def __init__(self, source, host, logs):
        self.source = source
        self.host = host
        self.logs = logs
        self.env = dict(os.environ, PATH=f"{host}{os.pathsep}{os.environ['PATH']}",
                        PYTHONDONTWRITEBYTECODE="1")

    def run(self, tool, *args, log=None, check=True):
        command = [str(self.host / tool), *map(str, args)]
        result = subprocess.run(command, cwd=self.source, env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if log:
            (self.logs / log).write_bytes(
                (shlex.join(command) + "\n").encode() + result.stdout + result.stderr)
        if check and result.returncode:
            raise RuntimeError(f"{tool} failed ({result.returncode}):\n"
                               + (result.stdout + result.stderr).decode(errors="replace"))
        return result


def policy_files(roots):
    vendor = roots["VENDOR"] / "etc/selinux"
    version = (vendor / "plat_sepolicy_vers.txt").read_text().strip()
    require(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", version), "Invalid policy version")
    system = roots["SYSTEM"] / "etc/selinux"
    files = [system / "plat_sepolicy.cil", system / f"mapping/{version}.cil"]
    optional = [system / f"mapping/{version}.compat.cil"]
    for partition, stem in (("SYSTEM_EXT", "system_ext"), ("PRODUCT", "product")):
        directory = roots[partition] / "etc/selinux"
        optional += [directory / f"{stem}_sepolicy.cil", directory / f"mapping/{version}.cil"]
        if partition == "SYSTEM_EXT":
            optional.append(directory / f"mapping/{version}.compat.cil")
    files += [path for path in optional if path.is_file()]
    files += [vendor / "plat_pub_versioned.cil", vendor / "vendor_sepolicy.cil"]
    odm = roots["ODM"] / "etc/selinux/odm_sepolicy.cil"
    if odm.is_file():
        files.append(odm)
    genfs_file = vendor / "genfs_labels_version.txt"
    genfs = genfs_file.read_text().strip() if genfs_file.exists() else "0"
    require(genfs.isdigit(), "Invalid genfs labels version")
    genfs_cil = system / f"plat_sepolicy_genfs_{genfs}.cil"
    if genfs_cil.is_file():
        files.append(genfs_cil)
    return files


def validate(roots, native, work, label):
    policy = work / f"{label}.sepolicy"
    native.run("secilc", *policy_files(roots), "-m", "-M", "true", "-G", "-N",
               "-c", "30", "-o", policy, "-f", os.devnull, log=f"{label}-secilc.log")
    contexts = [roots[part] / "etc/selinux" / name
                for part, name in PROPERTY_FILES.items()]
    contexts = [path for path in contexts if path.is_file()]
    return native.run("property_info_checker", policy, *contexts,
                      log=f"{label}-properties.log", check=False)


def parse_avb(avbtool, path):
    handler = avbtool.ImageHandler(str(path), read_only=True)
    avb = avbtool.Avb()
    footer, header, descriptors, size = avb._parse_image(handler)
    blob = avb._load_vbmeta_blob(handler)
    require(avbtool.verify_vbmeta_signature(header, blob), f"Invalid AVB signature: {path}")
    offset = header.SIZE + header.authentication_data_block_size + header.public_key_offset
    public_key = blob[offset:offset + header.public_key_size]
    return footer, header, descriptors, size, public_key


def partition_descriptor(avbtool, descriptors, name):
    matches = [desc for desc in descriptors
               if isinstance(desc, avbtool.AvbHashtreeDescriptor) and desc.partition_name == name]
    require(len(matches) == 1, f"Expected exactly one {name} hashtree descriptor")
    return matches[0]


def resign(avbtool, source, replacement, key, output):
    _, header, descriptors, size, public_key = parse_avb(avbtool, source)
    require(public_key == avbtool.RSAPublicKey(str(key)).encode(),
            "Signing key does not match the existing vbmeta_system key")
    require(header.public_key_metadata_size == 0, "Public-key metadata is unsupported")
    new = partition_descriptor(avbtool, parse_avb(avbtool, replacement)[2], "system_ext")
    old = partition_descriptor(avbtool, descriptors, "system_ext")
    updated = [new if desc is old else desc for desc in descriptors]
    algorithm, _ = avbtool.lookup_algorithm_by_type(header.algorithm_type)
    blob = avbtool.Avb()._generate_vbmeta_blob(
        algorithm_name=algorithm, key_path=str(key), public_key_metadata_path=None,
        descriptors=updated, chain_partitions_use_ab=None, chain_partitions_do_not_use_ab=None,
        rollback_index=header.rollback_index, flags=header.flags,
        rollback_index_location=header.rollback_index_location, props=None, props_from_file=None,
        kernel_cmdlines=None, setup_rootfs_from_kernel=None, ht_desc_to_setup=None,
        include_descriptors_from_image=None, signing_helper=None, signing_helper_with_files=None,
        release_string=header.release_string, append_to_release_string=None,
        required_libavb_version_minor=header.required_libavb_version_minor)
    require(len(blob) <= size, "Replacement vbmeta exceeds original image size")
    output.write_bytes(blob + bytes(size - len(blob)))
    _, result_header, result_descriptors, _, result_key = parse_avb(avbtool, output)
    require([desc.encode() for desc in result_descriptors] == [desc.encode() for desc in updated],
            "Unexpected AVB descriptor change")
    require(result_key == public_key, "AVB public key changed")
    for field in ("flags", "rollback_index", "rollback_index_location", "algorithm_type"):
        require(getattr(result_header, field) == getattr(header, field), f"AVB {field} changed")


def image_file(native, image, path):
    # debugfs can return zero on an invalid command. Check its output as well.
    result = native.run("debugfs_static", "-R", f"cat {path}", image)
    require(b"not found" not in result.stderr and b"File not found" not in result.stderr,
            f"Missing {path} in {image}")
    return result.stdout


def build(args, source, host, roots):
    target = args.target_files.resolve()
    output = args.output.resolve()
    require(not output.exists(), f"Output already exists: {output}")
    for path in (source, target, *roots.values()):
        require(not output.is_relative_to(path), "Output must be outside all input trees")
    require((target / "OTA/android-info.txt").read_text().strip() == "board=gold",
            "Only gold target-files are supported")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temp:
        stage = Path(temp)
        work = stage / "work"
        logs = stage / "logs"
        work.mkdir()
        logs.mkdir()
        native = NativeTools(source, host, logs)
        avbtool = load_module("gold_avbtool", source / "external/avb/avbtool.py")
        images = {p.stem: p for p in (target / "IMAGES").glob("*.img")}
        if args.overlay_images:
            for name in OVERLAY_IMAGES:
                path = args.overlay_images.resolve() / f"{name}.img"
                require(path.is_file(), f"Missing diagnostic overlay image: {path}")
                images[name] = path
        if args.system_dir:
            require(args.overlay_images, "--system-dir requires --overlay-images")
        require(bool(args.overlay_images) == bool(args.system_dir),
                "Diagnostic overlay requires its matching --system-dir")

        before = validate(roots, native, work, "before")
        message = (before.stdout + before.stderr).decode(errors="replace")
        require(before.returncode != 0 and "Duplicate prefix match detected" in message,
                "Baseline does not reproduce the audited property initialization failure")
        print(message.strip(), flush=True)
        original = roots["SYSTEM_EXT"] / "etc/selinux/system_ext_property_contexts"
        vendor = roots["VENDOR"] / "etc/selinux/vendor_property_contexts"
        repaired, removed = repair_contexts(original.read_text(), vendor.read_text())
        require(removed, "No audited duplicate rules found")
        require(image_file(native, images["system_ext"], "/etc/selinux/system_ext_property_contexts")
                == original.read_bytes(), "system_ext image does not match target-files")
        for file in [*policy_files(roots), roots["SYSTEM"] / "etc/selinux/plat_property_contexts"]:
            if file.is_relative_to(roots["SYSTEM"]):
                relative = file.relative_to(roots["SYSTEM"]).as_posix()
                require(image_file(native, images["system"], f"/system/{relative}") == file.read_bytes(),
                        f"System image does not match policy input: {relative}")

        staged_ext = work / "SYSTEM_EXT"
        shutil.copytree(roots["SYSTEM_EXT"], staged_ext, symlinks=True)
        patched = staged_ext / "etc/selinux/system_ext_property_contexts"
        patched.write_text(repaired)
        patched_roots = dict(roots, SYSTEM_EXT=staged_ext)
        after = validate(patched_roots, native, work, "after")
        require(after.returncode == 0,
                "Native property validation still fails:\n"
                + (after.stdout + after.stderr).decode(errors="replace"))
        print(f"Native property validation passed; removed: {', '.join(removed)}", flush=True)

        _, _, descriptors, partition_size, _ = parse_avb(avbtool, images["system_ext"])
        tree = partition_descriptor(avbtool, descriptors, "system_ext")
        parser = configparser.ConfigParser(interpolation=None, delimiters=("=",))
        parser.read_string("[image]\n" + (target / "META/misc_info.txt").read_text())
        info = parser["image"]
        require(info["system_ext_fs_type"] == "ext4", "Only ext4 system_ext is supported")
        filesystem = native.run("tune2fs", "-l", images["system_ext"]).stdout.decode()
        inode_count = re.search(r"^Inode count:\s+(\d+)$", filesystem, re.MULTILINE)
        require(inode_count is not None, "Cannot determine the original ext4 inode count")
        props = {
            "mount_point": "system_ext", "partition_name": "system_ext", "fs_type": "ext4",
            "partition_size": str(partition_size), "disable_sparse": "true",
            "ext_mkuserimg": str(host / "mkuserimg_mke2fs"), "journal_size": "0",
            "extfs_rsv_pct": "0", "timestamp": "1230768000",
            "extfs_inode_count": inode_count.group(1),
            "fs_config": str(target / "META/system_ext_filesystem_config.txt"),
            "selinux_fc": str(target / "META/file_contexts.bin"),
            "avb_enable": "true", "avb_hashtree_enable": "true", "avb_salt": tree.salt.hex(),
            "avb_avbtool": str(host / "avbtool"),
            "avb_add_hashtree_footer_args": info["avb_system_ext_add_hashtree_footer_args"]
                + f" --hash_algorithm {tree.hash_algorithm} --fec_num_roots {tree.fec_num_roots}",
        }
        properties = work / "system_ext_image_info.txt"
        properties.write_text("".join(f"{key}={value}\n" for key, value in props.items()))
        new_image = stage / "system_ext.img"
        print("Rebuilding system_ext and its AVB hashtree...", flush=True)
        native.run("build_image", staged_ext, properties, new_image, roots["SYSTEM"],
                   log="build-system_ext.log")
        native.run("e2fsck", "-fn", new_image, log="filesystem-check.log")
        require(new_image.stat().st_size == partition_size, "Partition size changed")
        require(image_file(native, new_image, "/etc/selinux/system_ext_property_contexts")
                == patched.read_bytes(), "Built image contains incorrect property contexts")
        shutil.copy2(patched, stage / "system_ext_property_contexts")
        key = args.key.resolve() if args.key else source / "external/avb/test/data/testkey_rsa4096.pem"
        resign(avbtool, images["vbmeta_system"], new_image, key, stage / "vbmeta_system.img")

        # Build a read-only view of the complete chain, including the unchanged
        # stock-signed boot and diagnostic system when one was explicitly selected.
        chain = work / "chain"
        chain.mkdir()
        merged = dict(images, system_ext=new_image, vbmeta_system=stage / "vbmeta_system.img")
        for name, path in merged.items():
            (chain / f"{name}.img").symlink_to(path)
        for desc in parse_avb(avbtool, images["vbmeta"])[2]:
            if isinstance(desc, avbtool.AvbChainPartitionDescriptor):
                child = merged[desc.partition_name]
                require(parse_avb(avbtool, child)[4] == desc.public_key,
                        f"Top-level AVB chain key mismatch: {desc.partition_name}")
        native.run("avbtool", "verify_image", "--image", chain / "vbmeta.img",
                   "--follow_chain_partitions", log="avb-full-chain.log")

        inputs = {name: {"path": str(path), "sha256": sha256(path)}
                  for name, path in images.items() if name in (
                      "system", "system_ext", "product", "vendor", "odm", "vendor_boot",
                      "boot", "dtbo", "vbmeta", "vbmeta_system", "vbmeta_vendor")}
        manifest = {
            "device": "gold", "hardware_boot_verified": False,
            "removed_system_ext_prefixes": removed, "inputs": inputs,
            "changed_partitions": ["system_ext", "vbmeta_system"],
            "requires_unchanged_top_level_vbmeta": inputs["vbmeta"],
            "outputs": {name: sha256(stage / name)
                        for name in ("system_ext.img", "vbmeta_system.img")},
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (stage / "SHA256SUMS").write_text("".join(
            f"{digest}  {name}\n" for name, digest in manifest["outputs"].items()))
        shutil.copy2(properties, logs / properties.name)
        shutil.rmtree(work)
        stage.rename(output)
    print(f"Verified repair package: {output}\nNo partitions were flashed.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "build"))
    parser.add_argument("--target-files", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--host-bin", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overlay-images", type=Path)
    parser.add_argument("--system-dir", type=Path)
    parser.add_argument("--key", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    host = (args.host_bin or source / "out/host/darwin-x86/bin").resolve()
    roots = {part: args.target_files.resolve() / part for part in PROPERTY_FILES}
    if args.system_dir:
        roots["SYSTEM"] = args.system_dir.resolve()
    if args.command == "build":
        if not args.output:
            parser.error("build requires --output (a new directory)")
        build(args, source, host, roots)
        return 0
    with tempfile.TemporaryDirectory(prefix="gold-property-check-") as temp:
        work = Path(temp)
        result = validate(roots, NativeTools(source, host, work), work, "check")
        print((result.stdout + result.stderr).decode(errors="replace").strip()
              or "Native SELinux and property initialization checks passed.")
        return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
