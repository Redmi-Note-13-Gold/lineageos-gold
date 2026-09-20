更新于 2026-09-21 00:17（UTC+8）。主线采用 Global OS3.0.5.0.VNQMIXM / 6.6.118 / LineageOS 23.2，目标 `lineage_gold-bp4a-userdebug`。接手基线 462fab1，未回退到 c7c2c04。

**尚不可删除旧 hybrid Python 流程。** 完整对照及条件删除清单见 [ADAPTATION](ADAPTATION.md)。当前必须闭合的是最新候选构建与上机、IMS 后端／注册、Wi-Fi 关联和 Power 实际请求及收益验证；本轮未删除归档、历史镜像或唯一输入。

本机最新源码 `f17a75a` 另补 C 句柄跨 HAL 重启隔离、有界调用记录及实际 C ABI 设备探针；71 项主线测试（含真实适配器源码的传输替身测试）和 28 项节点／引擎主机测试通过。它尚未同步活动编译机，也未在 Android 上运行。

当前构建源码 `3ee80e9` 包含共享 Power HAL／C ABI 转发、IMS 启动配置、保数据 Wi-Fi PMF overlay 和 userdebug Recovery 自动 ADB。158 个实际合并源码文件逐项匹配，没有旧 upper 覆盖。科研机 `gold-power-ims-20260920.service` 正在唯一的 `out-gold-standard` 增量构建，BUILD_DATETIME=1789918353。保留原 OverlayFS、缓存、24 GiB swap 和资源限制，未 clean、未创建第二份输出。

| 验证层次 | 本轮实际结果 |
|---|---|
| 主机工具 | 71 项 Python 测试通过；f17a75a 无 archive 导出仍通过 71 项并含可验证 IMS 输入 |
| Power 单元测试 | 请求核心 Mac arm64／Soong Linux x86_64 各 26 项通过；节点和引擎 Mac arm64 另 28 项通过；Android HAL/客户端和性能收益未验证 |
| 97969dc 构建 | Android 11:44，包／签名／VINTF／SELinux 通过；14 个 payload 分区和 20 个实际镜像文件匹配 |
| 2cd2675 构建 | Android 59:21，包／签名／VINTF／SELinux 通过；14 个 payload 分区和 21 个实际镜像文件匹配；未安装 |
| 3ee80e9 构建 | 正在构建；尚无编译终态、产物或安装结论 |
| 97969dc 安装／启动 | 侧载 host exit 0；用户手动重启后 B 槽 incremental 1789911389、boot_completed=1、Enforcing；稳定启动观察通过，data/persist 正常、两个 canary 一致、快照 state none；Recovery 最终 status 0、安装器 14 项哈希和独立回读 14 个分区的最终镜像字节范围全部匹配 |
| IMS | 97969dc feature、框架初始化及 MTK 服务实际绑定通过；MMTEL UNAVAILABLE，后端被缺失 ims_support 阻断；3ee80e9 修复待验证。未通过注册／通话／短信 |
| Wi-Fi | 97969dc data pmf=0、vendor 模板=1，证实升级漏覆盖；2cd2675 overlay 修复未上机，当前尚未关联 |
| 性能／能耗 | 真实节点、匹配内核协议和调用者静态证据已核对；尚无同机可重复收益，新增框架 boost 默认关闭 |
| 其他硬件 | 旧候选的相机／指纹／振动结果保留为历史，不挪给 97969dc 或新候选 |

IMS APK SHA-256 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1`，为主线普通 Git blob。47 个载荷条目和重编兼容 dex 已核验；原厂完整依赖打包配方不完整，但当前输入可独立取得，不依赖旧 Python 环境。

用户已授权本会话同基线保数据 OTA、正常系统／Recovery 重启、分区回读、临时 adb root、安装并清理测试程序、Wi-Fi 重连和网络调试；不清数据、不改 SIM、不拨号或发短信。最后现场卡为第二槽漫游 eSIM。23:59 已重新连接 USB ADB，仍为 97969dc 的 B 槽正常系统；网络 ADB 尚未启用。

原始证据和后续检查路径在 [mainline-convergence-20260920.json](../validation/mainline-convergence-20260920.json)。2cd2675 构建记录 `source/out-gold-standard/gold-build-records/1789914079640672965/`；保留产物 `verified-candidates/20260920-222119-2cd2675/`，OTA SHA-256 `a908222f5162bdc01c18b87634d18f9c433d258199e5292cb7fd3269f55a290d`，target-files SHA-256 `efbc1306c820fe83b38031aa8de3444584be136864c2bf59401acba04ab125e1`。97969dc 保留路径仍为 `verified-candidates/20260920-213629-97969dc/`，OTA SHA-256 `30a753e70b74de6243bdb649972b8d87d11995d40ced7ad877b2ec2793e3d5e6`。不得用可变平铺路径代替候选身份。

97969dc 和 2cd2675 的构建及 VM guard 均已成功退出，临时参数恢复已核对。3ee80e9 使用新的独立 guard；源码和集成仓库在活动构建期间不再同步改动。

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
