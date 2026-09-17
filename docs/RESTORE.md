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

本项目目录中已没有安装到设备树的 `hybrid_*` 主机工具。旧工具与镜像补丁归档在 `archive/hybrid/`，不属于源码恢复步骤。

## 准备厂商组件并构建

按 [BUILD.md](BUILD.md) 从固定 Global Recovery 准备 vendor/firmware/kernel，再运行标准完整产品构建。IMS 必须提供指定哈希的兼容 APK；缺少它时入口明确失败，不能通过缺依赖开关绕过。

预编译内核与固件是有来源、版本和校验值的输入；它们与设备树来源分别记录。厂商修改应维护在提取规则中。构建入口已移除额外的源码比对和 vendor receipt 检查。

恢复工具不安装依赖、不刷机、不公开发布。构建是否实际完成，以本次生成的构建记录为准。
