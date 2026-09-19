# 标准 Android 构建

2026-09-17：当前源码已包含后续实机修复，部署和验收范围见 [STATUS.md](STATUS.md)。本次只推送源码，暂不重建或验证最新完整安装包。

主路径为固定源码 + Global 官方提取输入 → `bacon target-files-package` → 官方工具验证。设备配置负责最终分区、boot/vendor_boot、模块和策略；不读取旧 R1 镜像，不调用 `archive/hybrid/`。

## 输入

使用原生 Linux x86_64 Android 构建环境。固定的 Repo 源码和本仓库 device/vendor 集成通过 [RESTORE.md](RESTORE.md) 准备。Mac 仅用于审阅与主机脚本测试。

固件固定为 `firmware/gold-global.json` 指定的 Global 完整 Recovery；先由 `tools/prepare-stock.py` 提取到含 `physical/`、`logical/`、`prepared.json` 的独立目录。提取器的参数见 `--help`。

在已恢复的 Android 源码中执行：

```sh
python3 device/xiaomi/gold/prepare-vendor.py \
  --tree /path/to/android \
  --lock /path/to/lineageos-gold/firmware/gold-global.json \
  --stock /path/to/prepared-stock \
  --ims-apk /path/to/ImsService.apk
```

此入口验证全部 25 份原厂镜像，调用标准 extract-utils 生成 vendor 构建定义、闭源组件与固件，并提取匹配的 boot、kernel、DTB、DTBO 和 modules 到 `vendor/xiaomi/gold/proprietary/kernel/`。Android 使用源码重建 vendor_boot 与 DLKM 镜像，并将当前构建生成的 generic ramdisk 作为 `init_boot` 片段装入 vendor_boot。

随包底层固件仅保留锁定国际版 `scp`，以 [proprietary-firmware.txt](../device/xiaomi/gold/proprietary-firmware.txt) 为准。`md1img`、`lk`、`preloader_raw`、`dpm`、`gz`、`mcupm`、`spmfw`、`sspm`、`tee` 和 `pi_img` 均不随此系统包更新。完整官方输入的 25 份镜像及哈希仍保留，用于来源与提取验证。

当前产品配置为 14 个 OTA 分区，包括 `dtbo` 与 `odm_dlkm`；9 月 14 日完整包的 target-files 与 payload 已核实该数量。选择国际版 SCP 不等于已证明与 Google 套件、小爱或 Google 语音功能的对应关系；该兼容性仍未验证。

2026-09-14 的 SCP-only `user` 完整包包含 14 个分区，RADIO 仅 `scp.img`；当时的 target-files、VINTF、OTA/payload 签名与 AVB/策略检查通过，见 [历史记录](../validation/repack-scp-only-20260914.json)。其后 `userdebug` 启动与硬件修复采用增量镜像验证，旧完整包的结果不代表当前全部改动通过。此前 22 分区包为历史，四项固件/17 分区方案没有生成新包。

IMS 是独立锁定输入：`--ims-apk` 要求 SHA-256 为 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1` 的已有 23.2 兼容版本。其来源与部分重建配方见 `vendor/xiaomi/gold/ims/`；从原厂 APK 重建该版本的完整流程尚未闭合。不能用任意同名 APK 替代，也不能声称当前所有输入均可从 Recovery 独立还原。

厂商修正维护在提取清单和 fixup 中，以便后续提取保留修复。已移除 vendor receipt 的生成、验证和构建前源码比对；已有生成输入可直接用于增量开发。

## 构建

```sh
python3 /path/to/lineageos-gold/tools/build-source.py \
  --tree /path/to/android \
  --lunch lineage_gold-bp4a-user \
  --out /path/to/android/out-gold-standard \
  --jobs 8 --build-datetime UNIX_TIMESTAMP --execute
```

`UNIX_TIMESTAMP` 替换为本次固定构建时间。省略 `--execute` 只显示计划。`userdebug` 可用于开发调试；正式 `user` 构建检查无 permissive 域。上游 userdebug 的 su/osi/backuptool 调试声明与全局关闭 SELinux 需区分。入口拒绝 neverallow/缺依赖/ELF 检查绕过和关闭 AVB 的配置。

默认目标同时构建 `bacon` 与 `target-files-package`。输出目录必须在源码树内，传入构建系统时使用相对路径。独立输出目录防止将旧 R1 产物当成新结果；同目录允许本入口记录过的增量构建。构建前不额外扫描固定源码项目、比较本地改动或校验 vendor receipt，也不在构建过程中重复比对源码哈希。构建后使用 Android 自带验证工具检查 target-files、VINTF 与 OTA 签名，并核验时间戳、分区一致性与源码策略。

测试密钥只用于开发构建；正式发布需要持久保存的发布密钥及独立签名步骤。入口不刷机、不发布、不推送仓库。

## 验证边界

2026-09-14 的架构改动与实际验证结果见 `validation/architecture-20260914.json`。原包提取、配置展开、源码编译、完整 OTA 验证、实机安装及保数据升级是不同结果，不能相互替代。历史 `validation/integration-20260914.json` 记录的是旧 Global 混合镜像流程，其 27 项严格策略失败不能作为新源码构建的结果。

历史标准 `user -j8` 完整构建记录见 [standard-build-20260914.json](../validation/standard-build-20260914.json)，当时包内策略无 permissive 域，Neverallow 与 Treble 测试通过。最新增量镜像和启动摘要见 [device-fixes-20260916.json](../validation/device-fixes-20260916.json)。当前完整安装包验证暂缓；本次主机工具测试不计作 Android 编译或整包验收。
