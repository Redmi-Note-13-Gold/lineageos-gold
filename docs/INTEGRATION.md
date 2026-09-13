# 集成说明

## IMS / VoLTE

IMS 并不是给 LineageOS 增加一套通用“打开 VoLTE”的开关。这里适配的是 Gold 上的厂商 IMS 应用与 23.2 框架之间的接口、动态广播注册规则和权限。

1. v5 修复为动态广播提供明确的 export 标志，并在视频能力不可用时保护视频相关调用。`sources/vendor/xiaomi/gold/ims/patches/receiver-and-video-guard.patch` 的基线是**已补齐依赖的 v1 smali 树**，不能直接套在任意原厂 APK 上。
2. 23.2 需要补充旧 `TelephonyMetrics` 接口。`compat/rebuild.py` 从固定 v5 输入创建额外 `classes2.dex`，保留原有 47 项有效载荷。兼容 Java 源码来自 LineageOS，版本和校验值见 `compat/provenance.json`。
3. 权限与 framework/telephony/carrier overlay 配套。运营商 overlay 的 MCC 460 / MNC 01 是有意限定的；编译保留原始值中的前导零，不以全局强制属性冒充支持。
4. APK 由产品构建使用自己的 platform key 签名。这里不提供厂商 APK、私钥或可直接安装包。

**恢复缺口：** 当前配方能从经过校验的 v5 payload 重建 23.2 兼容版本，但尚没有从任意原厂 APK 自动还原 v1/v5 依赖闭包的完整公开流程。缺少该输入时，不能声称整个 IMS 已可独立重建。此限制不影响审阅 Java 兼容层、smali 差异、权限及 overlay。

## OpenEUICC

已逐文件比对当前构建输入和公开源码：

- OpenEUICC `9a537a25163c5159899260fb6191a5da35a692bd`，含固定 lpac/cJSON 子模块；738 个文件中仅 2 个有改动，其余 736 个哈希一致。
- 两处差异：系统 SIM 设置作为管理入口，修正可移除 eUICC 的物理槽位排除判断。
- openeuicc-deps `67a341e9cfbaed43da7e5a281f5cc7b8893fdc55`：23 个文件全部哈希一致，包括 JAR/AAR。无需重复上传依赖二进制，也无需额外依赖补丁。
- Soong、JNI、原生入口和大部分权限均已有上游实现；本项目不把这些原有功能标成自己新增。

卡上的 EF_MSISDN 为空时，这两处修复不会产生本机号码。不要把号码显示问题与 eUICC profile 管理混为一谈。

## Power HAL 与 MDDP

普通源码策略先应用设备补丁，再应用 R3 的 restorecon 精确标签补丁。R3 原来在独立镜像上修复，因此公开序列显式补入该变化。

对 OS3 hybrid vendor，还需要 `integration/power-hal/vendor-file-contexts.patch`：它针对**已包含前一轮窄范围 CIL 权限的 staging vendor**，不能只改标签就假定完整策略已集成。原部署保持 Enforcing；已有 hybrid 策略与普通源码策略的严格检查结果应分开解读。

`integration/mddp/ueventd.patch` 只修复 `/dev/mddp` 所有者和模式。HAL 能打开设备后，仍受基带 WH 能力及握手限制。实验目录的模块候选不在源码默认序列中，也不替换主树 5.10 预编译模块。

## 混合启动与打包

可读工具位于 `sources/device/xiaomi/gold/tools/`，恢复到 Android 源码的同一路径后使用。它们分别处理重复 property contexts、zygote 一致性、模块路径及只读启动观察，附带无设备测试。

实际系统还涉及 OS3 启动链、odm、匹配的 6.6 模块分区、mi_ext 对 Messaging 的遮挡处理，以及后续 vendor 策略组装。这些尚未成为可从空目录执行的统一构建入口。不要用普通 `bacon` 的成功替代 hybrid AVB/FEC、分区回读、开机和硬件验收；也不要把本仓库当成 OTA 包。

## 其他设备差异

设备补丁保留 KeyMint 执行标签及窄范围权限、双 zygote 注册、重复双卡属性清理、USB gadget 构建配置、memtrack/mdota 模块名适配、wlan_assistant init 清单调整，以及显示/刷新率/NTP overlay。`hardware/mediatek` 的 codec2 集成源码保留原 AOSP 版权头。

这些是当前构建树的移植差异，并不意味着每一项都可作为独立上游修复提交。准备送上游时仍需拆分问题、审查基线和补足相关验证。
