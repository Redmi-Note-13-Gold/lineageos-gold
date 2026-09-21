# 目录与环境

科研机是唯一维护和执行依据，本地同步同一 Git 提交。`/srv/build/gold` 是实际工作区；源码、输入、候选和宿主配置都已归入其中。

## 日常入口

```text
/srv/build/
├── build-gold.sh -> gold/project/tools/host/build-research.sh
├── gold/
│   ├── project/              主线 Git：源码、工具、文档、验证结论
│   ├── source/               Android OverlayFS 挂载点
│   │   └── out-gold-standard/ 唯一日常增量输出
│   ├── source-base/          Android 基础树，OverlayFS lower
│   ├── source-upper/         OverlayFS 修改层
│   ├── source-work/          OverlayFS 工作目录
│   ├── inputs/               官方 Global/CN 镜像与来源记录
│   ├── releases/             独立冻结候选的实际目录
│   │   ├── index.json        包路径、原始记录与哈希索引
│   │   └── <时间-提交>/      包、同次工具和验证证据
│   ├── jobs/                 执行请求、脚本与终态证据
│   ├── logs/                 构建及诊断日志
│   ├── host/
│   │   ├── manifest/         Repo 当前使用的本地 manifest Git 仓库
│   │   ├── git-safe-directories.config
│   │   └── build.swap        原数据盘 24 GiB swap，同一文件
│   └── history/              不再维护或执行的历史材料
│       ├── migration-20260912-14/
│       ├── source-experiments-20260914-19/
│       ├── vendor-preparation/
│       ├── initial-build-records-20260914/
│       ├── retired-build-home/
│       └── layout-moves-*.json
└── lost+found/               ext4 文件系统目录
```

统一构建命令仍为 `/srv/build/build-gold.sh`。除这个入口链接外，上述工作区目录均为实际目录。ccache 继续使用系统盘的 `/root/ccache`，root 构建的 HOME 仍为 `/root`。

`source-base`、`source-upper`、`source-work` 共同支撑唯一的 `source` 视图，并非三份可独立构建的工程。只在合并后的 `source` 中集成和构建；挂载活动时不能直接改写底层。

## 主线源码

```text
project/
├── README.md
├── device/xiaomi/gold/       设备配置、init、overlay、HAL、SELinux、提取配方
├── vendor/xiaomi/gold/ims/   IMS 集成、固定 APK 与输入说明
├── manifests/               固定 Android 项目提交
├── patches/                 平台补丁及 series.json
├── firmware/                Global/CN 官方输入锁
├── tools/                   恢复、提取、构建、产物验证与候选索引
│   └── host/                科研机入口、路径契约、挂载校验与 VM guard
├── tests/                   主机工具测试和明确授权使用的设备探针
├── docs/                    当前最终文档及 releases/CN-R1.md
├── validation/              构建、安装、实机与宿主结构的脱敏证据
├── LICENSES/
└── NOTICE.md
```

旧 hybrid 运行代码、内部补丁和重复测试已退出检出；15 个原路径及依据见 [ADAPTATION](ADAPTATION.md)，历史由 Git 提交 `0fed0d2e8f5d60fa1c7e5a3ecbe4a18377e5964f` 保存。历史材料中的脚本仅作证据。固定 IMS prebuilt 由主线管理；生成的厂商组件、用户日志、完整镜像和密钥不入源码 Git。

## 宿主路径与恢复

`tools/host/research-layout.json` 是当前路径和数据盘 UUID 的唯一配置。`check-research-layout.py` 只读检查磁盘、准确的 overlay 挂载点、lower/upper/work、实际目录和构建入口链接；构建入口在写输出前自动调用。缺失或不匹配时明确失败。

系统已启用 `srv-build-gold-source.mount`，对应普通文件由同一配置的 `--print-mount-unit` 生成。`/etc/fstab` 使用 `/srv/build/gold/host/build.swap`，root Git include 使用 `host/git-safe-directories.config`，Repo 的本地 manifest URL 使用 `host/manifest`。Git 信任清单仍为确切路径，没有通配信任。

