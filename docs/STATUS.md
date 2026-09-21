更新于 2026-09-22 主线移除 eSIM 支持。唯一主线仍为 Global OS3.0.5.0.VNQMIXM / kernel 6.6.118 / LineageOS 23.2，目标 `lineage_gold-bp4a-userdebug`；服务器为事实来源。

**6e7c418 已保数据安装到 B 槽，incremental 1789977174；WPA3 修复 89ae983 已完整构建及冻结，未安装；用户随后决定移除 OpenEUICC/eSIM，主线已移除，移除版前两轮分别在 target-files 和 OTA 临时 ZIP 阶段因空间不足失败；顺序打包之外，现增加专属系统盘临时目录，准备复用原输出第三次续编。** 已安装候选为 `/srv/build/gold/releases/20260921-224022-6e7c418`。下面分别列出剩余工作与已验收子项。冻结时的 candidate.json 保留当时未安装的原始事实，安装结论另见 [聚合证据](../validation/mainline-convergence-20260920.json) 中 `non_ims_followup_20260921.functional_candidate_6e7c418_device`，不能把冻结记录直接改成全部设备通过。

OpenEUICC/eSIM 已按用户明确决定退出当前支持范围：移除产品包、eUICC feature XML、两个专属源码项目与子模块获取配方、平台补丁和正向验收项；新门禁拒绝旧 APK、权限和原生库残留。普通双卡、IMS 和共享 20dp 状态栏保留。未卸载当前手机的应用或改变 SIM，历史记录不改写。

## 未完成与当前限制

| 项目 | 当前事实及下一步 |
|---|---|
| WPA3 热点 | 本机开启 WPA3 失败已复现：框架 capability=123，缺 SAE bit 4，记录 `Error, SAE requires HAL support`，在 native hostapd 前拒绝。匹配 Global 原厂两份 Wi-Fi RRO 均开启 `config_wifi_softap_sae_supported`，hostapd 已有 CONFIG_SAE。主线补同一资源为 true；168 个 Android 输入中仅此 XML 改变，91 项 Python 测试、实际编译资源检查通过，旧候选被新增资源门禁正确拒绝。89ae983 已构建及包门禁通过；合并 eSIM 移除的下一候选仍需实测启动、WPA3 客户端认证及关闭，当前手机尚未安装修复 |
| Wi-Fi 自动恢复 | 已安装正式探测 RRO，但之前批准的保存网络不在当前扫描范围；需该热点重新可见后核对自动关联、真实 TLS/204 和框架判定，不强制 VALIDATED |
| 设备属性证明 / 认证密钥 | 新 ROM 的 Key Attestation 仍报 -66 CANNOT_ATTEST_IDS；vnd_gold/gold 两项专用属性未获 TEE 接受。实机 SKU=gold_cn，已核验 Global vendor 与 product 镜像的通用属性不足以证明实际预置身份。不得继续把 vendor 值假说写成已修复；需核对真实变体与 TEE 请求。引导状态仍 orange；安全锁屏未设置，认证绑定密钥未测，不代用户设锁或导入 keybox |
| TCP/BPF | parser/event 和真实 TCP 状态变化已有旧版证据，IPv4 双向规则删除仍未证明；用户明确保持移动数据关闭，缺允许的 raw-IP 上行条件 |
| Recovery | bd50b19 的往返和缓存设备峰值为既有通过；6e7c418 的 Recovery 往返尚未执行。用户现要求不再重启手机，当前保持网络连接；Scudo 失败注入和完整 Recovery OTA 仍未测，不为重复验收刷机 |
| DeviceDiagnostics / AOD / 媒体 | 电池未知值界面旧版已测，非法边界注入未测；AOD/doze 与必要扩展媒体场景尚未完整验收，不把短 AVC 片段扩大为全格式通过 |
| Health / 热控 / 其他硬件 | 持续负载降频与恢复、完整充电/关机充电循环、长期续航未测；蓝牙音频等依外设和已有记录选择测试 |
| 主机重启 / 发行 | 目录迁移构图已过，科研机整机重启恢复未实测；userdebug/test-keys 不是正式发行密钥验收，未公开发布 |
| IMS | 按用户安排放最后，另有安排；本轮不推进，不操作 SIM、不拨号或发短信 |

