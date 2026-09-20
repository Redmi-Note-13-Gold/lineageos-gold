更新于 2026-09-21 04:01（UTC+8）。主线为 Global OS3.0.5.0.VNQMIXM / 6.6.118 / LineageOS 23.2，目标 `lineage_gold-bp4a-userdebug`。接手基线 462fab1，未回退到 c7c2c04。

**尚不可删除旧 hybrid Python 流程。** 完整迁移对照与 15 项条件删除清单见 [ADAPTATION](ADAPTATION.md)；本轮没有删除归档、历史镜像或唯一输入，没有公开推送。

最新源码 `2cca32362fc5cd4b28ef840bd90f0e14f46b4ecb` 已受控同步科研机，158 项合并输入匹配，仅更新 10 个内容改变的文件，Android.bp 时间戳保留。`gold-power-runtime-r3-20260921.service` 于 03:49 启动并已完成，Android 耗时 13:34、入口 exit 0，BUILD_DATETIME=1789933740；日志 `/srv/build/logs/gold-power-runtime-r3-20260921.log`。仍复用唯一 `source/out-gold-standard`，jobs=2、原内存／swap 上限、OverlayFS、缓存和独立 VM 恢复 guard；未 clean。

c36757a 已完成 Android 编译 01:15:15，原入口的 VINTF XML 格式字节比较误报由 05f156a 修正；同一不可变候选重验 14 个 payload 分区／29 个实际镜像文件、签名、VINTF、SELinux 均通过。03:09 标准 update_engine 安装到 A 槽以 kSuccess(0) 结束，14 项安装器哈希及独立 A 槽回读全部匹配。

**c36757a 原始启动未通过。** Power 对 root:root 0440 的显示 idle 节点写入失败，并在 Binder 注册前退出，导致框架等待。临时只把该节点改成 system:system 0660 后才 boot_completed=1，全局保持 Enforcing。内核反汇编和实际 34／50 值变化进一步证明它是共享全局 interval，不能由 Power 以固定 50 复位。2cca323 不接管该节点，明确拒绝相应资源；后端不可用时保持控制接口、拒绝 boost／票值并限速恢复，缓存省电／显示状态，要求新鲜温控。它也修复相同聚合跳过硬件回读的问题，以及仅调试 root 探针的进程身份读取 AVC。

| 验证层次 | 当前实际结果 |
|---|---|
| 2cca323 主机测试 | Python 75、Mac arm64 请求 27、节点／引擎 32 项通过；不含 archive 的 Git 导出再次通过 75 项且 IMS 哈希正确 |
| 2cca323 Android | **编译及全部包门禁通过**：14 payload／29 实际文件、签名、VINTF、SELinux；Linux 27+32 项通过；尚未安装 |
| c36757a 安装／回读 | 标准 update_engine 成功、14 项安装器与独立回读均匹配；data/persist 挂载、内部 canary 一致、snapshot none；共享存储 canary 等首次解锁 |
| c36757a 原镜像启动 | **失败**；临时 DAC 后进入系统仅是诊断条件，不能作为候选通过 |
| c36757a 确定性 Power 测试 | Linux、设备 ARM64、ARM 各 26+28 项通过；不是实际 HAL 动作／收益验收 |
| IMS 条件运行 | 三项启动属性=1、MTK 服务绑定、mtkIms Binder 存在、双槽 MMTEL READY；未注册，Voice/Video/UT/SMS 未就绪；有效配置已应用但 carrier VoLTE=false，套餐条件未知；未改 SIM／强制运营商，也未拨号或发短信 |
| Wi-Fi 条件运行 | vendor PMF overlay=1 已安装，保存的测试热点未在刷新扫描出现；关联／DHCP／联网／重连与网络 ADB 未完成 |
| Codec2 条件运行 | MTK AVC 编码与 29 帧硬件解码/EOS 通过；捕获 vpud_native/v3avpud 的真实性能请求；不等于渲染性能／能耗验收 |
| Power 实际探针 | c36757a root C ABI 因读取 su 进程身份的 AVC 返回 EPERM；2cca323 修复待验。私有 0x01468000 明确不支持；默认额外 LAUNCH/INTERACTION 均为 0 |
| 新候选 Recovery／硬件 | 尚未完成；不把 97969dc 的 Recovery status 0、14 项 B 槽回读及启动结果挪用 |

手机当前 c36757a、A 槽、incremental1789925665、Enforcing，依赖上述临时运行改动，暂不再次重启。首次解锁、原测试热点可见以及漫游 eSIM 是否有语音／VoLTE 套餐已询问用户，尚待答复；不索取密码，不更改 SIM。现有授权继续覆盖同基线保数据 OTA、正常／Recovery 重启、回读、临时 adb root、安装／清理测试程序和 Wi-Fi／网络调试。

不可变 c36757a 位于 `verified-candidates/20260921-025828-c36757a/`，OTA SHA-256 `a99afcc0da3fd26fd47537ee3d355abfcf1bec6a42ad262a908c402b1cf455a5`，target-files `5e6ce8367d20feb2f977935a567b29051f323b4f515e143bfa2b45ea53858e39`。固定 IMS APK 为主线 Git blob，SHA-256 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1`；47 个载荷和兼容 dex 已核验，完整原厂依赖打包配方不完整作为 prebuilt 限制明示，不要求旧 Python 工作目录。

3ee80e9 因 shell 写 vendor 属性违反 neverallow 的失败、c36757a 原入口 XML 比较误报和原始启动失败分别保留，不混淆构建／验证／安装／启动。旧 guard 已恢复 0/zbud/N/Y；r3 guard 也已退出并实读恢复 0/zbud/N/Y。当前仍是 userdebug/test-keys，不冒充正式发行签名。详情见 [聚合证据](../validation/mainline-convergence-20260920.json)。

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

2cca323 的不可变候选：`verified-candidates/20260921-040925-2cca323/`；OTA SHA-256 `08e6744536c973a10e4dfa6c4cefff56167d2c16265045f3d9c4af452640adbf`、target-files `b2f9e564bde9f9834da8f66e53a52443320e87dfc7cb9b97b4ebcfa0202f1ef3`。验证源码、同次 host 工具及依赖、记录和设备测试 ELF 均已冻结；主线专项验证对冻结内容再次通过。
