# 来源与许可

这是多来源补丁集合，不对所有文件统一改署名或声称重新授权。

| 内容 | 来源与许可处理 |
|---|---|
| Android / LineageOS / Gold 设备树差异 | 基线仓库和提交见 `patches/series.json`；保留原文件版权头和许可证。常见为 Apache-2.0，具体以原项目/文件为准 |
| codec2 集成源码 | 保留 Android Open Source Project 的原始版权头；属于已有 MediaTek/AOSP 适配输入，不声明为本项目从零编写 |
| OpenEUICC 两处修改 | PeterCxy/OpenEUICC 与其贡献者，GPL-3.0；只分发差异，完整上游许可证收录于 `LICENSES/GPL-3.0.txt` |
| OpenEUICC 的 lpac/cJSON 子模块与依赖 | 通过固定上游仓库获取，保留各自许可证；本仓库不复制二进制依赖或图标素材 |
| MDDP 实验补丁与提取测试代码 | MediaTek 原始实现，来自 Motorola 公开发布的内核模块源码，GPL-2.0；原文件 `SPDX-License-Identifier: GPL-2.0`。内核许可文本见 `LICENSES/GPL-2.0.txt` |
| TelephonyMetrics Java 兼容层 | LineageOS `android_hardware_lineage_compat`，精确提交及源文件哈希见 `compat/provenance.json`，保留 AOSP 版权头 |
| 厂商 IMS smali 差异 | 仅记录互操作修改及必要上下文，不分发完整厂商应用，不声称拥有或重新许可原厂代码 |
| 本项目新增的说明文档、恢复工具和原创测试/集成代码 | Apache-2.0；如果文件包含第三方实现或已有许可证，以对应文件及上表为准 |

Apache-2.0 完整文本见 `LICENSES/Apache-2.0.txt`。修改补丁的许可随其所修改代码的适用条款，不能从此目录的存在推断整个 Android/厂商代码都可按同一许可使用。

本次整理只做文档去历史环境化、测试夹具匿名化、主机编译警告清理与补丁编排；不将构建研究中的厂商二进制转成所谓“开源源码”。固件、设备日志、平台密钥、云账号资料和个人标识均不在发布范围。
