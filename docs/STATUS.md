# 当前适配状态

更新于 2026-09-20。主线为 Global OS3.0.5.0.VNQMIXM / 6.6.118 / LineageOS 23.2，开发目标 `lineage_gold-bp4a-userdebug`。

IMS 修正版已于 18:31:35（UTC+8）完成构建及自动验证，源码为 `5b8b9ab`，版本时间戳为 `1789894861`。新 OTA 已下载到本机并核对 SHA-256、ZIP CRC 和证书；当前 ADB 未连接，尚未安装此候选。

首次候选 `4cdee4a` 已完成保数据 OTA、A 槽启动及部分实机检查。验收发现 IMS feature 声明缺失，导致框架跳过 IMS 初始化；修正版已补齐声明并通过包检查。首次候选的硬件结果不能替代修正版验收，漫游 eSIM 的 LTE 注册也不能作为 IMS / VoLTE 通过的依据。

## 本轮源码候选

已修改：补齐 32 位 mapper 的五个厂商库及对应 AIDL 依赖修正；恢复原厂功耗统计资源并纠正大核字段名；启用按实际屏幕模式生成的刷新率选择；补齐显示轮廓；按当前内核实际单位修复电量计数器；撤下未有效调校的持续性能能力声明；修复振动 HAL 虚报能力和文件描述符泄漏；收窄相机数据/标定目录权限；清理重复及无读取方的属性；将实际编译树中的 Betterr 设置条目纳入恢复补丁。

| 验证层次 | 当前结论 |
|---|---|
| 主机工具 | 27 项 Python 测试通过，包括清单导出失败仍保存失败记录；原生 arm64 C++ 和本轮生成的 Linux x86_64 Health 测试均通过 8 个电量单位/边界用例 |
| IMS 修正版构建 | 源码 `5b8b9ab` 完整构建成功；target-files、AVB、VINTF、OTA/payload 签名及 Gold 包内容检查通过；实际镜像的 17 个关键文件、OTA payload 全部 14 个分区哈希与最终 target-files 匹配 |
| 振动契约测试 | 首次候选 ARM64 / ARM 已在手机 shell 下各通过 4 项；临时程序和依赖已清理。修正版生成的测试 ELF 与首次相同，但尚未在修正版上运行 |
| 首次候选安装、分区回读、开机 | Recovery status 0；14 项安装器写后校验及 7 项独立物理分区回读匹配；A 槽及新版 Recovery 往返启动完成，Enforcing，data/persist 正常；Virtual A/B 合并已完成 |
| 首次候选硬件 | Health 单位修复和显示 overlay 生效；前置预览出图，用户确认后置预览/拍照、已录入指纹解锁及基础振动正常；eSIM 漫游 LTE 注册正常。其他硬件仍未全面验收 |
| IMS 修正版实机 | 尚未安装；IMS 框架初始化、服务绑定及运营商注册仍待验证 |

具体采用与暂缓理由见 [ADAPTATION](ADAPTATION.md)。新增振动契约测试需要 Android 目标构建和运行，不把编译测试程序计作测试通过。

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

## 尚需完成

ADB 重新连接后，核对身份、当前槽位、合并状态和电量，继续已授权的同基线保数据 OTA；然后单独验证 Recovery 安装终态、分区回读、稳定开机和 IMS 框架服务绑定。不会把包内 feature 声明直接计作运营商 IMS 注册通过。构建回查在等待设备连接期间暂停。

其后按可用测试条件验收相机完整模式、新指纹录入、双卡与 IMS、Wi-Fi/热点、蓝牙音频、GNSS、传感器、USB 各模式、关机充电和温控功耗。首次同基线保数据 OTA、Virtual A/B 合并及新版 Recovery 往返已完成；回退尚未测试。

当前 Power HAL 缺少 launch/interaction 动作，不能宣称 v1 boost 已完整继承。Health 单位修复已在首次候选正常系统生效；关机充电完整循环与持续性能调校仍未完成，详见 ADAPTATION。

IMS 固定兼容 APK 已作为主线受管 prebuilt 保存并锁定哈希；原厂 APK 到完整依赖包的重建流程仍未闭合，明确保留此二进制输入。未用关闭 SELinux、跳过 neverallow、伪造硬件能力或强行声明 MDDP WH 支持来代替验证。
