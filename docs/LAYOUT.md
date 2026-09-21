# 目录与环境

以科研机实际检出为唯一维护和执行依据，本地同步同一 Git 提交。日常从 `/srv/build/gold` 进入；它是现有工作区的导航链接，不创建另一份工程。

## 日常入口

```text
/srv/build/gold/                         -> migration/gold-architecture-20260914
├── project/                            主线 Git：源码、工具、文档、验证结论
├── source/                             Android OverlayFS 挂载点
│   └── out-gold-standard/              唯一日常增量输出
├── inputs/                             -> /srv/build/stock-rom，官方原始输入
├── releases/                           -> /srv/build/releases/gold
│   ├── index.json                      候选真实路径、记录与包哈希
│   └── <时间-提交>/                    已有候选的导航链接；未来冻结候选直接存这里
├── jobs/                               -> /srv/build/build-jobs，执行请求与结果
├── logs/                               -> /srv/build/logs
├── history/                            不再维护或执行的实验与迁移材料
│   ├── migration-20260912-14/          56 项原外层迁移材料
│   ├── source-experiments-20260914-19/ 51 项原历史实验材料
│   ├── vendor-preparation/             32 项旧提取备份、日志与检查结果，以及 last-workspace 旧缓存
│   ├── initial-build-records-20260914/ 原 source-out，仅历史构建记录
│   └── layout-moves-*.json             原路径到归档路径的映射
├── source-upper/                       OverlayFS 修改层，直接操作会破坏活动挂载
└── source-work/                        OverlayFS 工作目录
```

构建命令仍只有 `/srv/build/build-gold.sh`，指向 `project/tools/host/build-research.sh`。Git、Repo、Soong 和输出继续使用原物理路径；导航链接不会改变构建工作区身份、缓存键或输出归属。

## 主线源码

```text
project/
├── README.md                 当前入口
├── device/xiaomi/gold/       设备配置、init、overlay、HAL、SELinux、提取配方
├── vendor/xiaomi/gold/ims/   IMS 集成、固定 APK 与输入说明
├── manifests/               固定 Android 项目提交
├── patches/                 平台补丁及 series.json
├── firmware/                Global/CN 官方输入锁
├── tools/                   恢复、提取、构建、产物验证与候选索引
│   └── host/                科研机入口、路径契约、挂载校验与 VM guard
├── tests/                   主机工具测试和明确授权使用的设备探针
├── docs/                    当前最终文档
│   └── releases/CN-R1.md    已发布 CN 版本最终说明
├── validation/              构建、安装、实机与宿主结构的脱敏证据
├── LICENSES/
└── NOTICE.md
```

旧 hybrid 运行代码、内部补丁和重复测试已退出此检出；15 个原路径及依据见 ADAPTATION.md，历史由 Git 提交 `0fed0d2e8f5d60fa1c7e5a3ecbe4a18377e5964f` 保存。服务器历史材料中的旧脚本只是证据，不是第二个构建入口。除明确锁定的 IMS prebuilt 外，源码仓库不保存生成的厂商组件；用户日志、完整镜像和密钥不入 Git。

## 物理路径与恢复

以下物理目录保持原位，不能因别名或相似文件名而当作重复数据删除：

| 路径 | 作用 |
|---|---|
| `/srv/build/migration/gold-architecture-20260914/project` | 唯一主线 Git 检出 |
| `/srv/build/migration/gold-architecture-20260914/source` | OverlayFS 挂载点及唯一输出所在树 |
| `/srv/build/lineage-23.2-gold` | OverlayFS lower，迁入的 Android 基础树 |
| `/srv/build/migration/gold-architecture-20260914/source-upper`、`source-work` | 修改层与挂载工作目录 |
| `/srv/build/stock-rom` | 官方 Global/CN 镜像与来源记录 |
| `/srv/build/releases/gold` | 冻结候选入口；现有 8 项通过链接指向原存储，不复制包 |
| `/root/ccache` | 系统盘上的实际编译缓存，非符号链接 |
| `/srv/build/gold-build-swapfile` | 数据盘 24 GiB swap，fstab 已持久化 |
| `/srv/build/gold-git-safe-directories.config` | root 对源码确切仓库路径的 Git 信任清单 |
| `/srv/build/home` | 旧构建账户历史资料，不作为 HOME 或构建入口 |

`tools/host/research-layout.json` 管理本机路径和数据盘 UUID。`check-research-layout.py` 只读核对数据盘、准确的 overlay 挂载点、lower/upper/work、输出与导航链接；构建入口在写输出前自动调用它。源目录未挂载、挂错层或误用其他磁盘会明确失败。

该工具的 `--print-mount-unit` 从同一配置生成 systemd 挂载定义。科研机已安装普通文件到 `/etc/systemd/system/`，单元为 `systemd-escape --path --suffix=mount <source物理路径>` 的结果，已启用并匹配现有挂载。配置和现有活动状态已验证；此次没有重挂或重启，不能声称重启恢复已经实测。恢复命令见 [RESTORE](RESTORE.md)。

## 历史与候选管理

2026-09-21 将 141 项历史根文件或目录在同一文件系统内重命名归档，逐项核对 inode；没有删除内容。完整原路径映射在 `/srv/build/gold/history/layout-moves-20260921.json`。历史记录内部绝对路径保持原文，通过映射定位；不要执行其中的旧流程来准备新候选。旧提取备份可能含唯一输入，归档不等于授权删除。原 vendor 准备区中的 9 条固件链接在整理前已经失效，现连同 dump/tree/work 整体归入 `history/vendor-preparation/last-workspace`；当前构建图无引用。有效厂商组件仍在 `source/vendor/xiaomi/gold`，重新提取使用主线 `prepare-vendor.py`，默认临时目录为 `source/.repo/gold-vendor-extraction`，不能复用旧缓存冒充完整的已验证输入。

原 `source-out` 只有两份历史构建记录，已归入 history；原外层 migration 现在只保留活动工作区。旧局部输出 `source/out-gold-betterr-20260917` 和空诊断输出仍原位保留，不用作新构建输出；它们涉及 OverlayFS，本次没有清理。

已有冻结候选的物理路径仍是 `source/out-gold-standard/target/product/gold/verified-candidates/<时间-提交>`。新的完整冻结候选放入 `/srv/build/releases/gold/<时间-提交>`，连同当次工具、输入说明、构建记录和验证结果一起保存；使用完整内容复制并验证，不能硬链接会被下一次构建改写的包。活动输出仍只有原 out-gold-standard。

用 `python3 /srv/build/gold/project/tools/index-candidates.py /srv/build/releases/gold --verify-hashes` 生成只读 JSON 清单，再原子替换 `index.json`。省略校验参数只读已有记录和文件大小，输出会明确标记没有重读包哈希。索引不根据目录名称授予验收状态，不设置容易误用的“最新可刷”别名；安装和硬件结论以 [STATUS](STATUS.md) 与对应 validation 为准。

硬件为 8 vCPU、约 14 GiB 可见 RAM、23 GiB 可见 swap，数据盘总容量 344 GiB。本次整理不释放大文件空间；剩余容量按现场检查。宿主变更证据统一归入 [host-layout-20260920.json](../validation/host-layout-20260920.json)，执行明细位于 `jobs/gold-mainline-20260920/structure-refactor-20260921.json`。
