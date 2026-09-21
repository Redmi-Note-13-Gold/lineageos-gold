更新于 2026-09-21 11:15（UTC+8）。主线为 Global OS3.0.5.0.VNQMIXM / 6.6.118 / LineageOS 23.2，目标 `lineage_gold-bp4a-userdebug`。接手基线 462fab1，未回退到 c7c2c04。

**尚不可删除旧 hybrid Python 流程。** 完整迁移对照与 15 项条件删除清单见 [ADAPTATION](ADAPTATION.md)。本验收未删除旧目录、历史镜像或唯一输入，未公开推送。另有未提交的本机归档 README 修改与旧 Codec2 patch 工作树删除，本验收未提交、还原或同步这些改动；科研机归档仍保留。

**bd50b19 原镜像已保数据安装到 A 槽，incremental 1789938387。** 用户明确授权 15% 电量即可写入，实际在 16%、Charging、USB 在线时开始；标准 update_engine 于 09:21:56–09:25:27 以 kSuccess(0) 结束。安装器与独立 A 槽读回各 14 项最终镜像哈希全部匹配。首次启动观察 exit 0，稳定 20.76 秒；正常系统→Recovery→正常系统往返通过，返回后稳定 21.17 秒。两次均 Enforcing，data/persist 挂载、snapshot none、首次解锁和内部／共享存储两份 canary 均核验通过。没有临时修改显示节点权限。

最新 ROM 源码 `bd50b19ef82575790eb455c6cb1d712a482d62b7` 已核对 161 项实际合并输入。r5 Android 构建 01:27:20、入口 exit 0，14 payload／35 实际镜像文件、签名、VINTF、SELinux 和同次 Linux 27+32 测试全部通过。`gold-codec-r5-20260921.service` 已结束，guard 已退出且实读恢复 0/zbud/N/Y；远端无活动构建。复用唯一输出与原 OverlayFS、缓存和资源上限。

| 验证层次 | bd50b19 实际结果与边界 |
|---|---|
| 构建、安装、启动、数据 | 上述层次通过；Android 产物与实机证据独立保存，不使用旧候选结果代替 |
| Recovery | 自动 ADB 无需菜单；Enforcing，Health 位于 hal_health_default；正常往返通过。此次使用标准系统 OTA，未将其记作 Recovery 侧载 status 0 或侧载缓存峰值通过 |
| Codec2 | a7bcbba 合成探针首次 5 轮＋3 次冷服务启动各 2 轮，共 11 轮；每轮 24 帧 MTK AVC 编码／解码及 EOS 匹配。PID 稳定、无相关 Fatal signal，三次日志显示 ComponentStore=352 字节；相机录像、画质和所有格式仍未验收 |
| Power 生命周期 | ARM64／ARM 各 27+32 确定性测试、两 ABI 的已装 C 库→Enforcing HAL 申请／并发／更新／释放／超时通过；无 release 退出在从进程启动前计 388.83 ms 内归零，早于 2000 ms 期限；真实 HAL 重启后旧句柄不能释放新票值 |
| Power 节点与诊断 | 受控停止／恢复 HAL 的 150 ms uclamp=10／1048000 kHz 下限读回、到期复位通过。普通 shell dump、root 策略设置／范围拒绝／重启后生效／恢复 0 0 通过；普通 shell 策略写入被拒绝；相关 Power AVC=0 |
| 性能收益 | 已在拔 USB、无外部电源、可比温度／设置下测 0／20 策略：11 组有效冷启动 258.3→252.5 ms；4 组滚动 p95 7.45→7.95 ms，电池侧估算 2.718→2.691 W。差值区间均跨 0，未证明可重复收益，默认 0／0 保留；只代表合成负载，不代表全应用或续航等价 |
| IMS | 正常启动和 Recovery 返回后，三启动属性=1、真实绑定、mtkIms Binder、双槽 MMTEL READY 均见；**未注册，Voice／Video／UT／SMS 能力未就绪**。有效 carrier config 已应用、VoLTE=false；套餐／漫游语音条件仍未确认，无 SIM 修改或通话／短信 |
| Wi-Fi | WPA3 SAE／5 GHz 关联、DHCP 和真实 HTTPS 200／TLS 校验通过。Recovery 后因无互联网标记需显式重选已保存网络；两次开关重连中一次需重选、一次 1.60 秒自动恢复，两次 HTTPS 均通过。Google HTTPS 探测超时、框架部分连接仍单列，不强制 VALIDATED |
| 网络 ADB | 已开启并通过 TCP 调试读取身份、A 槽、incremental 和 Enforcing；正常系统 ro.adb.secure=1。Mac 旧 ADB 进程报无路由、同地址普通 TCP 成功，重启专属 ADB server 后连通；后续使用网络 transport |
| SystemUI／显示／KeyMint | 横竖屏现有时钟／网络／电量图标未见重叠或裁切，20dp 生效；窗口请求 60／90／120 Hz 均被实际模式接受。普通应用经 TEE 的 EC／RSA 签名、AES-GCM 加解密及篡改拒绝通过，3 把自建密钥已清理；多图标溢出、认证密钥与证明能力未测 |
| Recovery 缓存／TCP | 实际合并 Recovery 源码的 Linux FUSE 三项通过：完整 OTA 大小读取、32 MiB 上限／重读、篡改拒绝、分配失败降级；不代替手机侧载峰值。已装 TetheringNext 的真实解析器／事件 13 项通过；实机 BPF 双向规则删除和热点仍未测 |
| 其他受影响能力 | DeviceDiagnostics／OpenEUICC 界面、相机／完整媒体、持续热控仍未验收。用户正在使用新装 Key Attestation，未切换其前台界面 |

