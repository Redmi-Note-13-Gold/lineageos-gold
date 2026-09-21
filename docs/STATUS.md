更新于 2026-09-21（构图收尾与非 IMS 定向适配）。主线为 Global OS3.0.5.0.VNQMIXM / 6.6.118 / LineageOS 23.2，目标 `lineage_gold-bp4a-userdebug`。接手基线 462fab1，未回退到 c7c2c04。

本轮 47b34c3 构建于 18:09:27 +08 以 exit 1 结束（Android 02:15:19），直接错误为 hiddenapi 编码命令 `unzip: not found`；宿主 zip/unzip 均未安装，非旧路径失效。内核日志无 OOM，独立 guard 于 18:09:34 恢复 VM，终态后实读为 0/zbud/N/Y。没有生成本轮可验收候选。新增入口依赖预检及宿主工具路径/哈希记录；使用经 APT 元数据 SHA-256 校验的 Ubuntu zip/unzip 临时解包到本次 job，不写 dpkg 安装状态，独立 guard 在续编结束后清理。ROM 的 168 项合并输入不因宿主修复而改变。

**旧 hybrid 运行代码已按用户后续明确授权清理；完整功能验收仍未完成。** 原 15 个受管归档文件（含此前已删除的 Codec2 补丁）均退出主线工作树，删除依据与历史定位见 [ADAPTATION](ADAPTATION.md)。退役本身不授予任何功能通过结论；后续主线定向验收按下表记录，不删除历史镜像、唯一输入或当前主线 Python 工具。科研机为执行与核验依据，本地同步同一提交。

宿主物理目录已收拢到 `/srv/build/gold`，外层只留该实目录、`build-gold.sh` 入口链接及 `lost+found`。源码、唯一输出、输入、宿主配置与历史以同盘重命名迁移；8 个冻结候选已移出活动输出，14 个包哈希仍匹配原始记录。新 OverlayFS 与原 swap 文件已在新路径启用，161 项合并输入和 1158 个 Repo 项目提交保持一致。迁移后的构建图于 14:56:55 +08 真正结束、入口 exit 0，Android m nothing 耗时 01:01:37；独立 guard 于 14:57:03 退出，实读 VM 已恢复 0/zbud/N/Y。无 OOM；输出 inode 9437191 保持，.top 为 /srv/build/gold/source，161 项合并输入和 1158 项 Repo 提交复核未变，环境检查 exit 0。整机重启未测试。见 [LAYOUT](LAYOUT.md) 和 [host-layout-20260920.json](../validation/host-layout-20260920.json)。这次目录迁移构图没有生成新 ROM，也不增加设备验收结论；下列验收仍属于各自版本。

**bd50b19 原镜像已保数据安装到 A 槽，incremental 1789938387。** 用户明确授权 15% 电量即可写入，实际在 16%、Charging、USB 在线时开始；标准 update_engine 于 09:21:56–09:25:27 以 kSuccess(0) 结束。安装器与独立 A 槽读回各 14 项最终镜像哈希全部匹配。首次启动观察 exit 0，稳定 20.76 秒；正常系统→Recovery→正常系统往返通过，返回后稳定 21.17 秒。两次均 Enforcing，data/persist 挂载、snapshot none、首次解锁和内部／共享存储两份 canary 均核验通过。没有临时修改显示节点权限。

最新 ROM 源码 `bd50b19ef82575790eb455c6cb1d712a482d62b7` 已核对 161 项实际合并输入。r5 Android 构建 01:27:20、入口 exit 0，14 payload／35 实际镜像文件、签名、VINTF、SELinux 和同次 Linux 27+32 测试全部通过。`gold-codec-r5-20260921.service` 已结束，guard 已退出且实读恢复 0/zbud/N/Y。当前目录迁移构图也已收尾；后续任务须重新核对占用。复用唯一输出与原 OverlayFS、缓存和资源上限。

