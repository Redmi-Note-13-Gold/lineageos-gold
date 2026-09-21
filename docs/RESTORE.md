# 恢复固定源码与输入

使用独立的 Repo 源码目录，保留现有工作区。下面的集成工具路径指向本仓库的完整检出目录。

## Android 源码

```sh
repo init -u https://github.com/Redmi-Note-13-Gold/lineageos-gold \
  -b main -m manifests/lineage-23.2-gold.xml
repo sync -c -j8

git -C external/openeuicc submodule update --init --recursive
```

本仓库 manifest 固定 1160 个项目的提交。设备树的历史起点仍保留，应用本仓库完整 device 源码后成为当前维护版本；避免同时维护另一份 device 补丁。厂商文件不由 Repo 自动取得。

## 应用本项目源码

```sh
python3 /path/to/lineageos-gold/tools/apply-patches.py /path/to/android
python3 /path/to/lineageos-gold/tools/apply-patches.py /path/to/android --apply
```

默认只检查；显式应用前检查各目标项目固定提交、工作区及补丁。执行后，device 采用本仓库完整源码，平台只应用 `patches/series.json` 中的差异，vendor 仅复制本项目 IMS 集成源码。已有未记录文件不应被覆盖；被中断的应用需先检查工作区，不要直接重复套补丁或清理。

必要的只读启动观察工具及回归测试已归入 `tools/capture_boot.py` 和 `tests/test_capture_boot.py`。本项目目录中没有安装到设备树的 `hybrid_*` 主机工具。旧工具与镜像补丁已退出工作树；追溯时读取 Git 提交 `0fed0d2e8f5d60fa1c7e5a3ecbe4a18377e5964f` 的 `archive/hybrid/` 原路径，恢复和构建均不需要检出或执行它们。

## 准备厂商组件并构建

按 [BUILD.md](BUILD.md) 从固定 Global Recovery 准备 vendor/firmware/kernel，再运行标准完整产品构建。IMS 的固定兼容 APK 和 `input.json` 已归入主线 Git，恢复步骤直接复制，不需要旧检出或旧镜像；输入不符时入口明确失败。

预编译内核与固件是有来源、版本和校验值的输入；它们与设备树来源分别记录。厂商修改应维护在提取规则中。构建入口已移除额外的源码比对和 vendor receipt 检查。

恢复工具不安装依赖、不刷机、不公开发布。构建是否实际完成，以本次生成的构建记录为准。

## 科研机挂载与导航恢复

仅适用于当前科研机的同一数据盘和物理目录。先核对 `tools/host/research-layout.json`：其中固定数据盘 UUID、现有 source/lower/upper/work 和导航链接；它不负责从空盘恢复源码或厂商输入。`/srv/build/gold` 及 inputs/releases/jobs/logs 均只是导航，不能用复制整个源码的方式修复链接。

系统已启用主线生成的 OverlayFS mount 单元。重启后先运行 `/srv/build/build-gold.sh --check-environment`；它不会尝试自动修复错误挂载。如果需要重新安装丢失的单元定义，在确认没有构建、盘已正确挂载、配置路径存在后执行：

```sh
set -e
project=/srv/build/migration/gold-architecture-20260914/project
source_tree=/srv/build/migration/gold-architecture-20260914/source
mount_unit=$(systemd-escape --path --suffix=mount "$source_tree")
unit_dir=$(mktemp -d)
python3 -B "$project/tools/host/check-research-layout.py" --print-mount-unit > "$unit_dir/$mount_unit"
systemd-analyze verify "$unit_dir/$mount_unit"
test ! -e "/etc/systemd/system/$mount_unit"
install -m 0644 "$unit_dir/$mount_unit" "/etc/systemd/system/$mount_unit"
systemctl daemon-reload
systemctl enable "$mount_unit"
```

仅当 source 当前未挂载时，再用 `systemctl start "$mount_unit"` 恢复；若已经挂载且与配置不符，应先排查，不能直接 stop/restart 或 remount。确认后删除本次临时单元文件和空目录，运行 `python3 -B "$project/tools/host/check-research-layout.py"` 与 `/srv/build/build-gold.sh --check-environment` 验证。2026-09-21 的安装没有重启或重挂，重启恢复仍是未实测项。

历史归档原路径通过 `/srv/build/gold/history/layout-moves-20260921.json` 定位。恢复只使用主线工具、固定原厂输入和当前提取配方，不运行历史迁移目录里的旧 Python 流程。