不可变候选 `verified-candidates/20260921-090452-bd50b19/`：OTA SHA-256 `dc2edec257034194959c86e7bb003c56b6c7129628ca35c8e47e0ba02fb32ff4`，target-files `60a6521e89d36e99a3394fb81030d3e3f83da959f519869ab164409f97ef83df`。同次工具、12 项检查输入和 ELF 已冻结；本机 a7bcbba／57b2a51 分别增加合成媒体探针和不读取凭据的已保存 Wi-Fi 重选工具，属于测试源码，没有改变已安装 ROM。`3dcd922` 归入可复用性能、TEE／显示、已装 conntrack 和 Recovery 缓存探针，已同步科研机；同步后 161 个实际 Android 输入仍一致，未重复构建。完全不含 archive 的该提交新导出通过 75 项主线测试，IMS pin 一致；不冒充从零 Android 构建。两款自建测试 APK 与专属 8 个临时文件已清理，临时 adb root 已恢复 UID 2000 且鉴权网络 ADB 仍可用，用户要求的 Key Attestation 1.8.4 保留。11:06 再验两份 canary 相符、默认策略 0／0、活动请求 0。

2cca323 的首次 MTK 编码器创建 SIGSEGV 仍保留为历史失败：原厂入口分配 336 字节，当前类需要 352 字节。客户端重试后的成功不能清除该失败；bd50b19 源码入口的独立实测才证明上述生命周期修复。3cb28c3 单独候选未安装，其诊断修复随 bd50b19 实测通过。97969dc 的 Recovery status 0／B14 已齐备，c36757a 原镜像启动失败和临时 DAC、3ee80e9 neverallow 失败均保留版本边界。

固定 IMS APK 是主线普通 Git blob，SHA-256 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1`；完整原厂依赖打包配方不完整是声明的 prebuilt 限制，本身不要求旧 Python 目录。当前 userdebug/test-keys 不冒充正式发行签名。此前低电重启的 bootreason=shutdown,battery 原因未定，不宣称长时功耗通过。详情见 [聚合证据](../validation/mainline-convergence-20260920.json)。

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