| 验证层次 | bd50b19 实际结果与边界 |
|---|---|
| 构建、安装、启动、数据 | 上述层次通过；Android 产物与实机证据独立保存，不使用旧候选结果代替 |
| Recovery | 自动 ADB、Enforcing、正常往返通过。新增真实签名侧载验证：1,174,408,317 字节专用无安装器 fixture 完整验签通过，错误产品名在 updater 前被拒绝，未刷 ROM。32 MiB 缓存；minadbd RSS 峰值 43,084 KiB、HWM 43,436 KiB，Recovery 主进程 HWM 99,284 KiB。未做设备分配失败注入或完整 Recovery OTA 安装 |
| Codec2 | 3 次冷服务启动、11 轮各 24 帧 MTK AVC 编解码及 EOS 通过、PID 稳定。新增 Aperture 实际预览／7.218 秒 1080p 自有录像，c2.mtk.avc.decoder 解出 216 帧和 EOS；自有片段已删除。用户确认相机体验正常；不扩大为全部格式、画质或长时稳定性 |
| Power 生命周期 | ARM64／ARM 各 27+32 确定性测试、两 ABI 的已装 C 库→Enforcing HAL 申请／并发／更新／释放／超时通过；无 release 退出在从进程启动前计 388.83 ms 内归零，早于 2000 ms 期限；真实 HAL 重启后旧句柄不能释放新票值 |
| Power 节点与诊断 | 受控停止／恢复 HAL 的 150 ms uclamp=10／1048000 kHz 下限读回、到期复位通过。普通 shell dump、root 策略设置／范围拒绝／重启后生效／恢复 0 0 通过；普通 shell 策略写入被拒绝；相关 Power AVC=0 |
| 性能收益 | 已在拔 USB、无外部电源、可比温度／设置下测 0／20 策略：11 组有效冷启动 258.3→252.5 ms；4 组滚动 p95 7.45→7.95 ms，电池侧估算 2.718→2.691 W。差值区间均跨 0，未证明可重复收益，默认 0／0 保留；只代表合成负载，不代表全应用或续航等价 |
| IMS | 既有绑定、mtkIms Binder、双槽 MMTEL READY 和 Recovery 恢复通过；注册／能力仍未就绪。**用户要求最后处理，另有安排，本轮未操作 IMS、SIM、通话或短信** |
| Wi-Fi | WPA3 SAE／5 GHz、DHCP、真实 TLS HTTPS 通过。Google 探测超时导致部分连接并可阻止自动恢复。临时增加真实 gstatic HTTPS 204 后三次验证成功（2.767／21.574／1.448 秒，其中后两次为自动重连）；恢复原配置后部分连接复现。主线 RRO 修复已集成，待新镜像验收；凭据、探测判定未绕过 |
| 网络 ADB | 已开启并通过 TCP 调试读取身份、A 槽、incremental 和 Enforcing；正常系统 ro.adb.secure=1。Mac 旧 ADB 进程报无路由、同地址普通 TCP 成功，重启专属 ADB server 后连通；后续使用网络 transport |
| SystemUI／显示／KeyMint | 60／90／120 Hz 与 TEE EC／RSA／AES 运算保留既有通过。新增 10 合成图标 LTR／RTL 横竖屏溢出点检查，无图标重叠；**横屏左 111px／右 55px 不对称已复现，不能记全组合通过**。Key Attestation 设备属性证明报 -66，实际原厂 vendor product/model 为 vnd_gold/gold，与当前值不同。两项已集成源码修复，均待新镜像；引导状态仍真实 orange，认证绑定密钥未测 |
| Recovery 缓存／TCP | 主机缓存测试和上述设备侧载峰值各自通过。已装 TCP parser／event 13 项通过；USB NCM 真连接 ESTABLISHED→TIME_WAIT 已见，Wi-Fi 上行没有创建 IPv4 BPF 规则，故未证明规则删除。用户明确保持移动数据关闭，后续需允许的 raw-IP 上行条件 |
| 其他受影响能力 | DeviceDiagnostics 电池界面、实际未知值隐藏通过，非法边界注入未做。OpenEUICC 系统只读 SIM 列表可见，但管理路由误进下载页、无 launcher 时动态快捷方式导致崩溃；修复待构建／安装。用户确认麦克风、扬声器、震动体验正常。持续热控和认证密钥未测；保留用户 Key Attestation 应用 |

双击唤醒：LineageOS 已有标准设置；bd50b19 缺 Gold 能力资源和 Power HAL 模式处理。原厂 FT3683G 模块的 mode 14 临时调用已确认熄屏寄存器 0xD0=1、两组触摸 KEY_POWER 和 gesture ID 0x24，用户确认两次双击亮屏；临时状态已恢复。主线已接入系统设置、实际 ioctl 和最小 SELinux 设备类型，9 项协议／失败测试通过；**正式 HAL、开关和重启恢复仍待新镜像验收**。

本轮五处运行修复（Wi-Fi 探测、OpenEUICC、原厂证明身份、横屏边距、双击唤醒）已经集成到服务器合并源码，168 项输入核对一致；84 项主机工具测试、40 个实际 Kotlin 几何用例通过，旧代码能复现同一几何回归。目前尚未生成或安装本轮新候选；不得继承 bd50b19 的设备验收。原始设备证据只在本机私有目录，跨机可读脱敏结论为 [聚合证据](../validation/mainline-convergence-20260920.json) 的 non_ims_followup_20260921 及服务器 jobs 中同名记录。

当前不可变候选 `/srv/build/gold/releases/20260921-090452-bd50b19/`：OTA SHA-256 `dc2edec257034194959c86e7bb003c56b6c7129628ca35c8e47e0ba02fb32ff4`，target-files `60a6521e89d36e99a3394fb81030d3e3f83da959f519869ab164409f97ef83df`。同次工具、12 项检查输入和 ELF 已冻结；本机 a7bcbba／57b2a51 分别增加合成媒体探针和不读取凭据的已保存 Wi-Fi 重选工具，属于测试源码，没有改变已安装 ROM。`3dcd922` 归入可复用性能、TEE／显示、已装 conntrack 和 Recovery 缓存探针，已同步科研机；同步后 161 个实际 Android 输入仍一致，未重复构建。完全不含 archive 的该提交新导出通过 75 项主线测试，IMS pin 一致；不冒充从零 Android 构建。两款自建测试 APK 与专属 8 个临时文件已清理，临时 adb root 已恢复 UID 2000 且鉴权网络 ADB 仍可用，用户要求的 Key Attestation 1.8.4 保留。11:06 再验两份 canary 相符、默认策略 0／0、活动请求 0。

2cca323 的首次 MTK 编码器创建 SIGSEGV 仍保留为历史失败：原厂入口分配 336 字节，当前类需要 352 字节。客户端重试后的成功不能清除该失败；bd50b19 源码入口的独立实测才证明上述生命周期修复。3cb28c3 单独候选未安装，其诊断修复随 bd50b19 实测通过。97969dc 的 Recovery status 0／B14 已齐备，c36757a 原镜像启动失败和临时 DAC、3ee80e9 neverallow 失败均保留版本边界。

固定 IMS APK 是主线普通 Git blob，SHA-256 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1`；完整原厂依赖打包配方不完整是声明的 prebuilt 限制，本身不要求旧 Python 目录。当前 userdebug/test-keys 不冒充正式发行签名。此前低电重启的 bootreason=shutdown,battery 原因未定，不宣称长时功耗通过。详情见 [聚合证据](../validation/mainline-convergence-20260920.json)。

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