用户最新限制是**不再重启手机，避免断网**；后续安装或 Recovery 操作须待用户改变这一限制。当前不切换 Wi-Fi、热点或 USB 网络状态。5 个自建临时文件和 2 个专属目录已清理，中文、旋转和 demo 设置原样恢复，两份 canary 一致，移动数据 0，正式双击开启。临时 adb root 尚为 UID0，为保留当前调试连接暂未重启 adbd；退出 root 待允许短暂 ADB 重连。用户 Key Attestation 1.8.4/code198 保留。

## 6e7c418 已验收子项

| 子项 | 本候选证据与边界 |
|---|---|
| 包与安装 | 完整 A/B OTA 已下载本机并核验；适用性与签名匹配后标准 update_engine 于约 23:00:50 +08 返回 kSuccess(0)、UPDATED_NEED_REBOOT。安装器最终 14 分区哈希及独立 B 槽 14 项回读均与签名镜像一致 |
| 正常启动与数据 | B / 1789977174，首次稳定观察 25.8 秒，另一次正常重启稳定 20.34 秒；Enforcing、data/persist、snapshot none、两份 canary 通过。后续不再重启的限制已生效 |
| 正式双击唤醒 | Settings→Power HAL→窄 SELinux 权限生效；用户确认两轮黑屏物理双击均亮，FTS 两组 KEY_POWER 对应。实际设置开关 Off/On 与 framework、睡眠寄存器 0xD0=0/1 一致；正常重启保留，Power HAL 受控重启后 PID 改变且状态恢复。没有用直接 ioctl 冒充本轮正式路径 |
| SystemUI 横屏边距 | zh-CN / ar-SA、rotation 1 / 3 共四组真机截图和实际 InsetsProvider 缓存核对；左右均 55 px，原 111/55 px 缺陷消失。10 合成状态图标可见溢出点，未见重叠；不是全部可能组合的穷尽测试，语言/旋转/demo 已恢复 |
| OpenEUICC 管理 | 系统 SIM 列表可见；标准 MANAGE_EMBEDDED_SUBSCRIPTIONS 路由打开 PrivilegedMainActivity 只读管理列表，4 个配置、1 个已启用，未进入下载页，观察窗口没有原快捷方式崩溃。已只读核对第二实体槽 physical1→port0→logical phone1 为 eUICC，第一槽不是。2026-09-22 用户决定退出该支持，此行仅为 6e7c418 历史记录 |

## bd50b19 既有验收（不继承给新候选）

ROM `bd50b19ef82575790eb455c6cb1d712a482d62b7`、A 槽 / 1789938387 的冻结候选仍为 `/srv/build/gold/releases/20260921-090452-bd50b19`。其完整 Android 构建 01:27:20、入口 exit 0，161 项输入、14 payload / 35 实际镜像文件、保数据 OTA、安装器及独立各 14 项回读、稳定启动与 Recovery 往返、Enforcing、挂载、snapshot none、两份 canary 为既有通过。

| 已验收子项 | 证据边界 |
|---|---|
| Recovery 缓存 | 主机实际源码 32 MiB、淘汰重读、篡改拒绝和 malloc 降级；设备 1,174,408,317 字节无安装器 fixture 验签后产品检查拒绝，未刷 ROM。minadbd RSS/HWM 43,084/43,436 KiB，Recovery HWM 99,284 KiB |
| Codec2 / 相机 | 3 次冷服务启动、11 轮各 24 帧 MTK AVC 编解码及 EOS、PID 稳定；Aperture 预览和 7.218 秒 1080p 自有录像、216 帧 MTK 解码/EOS。自有片段已删；用户确认相机、麦克风、扬声器和震动体验正常 |
| Power 生命周期 | ARM64/ARM 各 27 项请求和 32 项节点测试；真实 C ABI→Enforcing HAL 的申请、更新、并发、释放、超时、退出回收、服务重启隔离、诊断权限和复位通过 |
| Power 性能策略 | 无外部电源、可比设置温度 AB/BA：11 组冷启动 258.3→252.5 ms，探索性差值区间 [-11.64,+1.55] ms；4 组滚动 p95 7.45→7.95 ms；电池估算 2.718→2.691 W，差值区间 [-0.0965,+0.0433] W。未证明可重复收益，默认 LAUNCH/INTERACTION 保持 0/0 |
| Wi-Fi 客户端 / 网络 ADB | WPA3 SAE 5GHz 关联、DHCP、真实 TLS HTTPS 与鉴权网络 ADB 通过；临时 gstatic 真 HTTPS 配置使自动重连 21.574/1.448 秒验证成功。客户端 WPA3 通过不等于本机 WPA3 热点通过 |
| 显示 / TEE / Diagnostics | 60/90/120Hz 窗口模式；普通应用 TEE EC/RSA 签名、AES-GCM 加解密及篡改拒绝，自建密钥删除；DeviceDiagnostics 正常界面与实际未知值隐藏 |
| TCP 状态 | 已装 parser/event 13 项，USB NCM 真连接 ESTABLISHED→TIME_WAIT；未证明 BPF 规则回收 |

