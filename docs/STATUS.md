更新于 2026-09-21 05:12（UTC+8）。主线为 Global OS3.0.5.0.VNQMIXM / 6.6.118 / LineageOS 23.2，目标 `lineage_gold-bp4a-userdebug`。接手基线 462fab1，未回退到 c7c2c04。

**尚不可删除旧 hybrid Python 流程。** 完整迁移对照与 15 项条件删除清单见 [ADAPTATION](ADAPTATION.md)；本轮未删除归档、历史镜像或唯一输入，未公开推送。

最新源码 `bd50b19ef82575790eb455c6cb1d712a482d62b7` 已同步科研机，161 项实际合并输入完全匹配。新增 Codec2 主线入口后，仅重新生成 vendor 构建定义，差异只有旧可执行文件模块及产品条目的移除；未重提取或删除原输入。`gold-codec-r5-20260921.service` 于 05:06 启动，BUILD_DATETIME=1789938387，日志 `/srv/build/logs/gold-codec-r5-20260921.log`，**尚在构建**。独立 guard 为 `gold-codec-r5-vm-guard-20260921.service`。复用唯一 `source/out-gold-standard`、jobs=2、原内存／swap 上限、OverlayFS 和缓存；构建活动期间不修改远端源码。

手机当前为 **2cca323 原镜像、B 槽、incremental 1789933740**，boot_completed=1、Enforcing。标准 update_engine 保数据安装以 kSuccess(0) 结束，安装器与独立分区回读各 14 项全部匹配；原镜像正常启动、正常系统→Recovery→正常系统往返均通过。Recovery 自动 ADB 已实测，无需菜单；正常系统 ADB 仍鉴权。共享 display idle 节点保持原 root:root 0440，没有沿用 c36757a 的临时 DAC 改动。data/persist 挂载和内部 canary 通过，snapshot none；共享存储 canary 仍待用户首次解锁。

**Codec2 稳定性未通过。** 2cca323 首次创建 MTK AVC 编码器时发生 SIGSEGV，客户端重试后完成编码／41 帧解码并不能算无崩溃通过。LLDB、匹配库哈希和 DWARF 确认：原厂入口为 ComponentStore 只分配 336 字节，当前主线对象需要 352 字节，崩溃落在组件表插入。bd50b19 将当前平台头文件编译的 AIDL 入口纳入 `device/xiaomi/gold/codec2/`，保留匹配 MTK 库、原服务身份和沙箱；仅为实测崩溃报告的二次 SIGSYS 增加 `uname`。新入口尚未完成 Android 构建及实机冷启动／反复创建验证，旧版源码入口的价值不能再判为已被原厂二进制等价替代。

| 验证层次 | 当前实际结果 |
|---|---|
| 主线工具 | bd50b19 的 75 项 Python 测试通过；无 archive 导出 75 项与 IMS 哈希证明属于 2cca323，不充当新 Android 构建证明 |
| 2cca323 构建／安装 | Android 13:34、入口 exit 0；14 payload／29 实际文件、签名、VINTF、SELinux 通过；保数据 OTA、B 槽 14 分区独立回读通过 |
| 2cca323 原镜像启动／Recovery | 两次启动观察 exit 0、各稳定约 20 秒；Recovery 自动 ADB 和往返通过，Recovery 全局 Enforcing、Health 位于 hal_health_default；不是全部 Recovery 硬件验收 |
| 2cca323 Power 实机 | ARM64／ARM 各 27+32 确定性测试；两 ABI 实际 C 接口的申请、聚合、更新、独立释放和超时通过；所有者退出后小于 340 ms 回收，早于 2 秒期限；HAL 重启后旧句柄不能释放新票值 |
| 2cca323 Power 节点 | 受控停止／恢复 HAL 的 150 ms 探针完成 uclamp=10、1048000 kHz 频率下限写入／读回／到期复位；另行通过运行中 Enforcing HAL 的 C ABI 探针，未用 root 节点探针代替权限验收 |
| Power 诊断与收益 | 普通 shell dump 的 FIFO AVC 和 Lineage userdebug 的 ro.debuggable=0 导致调试门拒绝，已在 3cb28c3 修复并编译；尚未上机。额外 LAUNCH／INTERACTION 默认 0，可比启动／帧时间／能耗未测试 |
| IMS | 2cca323 正常启动及 Recovery 往返后均绑定、mtkIms Binder 存在、双槽 MMTEL READY；**未注册、能力未就绪**。有效 carrier config 已应用但 VoLTE=false，漫游 eSIM 语音资格未知；未改 SIM／强制运营商，未拨号或发短信 |
| Wi-Fi／网络 ADB | PMF vendor overlay=1 已安装；新扫描未见保存的测试热点，关联／DHCP／联网／重连未完成，网络 ADB 未启用 |
| Codec2 | **2cca323 稳定性失败，bd50b19 修复构建中**；仍需服务冷启动首次编码、多次创建／销毁、解码及相应硬件验证 |
| 3cb28c3 候选 | Android 13:14、入口 exit 0；14 payload／29 实际文件及全部签名／VINTF／SELinux 门禁通过，Linux 27+32 通过；冻结保存但未安装，等待包含 Codec2 修复的下一候选 |

