# LineageOS for Redmi Note 13 5G (gold)

Unofficial LineageOS 23.2 device adaptation: source patches, integration notes, and verification boundaries.

这是 Redmi Note 13 5G（`gold`）的非官方适配记录。目的：保留可审阅的改动和失败线索，供后续开发者接手。与 Xiaomi、MediaTek、LineageOS 官方无隶属关系。

**已生成新底包完整 OTA 测试候选，但尚未完成全新安装验收，也不是完整可复现的整包构建工程。** 已部署系统结合了 LineageOS 23.2 与 OS3/6.6 的启动及 vendor 组件；普通 `bacon` 尚未串联全部组装步骤。`main` 固定采用国行官方 **OS3.0.10.0.VNQCNXM** 底包；旧 OS3.0.9 组合和自编译 MDDP 候选保留在 [`experimental`](https://github.com/Redmi-Note-13-Gold/lineageos-gold/tree/experimental) 分支。

## 从这里开始

- [配套 Recovery](docs/RECOVERY.md)：保留官方 6.6 平台输入的候选整合方法与验证边界。
- [完整 OTA 构建与安装测试](docs/FULL_BUILD.md)：完整包离线结果、Recovery 缺口与测试进度。
- [功能与验收状态](docs/STATUS.md)：哪些已部署、哪些只做过离线验证。
- [源码恢复与应用顺序](docs/RESTORE.md)：精确基线、补丁、独立源码，以及尚缺的输入。
- [集成说明](docs/INTEGRATION.md)：IMS/eSIM、混合启动、Power HAL 和热点后端。
- [发布前检查](docs/VALIDATION.md)：补丁应用、来源比对与主机测试。
- [来源与许可](NOTICE.md)：保留上游作者和许可证，不将第三方代码改署名。
- [官方底包整合](docs/STOCK_BASE.md)：输入校验、增量镜像组装和本轮验证边界。
- [MDDP 实验](https://github.com/Redmi-Note-13-Gold/lineageos-gold/tree/experimental/experiments/mddp)：未刷入、未证明硬件加速成功。

## 目录

| 路径 | 内容 |
|---|---|
| `patches/` | 按 Android 项目划分的 23.2 补丁和应用清单 |
| `sources/` | 独立集成工具与 IMS 兼容源码 |
| `integration/` | 源码树之外的镜像级修复 |
| `firmware/` | 官方固件版本、来源和完整文件校验值 |
| `tools/` | 源码恢复、底包提取、增量组装与离线检查 |
| `manifests/` | 本次导出基线与来源记录 |
| `docs/` | 状态、恢复步骤、证据摘要 |

快照整理日期：2026-09-13。仅维护 23.2；不迁入旧版 Darwin 构建绕过、历史 permissive 调试或无关裁剪。没有发布账号凭据、设备原始日志、用户数据、ROM 镜像或厂商 APK。

提交问题时请描述底包版本、源码基线、补丁顺序、可复现步骤，并先清除日志中的号码、SIM 标识和设备序列号。未经覆盖测试的功能请不要从“编译成功”推断为“可用”。
