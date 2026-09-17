# 官方底包：Global Recovery

> 历史范围：本文记录 CN R1 与早期 Global 混合镜像流程。当前源码构建请以 [BUILD.md](BUILD.md) 为准；本文的通过结果不继承到新构建。

工作基线切换为 **gold Global MIXM OS3.0.5.0.VNQMIXM 完整 Recovery ZIP**，Android 15、系统补丁 2026-08-01、内核 6.6.118；Lineage 上层仍为 23.2 / Android 16。锁定记录见 [gold-global.json](../firmware/gold-global.json)。2026-09-14 重新查询时这是公开目录最新的 Global 稳定完整 Recovery；EEA EUXM、增量 OTA、Fastboot 均不混用。

**这是新迁移基线，不等于新 ROM 已编译或实机通过。** 已发布 R1 的 CN OS3.0.10 / 6.6.89 安装、启动、回读与尚未完成的硬件记录继续保留；[gold-cn.json](../firmware/gold-cn.json)、旧 `validation/*20260913*` 与 `clean-install-20260914.json` 不能改写成 Global 结果。

## 来源与校验

- 官方入口：[Recovery ZIP](https://bigota.d.miui.com/OS3.0.5.0.VNQMIXM/gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip)，[官方镜像](https://hugeota.d.miui.com/OS3.0.5.0.VNQMIXM/gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip)。官方镜像本次 Range 请求返回 206、总长 5,419,567,545 字节；主入口本地返回 403，不能把这一点当成版本不存在。
- MD5：`df9ff3aa93ea8ea98df428b13ceb20c3`。
- SHA-256：`35c9f1d98b28538ac10c319ad4cba993cd5a632960d9111162e3efa494dae5c9`，来自实际完整包计算，**不是小米签名发布的 SHA-256**。
- ZIP 内 `pre-device=gold`、`post-build-incremental=OS3.0.5.0.VNQMIXM`、`ota-type=AB`，无增量包所需旧版本条件。锁还固定完整 payload 与 metadata 哈希、25 个重建分区的大小和 SHA-256。
- ETag 未充当 MD5；ZIP/payload/partition 一致性验证不等于独立的小米签名信任链验证。

## 提取

使用已有 Linux Android 主机工具。脚本不下载，不安装，不运行原厂刷写脚本。

```sh
python3 tools/prepare-stock.py \
  --archive /path/to/gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip \
  --output /path/to/new-stock-staging \
  --host-bin /path/to/android/out/host/linux-x86/bin

python3 tools/prepare-stock.py \
  --verify-prepared --output /path/to/new-stock-staging
```

输出 `physical/*.img`、`logical/*.img`、`prepared.json`。先校验整 ZIP，再校验包内身份和 payload，使用 AOSP `ota_extractor`，最后逐个核对 25 个分区。只有全部通过才写完成清单。`--verify-prepared` 对锁和所有图片重新计算哈希；它可在原生 arm64 Mac 上运行，实际提取仍在 Linux 构建主机进行。

CN 历史提取显式加 `--lock firmware/gold-cn.json`。旧清单没有 `lock_sha256` 时，应保留旧记录并在新目录重新提取，不能把历史记录简单改成新 schema。

`physical/preloader_raw.img` 仅用于来源记录；现有组装和 OTA 分区集合不自动纳入它。原厂 `system/product/system_ext` 保留为 proprietary 提取参照，上层镜像仍必须来自 Lineage 构建。

## 组装与 Recovery 接口

`build-stock-base.py`、`build-recovery.py` 和 `verify-stock-base.py` 都默认读取 Global 锁；`--firmware-lock` 可明确选择 CN 历史锁。原先 `--lock` 仍是构建互斥文件，不改其含义。组装清单记录锁、原包、prepared 清单、构建脚本及 vendor 兼容补丁哈希。任何跨底包混搭在进入镜像改动前被拒绝。

```sh
python3 archive/hybrid/tools/build-stock-base.py \
  --source /path/to/android --stock /path/to/new-stock-staging \
  --lineage-images /path/to/matching-lineage-images \
  --output /path/to/new-assembly --lock /path/to/assembly.lock

python3 archive/hybrid/tools/build-recovery.py \
  --source /path/to/android --assembly /path/to/new-assembly \
  --lineage-vendor-boot /path/to/matching-lineage-vendor_boot.img \
  --output /path/to/new-recovery-assembly --lock /path/to/recovery.lock

python3 archive/hybrid/tools/verify-stock-base.py \
  --source /path/to/android --assembly /path/to/new-recovery-assembly \
  --apex-root /path/to/matching-lineage-apex-root
```

这些命令是已有上层镜像的离线组装与校验，不是整棵 Android 源码的重新编译。`verify-stock-base.py` 在严格 neverallow 检查失败时返回失败，同时保存问题数量；运行时策略可编译或 VINTF 通过不能覆盖此门槛。

## Global 必需的迁移处理

Global `mi_ext` 是 888,860,672 字节，包含 49 个 APK，其中六个是零字节遮挡：Calendar、Messaging、Contacts、Dialer、MtkCalendar、MtkContacts。还有 Google/Miui 实际应用、权限 XML、地区预装和渠道分成 init。仅删除 Messaging 后整张继承会混入原厂应用。

Global 组装现重建最小内容：保留 NOTICE、十条版本/region/IMEISV 属性和原目录骨架；移除其他文件、所有 APK 和 OEM init，回读验证内容及元数据。保留空目录让 vendor_boot 等外部 overlay 路径仍有目标，但其运行时挂载行为还要实机验证。CN 分支保留原来的单 Messaging 占位删除逻辑。

现有 `vendor-compat.patch` 在实际 Global 四个源文件上 `git apply --check` 通过，Global CIL 原文完整保留，仅追加已有兼容规则。它仍只涉及 boost 标签/权限、MDDP 节点、FCM 目标声明，并移除旧预编译策略缓存；这不是严格 SELinux 问题已解决的证明。

内核、vendor_boot 平台 ramdisk、system_dlkm、vendor_dlkm、odm_dlkm必须来自同包。Global 官方 kernel 的 SHA-256 是 `0281e33d7e25c54aa65a6460a8f3b86f7c414e520b88db3919ce7efaa12754f9`。Recovery 工具仅换 Lineage recovery fragment，其他 ramdisk、DTB、bootconfig 保持一致并重新校验 AVB；仍需真正的开机与安装验收。

## 尚需验收

1. 重新编译 Global 组合并逐项解决严格 SELinux neverallow；历史 CN 曾有 **27 项失败**，不能隐藏或通过 `-N` 当作通过。
2. 完整 target-files/OTA 与动态分区、AVB、FEC、Recovery ramdisk和兼容性检查。单纯组装成功不代表可复现源码构建完成。
3. Recovery 重入、升级安装及数据保留、启动链回读、普通与 VoLTE 通话/双卡、eSIM、热点 TCP/WH、GPU 帧积压、功耗、传感器等实机验收。

Global 的 IMS dex 与旧 CN 相同，热点和图形重点模块代码段未显示已修复，因此既有兼容补丁不能因底包升级直接删除。区域无线/基带配置有变化，不能预先承诺国内 SIM 或 WH 协商改善。

## 本轮离线执行记录

2026-09-14，新提取器使用实际官方 ZIP 重建并核验全部 25 个分区，退出 0；Global 组装重建 vendor/最小 mi_ext、元数据回读、完整 AVB 链与两分区 FEC 均通过，退出 0。见 `validation/global-assembly-20260914.json`。本轮复用 CN R1 的 Lineage 上层镜像，只验证新底包的离线接入，`clean_source_build`、`device_flashed`、`hardware_verified` 均为 false。

随后真实 Global Recovery 重建退出 0，平台/init_boot ramdisk、DTB、bootconfig 保留并通过 AVB；内核锁、运行时策略、property contexts、VINTF、Lineage Messaging 和最小 mi_ext 两文件/版本检查均通过。**严格 neverallow 仍失败 27 项，兼容性子进程退出 1，兼容验收未通过**。外层收集服务的退出 0 不能覆盖该失败。见 `validation/global-compatibility-20260914.json`。这 27 项是本次 Global 组合重新运行的结果；完整源码构建、严格策略收敛和实机验收仍未完成。

## 最终源码与运行记录的对应

远端实跑的产物保留当时构建脚本的真实哈希。之后本地修正了自定义 ODM 输入文件名的目标链接，并统一构建前底包校验；这些变化已通过 14 项针对性测试。没有把此前运行记录中的脚本哈希改写成新值。已发布 CN R1 和原始官方输入未被修改。