## 构建与工程证据

eSIM 移除时，实际合并输入 165 项与主线一致；保留的输入只改 device.mk，删除 3 项 OpenEUICC 补丁输入及两个独立检出。原 1158 个 Repo 项目清单未变；受管完整 manifest 从 1160 项变为 1158 项，8 个保留受管项目提交未变。包检查在旧 target-files 和旧 system_ext 实际镜像上均正确拒绝残留。新的最终镜像和增量构建尚待完成。首轮02:11:40入口exit1，直接错误为target-files soong_zip的ENOSPC；guard02:11:54退出，VM实读0/zbud/N/Y、无OOM、临时ZIP工具清理。保留失败结果，不将随后完成的OTA单包冒充候选。

本次已装候选的 Android r2 构建成功，02:36:40；原入口于 22:14:26 +08 exit 1，因检查器固定四空格缩进误拒绝正确 OpenEUICC 路由。`00be34a` 修正层级解析，91 项测试、原 ZIP 和冻结工具独立复验均通过，未改 Android 输入或 ZIP，也未改写原失败结果。168 项输入一致，签名/VINTF/SELinux、14 payload / 38 实际镜像文件通过。OTA SHA-256 `22f5937ef97ed7073e57c357c0302bf77bbdd6cddb2b474aab7073a38e79f6cb`；target-files `7e8cc241b97b73beef1dacdd0948af6271c4c1d5bc1b64d786e142317256f98c`。

r2 guard 于 22:14:31 恢复，终态实读 VM=0/zbud/N/Y，无 OOM，临时 ZIP 工具清理；r1 缺 unzip 失败及 6e7c418 前置检查修复记录保留。WPA3 补丁只改一个实际 Android XML；89ae983 于 2026-09-22 00:20:25 +08 入口 exit 0，Android 编译打包 12:33，签名/VINTF/SELinux、14 payload / 39 实际镜像文件通过。guard 00:20:29 恢复 VM=0/zbud/N/Y，临时 ZIP 工具清理、无 OOM。冻结候选 `/srv/build/gold/releases/20260922-002433-89ae983` 已独立复验，包含撤回之前的 OpenEUICC，未安装；下一版本合并移除后重新构建，不继承设备结论。

活动输出两种同次包的三个路径在与独立冻结候选逐个重读 SHA-256 一致后清理，释放约 3.80 GiB，输出 inode 9437191 不变；记录 `jobs/gold-mainline-20260920/wpa3-active-package-duplicates.json` 给出已保存冻结路径。历史候选、官方输入、OverlayFS、缓存与 swap 均保留。OverlayFS 合并视图到 releases 直接 rename 实测返回 EXDEV；冻结改为逐包复制、重读 SHA-256 并 fsync 后才移除该包的全部可变硬链接，保存路径映射和独立工具复验；不改 OUT_DIR，不复制第二套输出。

目录迁移构图于 14:56:55 exit 0、01:01:37，guard 14:57:03 退出、VM 0/zbud/N/Y，无 OOM；.top、新路径、inode9437191、161 项原输入和1158个Repo提交未变。整机重启恢复尚未测。`27ea764` 已退役15个 archive/hybrid 文件；旧源码从 Git 历史查阅，当前主线 Python 提取/构建/检查工具继续保留，后续适配只走主线。