2cca323 不可变候选：`verified-candidates/20260921-040925-2cca323/`，OTA SHA-256 `08e6744536c973a10e4dfa6c4cefff56167d2c16265045f3d9c4af452640adbf`，target-files `b2f9e564bde9f9834da8f66e53a52443320e87dfc7cb9b97b4ebcfa0202f1ef3`。3cb28c3 为 `verified-candidates/20260921-045747-3cb28c3/`，OTA `2b4840d4bdc7bc358ebb87ce2fbdd21da04c75bdcce6b4f69a96a9fcf3b38228`、target-files `e32739f2532f3c7fa8cdd5e85828642b48eae950f80ed3d51f5edbd8b5c25e1e`；同次工具、检查输入与测试 ELF 均已冻结。r3、r4 guard 都已退出且实读恢复 0/zbud/N/Y；r5 guard 当前随构建活动。

固定 IMS APK 是主线普通 Git blob，SHA-256 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1`。47 个载荷和兼容 dex 已核验；完整原厂依赖打包配方不完整是明确的 prebuilt 限制，本身不要求保留旧 Python 工作目录。IMS 实际可用性仍未闭合。

c36757a 的原始启动失败、临时 DAC 定位，以及 3ee80e9 neverallow 失败都保留为历史证据，不挪给 2cca323 或新候选。当前是 userdebug/test-keys，不冒充正式发行签名。首次解锁、测试热点可见和 eSIM 语音套餐条件已询问，等待用户答复；现有设备授权持续有效，不重复请求。2cca323 的临时测试 ELF、LLDB server、自建媒体、dex 和端口转发已清理，调试进程已退出。

详情见 [聚合证据](../validation/mainline-convergence-20260920.json)。

以下内容仅保留为历史验收记录，不表示当前待装候选已经通过。

## 9 月 20 日 IMS 修正版产物

科研机以实际 UID 0 构建，Android 构建耗时 1:28:17。复用原 `out-gold-standard`、overlay 和缓存，未 clean 或创建另一完整输出。最终证据见 [ims-build-20260920.json](../validation/ims-build-20260920.json)，官方记录为 `source/out-gold-standard/gold-build-records/1789894861622125711/result.json`。`artifact_contract_verified` 和 `android_validators_passed` 均为 true。

产物根目录为 `/srv/build/migration/gold-architecture-20260914/source/out-gold-standard/target/product/gold/`：

| 产物 | 相对路径 | 字节数 |
|---|---|---|
| IMS 修正版 OTA（保留） | `verified-candidates/20260920-170101-5b8b9ab/lineage-23.2-20260920-UNOFFICIAL-gold.zip` | 1174497268 |
| IMS 修正版 target-files | `obj/PACKAGING/target_files_intermediates/lineage_gold-target_files.zip` | 2903516865 |

SHA-256 见 [IMS 修正版校验清单](../validation/ims-build-20260920-SHA256SUMS)。平铺 OTA 和 target-files 路径会随后续增量更新；安装应使用上表按时间和提交保留的 OTA，并核对哈希。

五个 ARM 图形库及 graphics-common V7 依赖、Gold Health 正常/Recovery 服务、标签与各自唯一的 VINTF 声明、正常系统唯一 charger、Settings 维护者资源和刷新率 overlay、38 项功耗配置，以及新增的标准 IMS feature XML 均已核验。`tools/check-gold-package.py` 可复查这些包内容。Linux 原生 Health 测试 8 项通过。

从最终 vendor、system_ext、vendor_boot 镜像提取的 17 个关键文件与 target-files 条目匹配。散装 `vendor.img` 少一个最终镜像中已存在的 ARM 振动 AIDL 测试依赖，不能当作此次候选镜像；已进一步核对签名 OTA payload 的全部 14 个分区哈希和大小，均与最终 target-files 的实际镜像一致。标准 OTA 使用的是这组已核验的镜像。

这是 **userdebug / test-keys** 候选，签名完整性通过不等于正式发行密钥验收。包内策略的 permissive 域为上游调试域 `su`、`osi`、`backuptool`；没有把新 Health/Vibrator 域设为 permissive，也未关闭全局 SELinux。VINTF 详细检查返回 `COMPATIBLE`，保留了路径回退、空 boot ramdisk及 kernel level 提示的原始日志，详见验证记录。

构建及 VM 恢复服务均已成功退出。四项临时参数已经自动恢复并与实时值核对：swappiness=0、zswap=N、zpool=zbud、shrinker_enabled=Y。保留现有 24 GiB swap。此记录仅为 IMS 修正版的构建和包验证，尚无该版本的安装或实机通过结论。

宿主布局已按用户要求调整：swap 位于 `/srv/build/gold-build-swapfile`，缓存实际位于 `/root/ccache`，统一入口以 root 执行。root 构建暴露的 Git 信任与旧输出所有权问题已修复；只信任源码确切仓库路径，只把全部位于 overlay upper 的受管输出移交 root，源码所有权和沙箱保持原状。此次实际完整构建及验证通过，补齐了迁移时只有入口和缓存验证的证据。见 [host-layout-20260920.json](../validation/host-layout-20260920.json)。

## 首次候选的保留产物与实机结果

首次候选源码为 `4cdee4a`，构建时间戳 `1789870972`，13:21:39（UTC+8）完成自动验证，Android 构建耗时 2:56:08。OTA 保留在 `verified-candidates/20260920-102252-4cdee4a/lineage-23.2-20260920-UNOFFICIAL-gold.zip`；大小 1174542977 字节，SHA-256 为 `e35824385ab2e6e915f6ea33be37ac2aa58296de1d9a877cd407f922cbc8f0a4`，已重新核对。其原 target-files 路径已由新构建更新，旧大小和哈希只作为历史记录。9 月 19 日旧 OTA 也已保留并重新核对哈希不变。

首次构建记录见 [final-build-20260920.json](../validation/final-build-20260920.json)，独立实机记录见 [device-acceptance-20260920.json](../validation/device-acceptance-20260920.json)。

首次候选已完成正常系统 → 新版 A 槽 Recovery → 正常系统的往返：Recovery 中 Gold Health 位于 `hal_health_default`，VINTF 仅一个 Health 实例；misc 的合并状态为 `NONE`，metadata 的 OTA state 为空且快照目录为空。再次开机、解锁后两份验收文件哈希一致，临时文件已清理。Recovery 内核上报电量 100% / Charging，但 charge_counter 与 charge_full 为零，因此未把 Recovery 的计数换算记作实测通过。

## 本轮读取的原有系统

[9 月 20 日只读基线](../validation/device-baseline-20260920.json)：设备已连接，内核 6.6.118，B 槽，boot_completed=1，Enforcing，加密 data，连续运行约 70 小时。确认电量计数单位错误、屏幕 60/90/120 Hz 及四个相机枚举。没有 adb root、重启、安装或刷写；受 shell 权限限制，未验证 persist 与相机目录 DAC。

## 可追溯的已有结果

- 9 月 19 日科研机日志确实以 `build completed successfully (13:38)` 结束，产物为 `lineage-23.2-20260919-UNOFFICIAL-gold.zip`。它早于本轮修改；包内容的重新核查记录见 [final-build-20260919.json](../validation/final-build-20260919.json)。
- 9 月 16 日已有最终增量镜像的 [设备记录](../validation/device-fixes-20260916.json)：记录包含 B 槽 14 项回读一致、短时正常开机、加密 data/persist 正常和 Enforcing。这是历史记录，本轮没有重现实机检查。
- 该记录只证明服务就绪和有限日志窗口；没有完成相机拍照、指纹录入、Wi-Fi 联网、蓝牙音频、通话/蜂窝数据和长时稳定性测试。
- 关机充电图案曾由用户在包含相同永久修复的诊断版确认；最终清理版的完整插电循环及熄屏唤醒仍需测试。
