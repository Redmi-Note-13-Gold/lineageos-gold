# 新底包完整 OTA 构建与安装测试

日期：2026-09-13。已生成 LineageOS 23.2 + 官方 OS3.0.10.0.VNQCNXM 的完整 A/B OTA 候选包，**尚未完成全新安装或实机验收，不作为已验证发行版提供**。

## 当前测试候选：Recovery R1

`lineage-23.2-20260913-UNOFFICIAL-gold-OS3.0.10.0-recovery-r1.zip` 已纳入配套 Lineage Recovery，是接下来全新安装测试的候选。大小 **1,741,273,388 字节**，SHA-256：

```text
cf04a5d81fb6b897165978f0b0982fd67ec0128585fdc234d8f5cef4b3a20a74
```

与下述原始完整包相比，仅 vendor_boot 和对应 vbmeta 两个分区变化。新包已重新验证整包/payload 签名、25 个分区的完整解包比对、AVB、9 个逻辑分区的 FEC、VINTF 与运行时策略编译。严格 neverallow 仍有 27 项失败。

[机器可读验证记录](../validation/full-build-recovery-r1-20260913.json)。**实机测试进行中，首次 sideload 暴露了旧布局兼容问题；最新结果见下节，不能把该候选称为已验收发行版。**

## 2026-09-14 实机进度

已在解锁的 gold 上从旧 LineageOS 23.2 / OS3.0.9 组合开始测试。先备份并核对两槽共 32 个启动/固件分区，再向 A 槽写入 R1 配套 LK、boot、DTBO、vendor_boot、vbmeta。五个写入分区回读一致，B 槽 16 个原启动/固件分区保持不变。

Lineage Recovery 已启动，报告 23.2-20260913 和官方 6.6.89 内核，显示初始化为 1080×2400/60Hz，ADB shell 可用。USB 曾短暂显示未授权，重连 ADB transport 后恢复；没有据此宣称该 USB 现象已经修复。

data 和 metadata 已由 Recovery 菜单清除成功。首次 sideload 的主机退出码为 0，但 Recovery 明确返回 **status 7 / Installation aborted**，因此不能把 ADB 传输成功当成安装成功。

失败发生在动态分区创建阶段：旧手工刷入的 A 槽分区位于 `default` 组，且存在历史 COW 项；更新器清除目标槽分组后，仍遇到重名 `system_b`。已保存原 super 元数据，用最终构建对应的 `super_empty.img` 执行标准 `fastboot wipe-super`，重建干净分组后开始第二次 sideload。**第二次结果、首次启动与硬件验收仍待完成。** 这是从旧 Lineage 环境开始的测试，不是从完整 HyperOS 原厂状态完成的验证。[实机记录](../validation/clean-install-20260914.json)。

### 干净动态分区布局

此步骤会移除 super 内两槽旧系统的逻辑分区，仅用于已经备份并明确选择全新安装的场景，不用于保留数据的普通升级。适用范围目前是本次旧手工混合布局；尚未证明所有官方底包都必须执行。

在具备 Android 主机工具的编译环境，从**最终新底包 target-files** 的 metadata 生成：

```sh
build_super_image /path/to/final-target-files/META/misc_info.txt super_empty.img
```

已验证此原生命令可复现同一文件：大小 5496 字节，SHA-256 `a1292477aab16a07e323dbf40846ffb88d2a41ebc55abc87470bf4838e0e4881`。它描述 9,126,805,504 字节的 super、A/B 两组各 9 个零长度逻辑分区，不包含系统文件或用户数据。

设备处于已解锁 Fastboot，确认设备、槽位和备份后，使用 [AOSP fastboot 的 wipe-super 命令](https://android.googlesource.com/platform/system/core/+/7c84b9fea2937c467adb257e27a9cac0ce40f24d%5E%21/)：

```sh
fastboot wipe-super super_empty.img
```

本次已成功执行。仍须回到配套 Recovery，通过 sideload 安装完整 OTA；不能启动空的旧系统。完整的终端用户安装步骤会在流程验证结束后定稿。

## 本轮构建

现有 Linux 编译树执行 `m -j8 bacon` 成功，用时 8 分 29 秒，复用了编译缓存；这是完整产品目标与完整 OTA，不能称为清空缓存重编或空目录恢复验证。system、system_ext、product 和 ODM 来自本轮构建，之后完成 hybrid 适配并结合匹配的官方下层镜像。

普通 `bacon` 仍未自动串联全部组装步骤，其直接输出不是新底包最终交付包。独立依赖及 IMS 重建限制仍见 [RESTORE.md](RESTORE.md)。本轮没有消除该恢复缺口。

原始完整包（使用官方 Recovery，已被上面的 R1 测试候选取代）：`lineage-23.2-20260913-UNOFFICIAL-gold-OS3.0.10.0.zip`。

- 大小：1,748,044,291 字节。
- SHA-256：`4bbe36ea5179b3d80c9df5c74a0df09b7671aad848777c1b040f5a8edd7b5f26`。
- 系统：Android 16 / LineageOS 23.2-20260913；官方内核 6.6.89。
- 包含 25 个分区；其中 10 个为匹配的 LK、基带等官方固件。未包含 userdata，未设置 wipe/downgrade 标志。
- 使用公开开发测试密钥，不能用于锁定 bootloader，也未完成正式发行密钥流程。

## 离线结果

| 检查 | 结果 |
|---|---|
| 完整产品构建 | 成功，复用缓存 |
| ZIP CRC、整包签名、payload 签名及哈希 | 通过 |
| 最终 payload 解包 | 25 个分区大小及 SHA-256 全部与构建输入一致 |
| AVB | 最终解包镜像的完整链验证通过 |
| FEC | 9 个逻辑分区独立重编码比对通过 |
| VINTF、property contexts、运行时策略编译 | 通过 |
| 严格 SELinux neverallow | **既有 27 项失败仍在** |
| 全新安装、启动、硬件功能 | **未验收** |

机器可读结果见 [full-build-20260913.json](../validation/full-build-20260913.json)。离线成功不代表 OTA 可以在 Recovery 中实际安装。

## 正在验证的用户安装流程

按“刷入配套 Lineage Recovery → 格式化 data → adb sideload 完整包 → 首次启动 → 再次进入 Recovery”测试，随后核对基础硬件和已有修复。

原始 OTA 使用官方 vendor_boot；普通源码单独生成的 Recovery 又使用另一套内核输入。R1 已纳入配套 Lineage Recovery 并完成整包离线检查，见 [RECOVERY.md](RECOVERY.md)；安装后仍能进入该 Recovery 的实机验证尚未完成。未解决前不提供可照抄的刷机命令，也不把开发期间分区直刷成功当作用户安装验收。

格式化 data 会清除应用、账号和内部存储文件。实际测试的清除、安装、首次启动及功能结果将分项记录；不发布设备序列号、SIM 标识或原始个人日志。
