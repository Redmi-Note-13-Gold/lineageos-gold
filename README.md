# LineageOS 23.2 for Redmi Note 13 5G (`gold`)

当前开发源码已纳入 Global 标准构建迁移及 2026-09-16 的启动、硬件服务和关机充电修复。最终 `userdebug-charger-final-20260916` 增量镜像已刷入 B 槽，14 项分区回读和正常开机验证通过；充电图案在包含相同永久修复的诊断版上获实机确认。详细边界见 [当前状态](docs/STATUS.md)。本次先推送源码，暂不重建或验证包含全部最新修复的完整安装包，也不发布新的 ROM Release。

本项目维护 Gold 的设备适配、固定源码基线与构建输入。当前架构采用标准 Android 构建：设备树描述最终分区和启动链，从锁定的国际版 Recovery 提取厂商组件，再生成完整 target-files 与 OTA。

**维护底包：Global OS3.0.5.0.VNQMIXM / Android 15 / kernel 6.6.118。** 固定归档与分区校验值见 [firmware/gold-global.json](firmware/gold-global.json)。预编译内核和闭源组件属于明确的构建输入，不要求从源码重建原厂闭源实现。

## 使用入口

- [当前修复与验收状态](docs/STATUS.md)：已部署结果和待验收功能。
- [构建与验证](docs/BUILD.md)：当前源码构建流程与未完成项。
- [恢复源码](docs/RESTORE.md)：固定 manifest、平台补丁和本地设备源码。
- [ROM 更新设计](docs/UPDATES.md)：首次迁移、后续 OTA 与签名策略，尚未启用更新服务。
- [来源与许可](NOTICE.md)：上游设备树、参考适配及闭源输入的来源。

## 维护结构

| 路径 | 职责 |
|---|---|
| `device/xiaomi/gold/` | 产品、分区、启动、HAL、overlay、源码 SELinux、厂商提取规则 |
| `vendor/xiaomi/gold/` | 本项目 IMS 集成；其余厂商构建文件与闭源组件由提取生成 |
| `vendor/xiaomi/gold/proprietary/kernel/` | 提取生成的固定内核、DTB、DTBO 和内核模块输入；不纳入源码仓库 |
| `manifests/`、`patches/` | 固定 Android 项目与确有需要的平台差异 |
| `firmware/` | 原厂输入的来源、版本、尺寸和哈希 |
| `tools/` | 输入准备、源码应用、标准构建与产物检查 |
| `archive/hybrid/` | 已退出主构建路径的镜像改写工具与历史兼容补丁 |
| `validation/` | 带日期的验证记录；历史通过不能视为新版本通过 |

标准构建从源码生成系统镜像。2026-09-14 的 Global `user` 完整包曾通过离线校验，最终 SCP-only 包含 14 个 OTA 分区，见 [历史完整包记录](validation/repack-scp-only-20260914.json)；该结果早于后续实机修复。2026-09-16 的最新部署是 `userdebug` 增量镜像验证，见 [实机修复摘要](validation/device-fixes-20260916.json)。完整硬件、包含最新修复的完整包和保数据 OTA 尚未验收。

构建入口已移除额外的源码/厂商输入预检查及 `input-receipt.json` 机制，准备好输入后直接进入配置和编译；原包提取检查及构建后的产物验证由各自入口完成。本次 24 项主机工具测试通过，见 [源码更新记录](validation/source-update-20260917.json)。

## 已发布版本

[CN R1 测试版](https://github.com/Redmi-Note-13-Gold/lineageos-gold/releases/tag/lineage-23.2-20260913-r1) 使用 OS3.0.10.0.VNQCNXM / 6.6.89，曾通过全新安装和首次启动，完整硬件及 OTA 更新验收未完成。其 [安装说明](docs/INSTALL_TEST.md) 与 [状态记录](docs/STATUS_R1.md) 仅适用于该发布版本，不适用于本次 Global 源码迁移。

本仓库不存放签名密钥、设备原始日志、用户数据或原厂 APK/ROM 镜像。未授权刷机、发布和远端推送不属于构建步骤。

## 致谢

设备树继承自 [mt6833-devs/android_device_xiaomi_gold](https://github.com/mt6833-devs/android_device_xiaomi_gold)，固定起点为 `d3d941c29395ce770b95b735b27bd28e6a8c6946`，保留原始版权与许可证。本次 6.6 迁移参考 [Dhterech/android_device_xiaomi_gold](https://github.com/Dhterech/android_device_xiaomi_gold/tree/lineage-23.2)，具体采用内容与固定版本见设备提取记录和 NOTICE。

本项目与 Xiaomi、MediaTek、LineageOS 官方无隶属关系。