2026-09-21 在确认无活动构建后正常卸载、迁移并重新挂载 OverlayFS；没有强制/懒卸载，没有重启服务器。swap 停用后同盘重命名，再启用原文件；未清理缓存或重建 swap。新位置的挂载和 swap 已实测，整机重启恢复仍未实测。恢复步骤见 [RESTORE](RESTORE.md)。

唯一输出保留原目录 inode；仅更新主线归属标记的 source_tree。输出中的 `.top` 与绝对链接交由 Soong 原生搬迁逻辑处理，不批量替换生成的 Ninja 内容。`/srv/build/build-gold.sh --check-build-graph` 在相同输出中执行 `m nothing`，与正式构建共用源码互斥锁；它验证新路径构图，不授予 ROM 构建或实机通过结论。2026-09-21 14:56:55 +08 已 exit 0，构图耗时 01:01:37；guard 退出且 VM 实读恢复 0/zbud/N/Y，输出 inode 9437191、161 项输入与 1158 个 Repo 提交保持，环境检查通过，无 OOM。终态见 [宿主证据](../validation/host-layout-20260920.json)。

## 历史与候选管理

先前已将 141 项历史根文件或目录同盘重命名归档；本次继续将旧构建 HOME 收入 `history/retired-build-home`。原 `goldbuild` 账户的 HOME 同步指向该处；它不作为日常构建账户。旧提取备份可能含唯一输入，归档不代表可删除。原准备缓存中 9 条固件链接在整理前已经失效，随缓存保留；当前准备工具使用 `source/.repo/gold-vendor-extraction`，不依赖旧缓存。

`history/layout-moves-20260921.json` 的原始记录保持不变，新增 `physical_followup` 给出旧绝对路径到现路径的映射；冻结 candidate.json 及历史日志同样保留原文。不能直接执行历史脚本恢复新构建。

8 个已有冻结候选已从活动输出移到 `/srv/build/gold/releases/<时间-提交>`，均为真实目录；14 个 ZIP 的 inode、大小、mtime 保持一致，重读 SHA-256 全部匹配原始记录。后续候选直接冻结到该目录，不在活动输出内再保留第二套候选。冻结时保存同次工具、输入说明、构建记录和验证结果；不能硬链接会被下一次构建覆盖的包。

用 `python3 /srv/build/gold/project/tools/index-candidates.py /srv/build/gold/releases --verify-hashes` 生成 JSON 清单，再原子替换 `index.json`。省略校验参数只读记录和大小。索引不根据目录名授予验收状态；安装与硬件结论以 [STATUS](STATUS.md) 和对应 validation 为准。

旧局部输出 `source/out-gold-betterr-20260917` 和空诊断输出仍保留，不用作日常输出。本次未删除历史镜像或唯一输入，没有复制大目录或释放大文件空间。现场硬件为 8 vCPU、约 14 GiB 可见 RAM、23 GiB 可见 swap，数据盘 344 GiB；剩余容量以实时检查为准。

执行明细在 `/srv/build/gold/jobs/gold-mainline-20260920/physical-layout-20260921.json`；脱敏结论统一更新 [host-layout-20260920.json](../validation/host-layout-20260920.json)。


2026-09-21夜间，releases/index.json含9个冻结候选，最新6e7c418已安装B槽。完成独立冻结包的SHA-256重读后，清理活动输出中同次OTA两硬链接路径及target-files一个路径，释放约3.80GiB，output inode9437191保留。原路径到现存冻结包的映射在 `jobs/gold-mainline-20260920/wpa3-active-package-duplicates.json`；不修改冻结candidate.json，不删除历史候选或官方输入。后续完成构建的包允许同盘移动入新的实际releases目录并解除所有活动输出硬链接，以免再占一份完整包空间；工具、输入、结果与哈希仍完整冻结和独立复验。
