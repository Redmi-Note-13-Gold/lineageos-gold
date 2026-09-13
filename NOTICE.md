# 来源与许可

这是多来源补丁集合，不对所有文件统一改署名或声称重新授权。

| 内容 | 来源与许可处理 |
|---|---|
| Android / LineageOS / Gold 设备树差异 | 基线仓库和提交见 `patches/series.json`；保留原文件版权头和许可证。常见为 Apache-2.0，具体以原项目/文件为准 |
| codec2 集成源码 | 保留 Android Open Source Project 的原始版权头；属于已有 MediaTek/AOSP 适配输入，不声明为本项目从零编写 |
| OpenEUICC 两处修改 | PeterCxy/OpenEUICC 与其贡献者，GPL-3.0；只分发差异，完整上游许可证收录于 `LICENSES/GPL-3.0.txt` |
| OpenEUICC 的 lpac/cJSON 子模块与依赖 | 通过固定上游仓库获取，保留各自许可证；本仓库不复制二进制依赖或图标素材 |
| experimental 分支的 MDDP 实验补丁与提取测试代码 | MediaTek 原始实现，来自 Motorola 公开发布的内核模块源码，GPL-2.0；原文件 `SPDX-License-Identifier: GPL-2.0`。内核许可文本见 `LICENSES/GPL-2.0.txt` |
| TelephonyMetrics Java 兼容层 | LineageOS `android_hardware_lineage_compat`，精确提交及源文件哈希见 `compat/provenance.json`，保留 AOSP 版权头 |
| 厂商 IMS smali 差异 | 仅记录互操作修改及必要上下文，不分发完整厂商应用，不声称拥有或重新许可原厂代码 |
| 本项目新增的说明文档、恢复工具和原创测试/集成代码 | Apache-2.0；如果文件包含第三方实现或已有许可证，以对应文件及上表为准 |

Apache-2.0 完整文本见 `LICENSES/Apache-2.0.txt`。修改补丁的许可随其所修改代码的适用条款，不能从此目录的存在推断整个 Android/厂商代码都可按同一许可使用。

本仓库源码树发布源码差异、集成工具及验证摘要，不纳入厂商二进制。配套测试 ROM 和官方底层组件通过单独的 Pre-release 提供，具体内容、来源和未验收项目以该 Release 说明为准；不将厂商二进制称为开源源码，也不声明重新许可第三方组件。设备原始日志、私人密钥、云账号资料和个人标识不在发布范围。

## 致谢

感谢 [mt6833-devs/android_device_xiaomi_gold](https://github.com/mt6833-devs/android_device_xiaomi_gold) 的维护者与贡献者。本项目直接继承其 `lineage-23.0` 设备树（HyperOS 1 / 5.10 基线），固定起点为 [`d3d941c29395ce770b95b735b27bd28e6a8c6946`](https://github.com/mt6833-devs/android_device_xiaomi_gold/commit/d3d941c29395ce770b95b735b27bd28e6a8c6946)，并在此基础上继续适配 LineageOS 23.2。保留上游原有版权声明与许可证。

当前 R1 测试包使用 OS3.0.10.0.VNQCNXM 官方提供的 6.6.89 内核镜像；设备树的继承来源与当前内核二进制来源分别记录。