固定 IMS APK SHA-256 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1` 为普通 Git blob，原厂完整依赖配方不足仍是 prebuilt 限制。匹配 Global vendor/kernel/modules、所需 ARM 媒体图形库、官方 Global/CN 输入和历史候选均有恢复及硬件用途，不能删除。原始设备/无线日志与截图只在本机私有目录0600，Git只存脱敏结论；维护、构建、冻结入口见 [LAYOUT](LAYOUT.md)、[BUILD](BUILD.md)、[RESTORE](RESTORE.md)。

以下内容仅保留为历史验收记录，不表示其他候选已经通过。历史 verified-candidates 绝对路径通过 `/srv/build/gold/history/layout-moves-20260921.json` 映射；实际冻结目录以 `/srv/build/gold/releases/index.json` 定位，历史记录不改写。

## 9 月 20 日 IMS 修正版产物

科研机以实际 UID 0 构建，Android 构建耗时 1:28:17。复用原 `out-gold-standard`、overlay 和缓存，未 clean 或创建另一完整输出。最终证据见 [ims-build-20260920.json](../validation/ims-build-20260920.json)，官方记录为 `source/out-gold-standard/gold-build-records/1789894861622125711/result.json`。`artifact_contract_verified` 和 `android_validators_passed` 均为 true。

产物根目录为 `/srv/build/gold/source/out-gold-standard/target/product/gold/`：

| 产物 | 相对路径 | 字节数 |
|---|---|---|
| IMS 修正版 OTA（保留） | `verified-candidates/20260920-170101-5b8b9ab/lineage-23.2-20260920-UNOFFICIAL-gold.zip` | 1174497268 |
| IMS 修正版 target-files | `obj/PACKAGING/target_files_intermediates/lineage_gold-target_files.zip` | 2903516865 |

SHA-256 见 [IMS 修正版校验清单](../validation/ims-build-20260920-SHA256SUMS)。平铺 OTA 和 target-files 路径会随后续增量更新；安装应使用上表按时间和提交保留的 OTA，并核对哈希。

五个 ARM 图形库及 graphics-common V7 依赖、Gold Health 正常/Recovery 服务、标签与各自唯一的 VINTF 声明、正常系统唯一 charger、Settings 维护者资源和刷新率 overlay、38 项功耗配置，以及新增的标准 IMS feature XML 均已核验。`tools/check-gold-package.py` 可复查这些包内容。Linux 原生 Health 测试 8 项通过。

从最终 vendor、system_ext、vendor_boot 镜像提取的 17 个关键文件与 target-files 条目匹配。散装 `vendor.img` 少一个最终镜像中已存在的 ARM 振动 AIDL 测试依赖，不能当作此次候选镜像；已进一步核对签名 OTA payload 的全部 14 个分区哈希和大小，均与最终 target-files 的实际镜像一致。标准 OTA 使用的是这组已核验的镜像。

这是 **userdebug / test-keys** 候选，签名完整性通过不等于正式发行密钥验收。包内策略的 permissive 域为上游调试域 `su`、`osi`、`backuptool`；没有把新 Health/Vibrator 域设为 permissive，也未关闭全局 SELinux。VINTF 详细检查返回 `COMPATIBLE`，保留了路径回退、空 boot ramdisk及 kernel level 提示的原始日志，详见验证记录。

构建及 VM 恢复服务均已成功退出。四项临时参数已经自动恢复并与实时值核对：swappiness=0、zswap=N、zpool=zbud、shrinker_enabled=Y。保留现有 24 GiB swap。此记录仅为 IMS 修正版的构建和包验证，尚无该版本的安装或实机通过结论。

宿主布局已按用户要求调整：swap 位于 `/srv/build/gold/host/build.swap`，缓存实际位于 `/root/ccache`，统一入口以 root 执行。root 构建暴露的 Git 信任与旧输出所有权问题已修复；只信任源码确切仓库路径，只把全部位于 overlay upper 的受管输出移交 root，源码所有权和沙箱保持原状。此次实际完整构建及验证通过，补齐了迁移时只有入口和缓存验证的证据。见 [host-layout-20260920.json](../validation/host-layout-20260920.json)。

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

WPA3 下一轮任务记录使用 `jobs/gold-mainline-20260920/wpa3-r1-build-request.json` / `wpa3-r1-build-result.json`；是否实际启动、终态与 VM 恢复以实时服务和这些记录为准。该构建不授予重启当前手机的权限。

2026-09-22续编r2于02:34:26入口exit1，bacon阶段12:05；OTA zip2zip自身临时副本仍触发ENOSPC，target-files阶段未启动。guard02:34:37恢复VM并清理工具；旧峰值估算不足。新增可选OTA系统盘临时目录补丁并准备r3：98项主机测试、实际Make宏默认/覆盖/含空格路径检查通过；合并输入166项/9个受管项目，原165项字节不变，只增加build/make主机打包规则。最终包尚未验收；手机和网络未动。
