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

## 科研机挂载与路径恢复

仅适用于当前科研机的同一数据盘和物理目录。先核对 `tools/host/research-layout.json`：其中固定数据盘 UUID、source/lower/upper/work 及入口链接；它不负责从空盘恢复源码或厂商输入。`/srv/build/gold` 及 inputs/releases/jobs/logs 都是实际目录，只有外层 `build-gold.sh` 是入口链接。

系统已启用主线生成的 OverlayFS mount 单元。重启后先运行 `/srv/build/build-gold.sh --check-environment`；它不会尝试自动修复错误挂载。如果需要重新安装丢失的单元定义，在确认没有构建、盘已正确挂载、配置路径存在后执行：

```sh
set -e
project=/srv/build/gold/project
source_tree=/srv/build/gold/source
mount_unit=$(systemd-escape --path --suffix=mount "$source_tree")
unit_dir=$(mktemp -d)
python3 -B "$project/tools/host/check-research-layout.py" --print-mount-unit > "$unit_dir/$mount_unit"
systemd-analyze verify "$unit_dir/$mount_unit"
test ! -e "/etc/systemd/system/$mount_unit"
install -m 0644 "$unit_dir/$mount_unit" "/etc/systemd/system/$mount_unit"
systemctl daemon-reload
systemctl enable "$mount_unit"
```

仅当 source 当前未挂载时，再用 `systemctl start "$mount_unit"` 恢复；若已经挂载且与配置不符，应先排查，不能直接 stop/restart 或 remount。确认后删除本次临时单元文件和空目录，运行 `python3 -B "$project/tools/host/check-research-layout.py"` 与 `/srv/build/build-gold.sh --check-environment` 验证。2026-09-21 物理搬迁已正常卸载并重新挂载，挂载与同一 swap 文件在新位置已实测；随后 m nothing 构图与环境检查通过，输出及输入核对未变；整机重启恢复仍未实测。同步检查 fstab 中的 `/srv/build/gold/host/build.swap`、root Git include 的 `host/git-safe-directories.config` 与 Repo 本地 manifest URL 的 `host/manifest`，不得重新引入旧物理路径。

历史归档原路径通过 `/srv/build/gold/history/layout-moves-20260921.json` 定位。恢复只使用主线工具、固定原厂输入和当前提取配方，不运行历史迁移目录里的旧 Python 流程。


后续 Wi-Fi RRO、双击唤醒 Power 源码／策略与专用 attestation 属性都由主线 device 文件恢复；OpenEUICC 和状态栏修复由当前 patches/series.json 恢复。证明专用属性曾按 firmware 锁定的原厂 vendor/build.prop 设置，但 6e7c418 实机仍报 -66；该通用 vendor 身份不能当作 TEE 实际预置身份已获验证，需继续核对 gold_cn 变体，不用猜测值或 keybox 掩盖失败。继续保留官方 Global/CN 输入、kernel/modules、闭源 HAL／固件和固定 IMS APK；这些有明确构建或恢复用途，不因旧拼装退役而删除。


Gold WifiOverlay现补入匹配Global原厂RRO的SoftAP SAE能力布尔值，恢复合并源码时须核对这一XML的有效内容，避免upper层遮盖；不重写无关Android.bp。新增资源和最终vendor镜像APK门禁通过前不得冻结为可安装WPA3修复候选。当前用户禁止进一步设备重启，恢复/安装操作不得沿用此前重启授权越过这一最新限制。
