# 适配来源与取舍

本轮接手基线 `462fab1`，未回退。`c36757a` 已通过编译及包重验并保数据安装到 A 槽，安装器与独立回读各 14 项匹配；原镜像因 Power 节点权限问题未正常完成开机，临时 DAC 修正后才进入系统，不能记作候选通过。`2cca323` 按现场证据修复，唯一输出增量构建 13:34、全部包门禁通过，尚待安装。参考树固定到 Dhterech `3dce0bbc357c63b28008e329593a412587618edc`；旧版对照为 `e14a7fa` 和 `archive/hybrid/`。下述结论以源码、实际合并输入、产物及分版本运行证据为准。

## 旧版到主线的完整收敛对照

对照 Git `e14a7fa` 与 `archive/hybrid/`，并检查实际合并源码。下表的旧证据只属于旧版；当前候选尚需独立实机验收。2026-09-20 本轮再次确认五份平台补丁逐字一致；`97969dc` 的 143 个输入文件核对通过；当前 `2cca323` 的 158 个合并源码输入匹配；仅同步 10 个改变的文件，未改变 Android.bp 时间戳。c36757a 的原始启动失败已记录，修正版尚未上机；额外启动／交互 boost 默认关闭。

| 旧版项目／解决的问题 | 旧版实际证据及边界 | 主线实现与位置 | 决定 | 仍缺的验证 | 是否依赖旧流程／旧产物 |
|---|---|---|---|---|---|
| Recovery 侧载缓存，避免缓存随大 OTA 无界增长 | `e14a7fa` 补丁和旧 Recovery 安装记录；不是新 Recovery 内存实测 | `patches/bootable__recovery/0001-sideload-memory.patch`；字节一致，合并源码一致 | 保留 | 新候选侧载、最终 status、内存峰值 | 不需要旧拼装 |
| SystemUI 状态图标排列 | 旧平台补丁及旧版显示记录 | `patches/frameworks__base/0001-status-icon-packing-r2.patch`；字节一致 | 保留 | 新候选多图标／缺口／旋转截图与溢出行为 | 不需要 |
| 状态栏 20dp 边距 | 旧 device 集成 overlay | `device/xiaomi/gold/overlay/GoldStatusBarOverlay` | 保留 | 新候选实际 overlay 生效与横竖屏 | 不需要 |
| TCP conntrack／BPF 回收 | 旧实现和测试差异；没有所有热点场景验收 | `patches/packages__modules__Connectivity/0001-tcp-conntrack-recycling.patch`；字节一致 | 保留 | 定向平台测试和实机连接回收／热点 | 不需要 |
| DeviceDiagnostics 电池信息有效值 | 旧补丁；错误值过滤逻辑可查 | `patches/packages__apps__DeviceDiagnostics/0001-battery-information.patch`；字节一致 | 保留 | 新候选界面和异常值路径 | 不需要 |
| OpenEUICC 物理槽位／设置入口 | 旧补丁、固定子模块；未证明所有 eUICC 场景或本机号码 | `patches/external__openeuicc/0001-service-slot-integration.patch` 与两个固定子模块；字节一致 | 保留 | 当前 eSIM 槽位、入口、运营商配置；不修改用户配置 | 不需要 |
| IMS 动态广播及视频 guard | 旧版有注册与 voice/SMS/UT 能力记录；无完整通话／全运营商验收 | `vendor/xiaomi/gold/ims/` 管理 APK、权限、兼容 Java 和限定 MCC/MNC overlay | 保留受管 prebuilt | c36757a 临时 Power 修正后已绑定且 MMTEL READY；尚未注册，需新候选复验、运营商条件和恢复；无通话／短信授权 | APK 是主线 Git blob；完整原厂依赖打包不可重建是已声明 prebuilt 限制，不要求旧目录 |
| IMS 框架发现和 modem 初始化 | 首次标准候选漏 feature；97969dc 已绑定但缺启动属性，APK 提前退出 | `device.mk` feature、`vendor.prop` 三项匹配 Global 启动配置及包／标签检查 | 主线修复，初始化已见实机进展 | c36757a 条件运行中 mtkIms Binder 存在、双槽 MMTEL READY；有效 carrier VoLTE=false，未注册；需要区分默认配置、套餐和漫游条件并在修正版复验 | 不需要旧流程 |
| TelephonyMetrics 兼容 dex | 固定旧 v5 加 `classes2.dex` 的配方 | 主线 `ims/compat/rebuild.py` 从受管 APK 重编兼容 Java；实际 dex 和全载荷一致 | 保留，移除对旧 v5 目录的必需依赖 | ZIP 字节因宿主压缩元数据不同；新 APK 如要采用必须重新评审 pin | 不需要；闭源主 dex 明确保留 |
| 框架启动／交互 boost 与原厂写权限 | 旧原厂动作与权限可查；无持续收益和功耗对照 | `power/` 统一 AIDL/HIDL、PPM/uclamp 和源码策略；2cca323 使后端故障不阻塞启动并校验未变票值 | 主线修复，默认策略待测 | 修正版编译／启动、SELinux 下动作与复位、同温度启动耗时／帧时间／能耗；不再接管内核共享 display idle 全局值 | 不调用旧流程；性能验收未完成 |
| 厂商性能锁 | 旧原厂 HAL 有实际实现；匹配 Global 有 2 个直接导入者和 16 个动态查找者；c36757a 已捕获 v3avpud 实际调用 | ARM/ARM64 正确 C ABI 转同步 HIDL 1.2；统一身份、更新／超时／并发、门控、读回／回滚；C 句柄绑定原 Binder；2cca323 拒绝不能安全仲裁的显示全局值 | 替代空实现；未支持请求明确报错 | root 探针实测 EPERM 后加入仅调试 su 的身份读权限，待新候选；仍需实际 CPU/uclamp 请求、退出／重启和媒体性能；私有 0x01468000 保持不支持 | 无旧拼装依赖；实际功能验收仍阻塞退出 |
| 32 位应用／双 zygote | 旧工具可修 zygote64_32 闭包，但不是本轮保留目标 | `ro.zygote=zygote64`；包检查验证选中 RC | 按用户要求明确放弃 | 检查无第二 zygote；不做 32 位 APK 兼容 | 不需要旧 zygote 工具 |
| 底层 ARM 库、媒体与图形 ABI | 固定 Global ROM 存在 ARM 文件；首次主线曾缺五个图形库 | BoardConfig 保留 native ARM ABI；提取清单及 graphics-common V7 修正；包检查验证五库与 AIDL 依赖 | 保留 | 新候选媒体／图形实际路径与所有依赖 | 从固定官方镜像提取，不从旧 hybrid 镜像取 |
| 显示模式／刷新率／轮廓 | 旧版与当前基线观察到 60/90/120 Hz；不是新候选省电验证 | Settings 读取实际 supported modes；显示形状来自固定 Global overlay | 保留、标准 overlay 替代 | 新候选切换、熄屏、热控、帧时间 | 不需要 |
| Wi-Fi PMF 与保数据升级 | 97969dc SAE 后关联拒绝 12；data pmf=0 而 vendor 基础模板=1 | 2cd2675 的每次加载 vendor PMF overlay 已随 c36757a 安装，不改网络凭据 | 修复已安装，关联未验收 | 当前刷新扫描未见已保存热点；需热点可用及首次解锁后检查关联、DHCP、联网、重连、网络 ADB | 不依赖旧流程或清数据 |
| 电量统计与 Health | 旧模板功耗 XML 路径有误，首次候选 Health 单位修复已实测 | `res/xml/power_profile.xml`、Gold Health；完整包检查与 8 项单位测试 | 标准源码实现 | 新候选正常系统和关机充电；不挪用旧候选结果 | 不需要 |
| 热控缺失节点诊断 | 旧错误节点诊断有源码依据；权限不能创造控制节点 | `patches/hardware__mediatek/0001-thermal-missing-cooling-diagnostic.patch`，保留实际温控 | 保留 | 新候选持续负载／热控恢复 | 不需要 |
| property contexts 重复归属 | 旧脚本修 `persist.vendor.pco5.radio.ctrl` 和 `vendor.camera.aux.packagelist` 的镜像标签 | 标准源码 SELinux 生成最终 contexts，不再修镜像 | 等价替代 | `97969dc` 正常系统和 Recovery 各有唯一正确标签；仍需新候选运行 AVC | 不需要旧上下层镜像 |
| CIL 版本映射／错误 Binder 规则／neverallow 冲突 | 旧脚本只针对混合 stock vendor 与上层的特定 CIL 语句 | 同一源码策略构建、neverallow 检查；不导入旧版本的手工 CIL | 有依据取消镜像修补 | 新包策略验证；userdebug 调试域与全局 Enforcing 分开记录 | 不需要手工 CIL |
| 内核模块路径／链接／加载闭包 | 旧工具修链接、fs_config 和 labels；旧安装读回不证明新模块启动 | 匹配 Global kernel/modules；标准 system_dlkm/vendor_dlkm，包检查 `/system/lib/modules` 和 `/vendor/lib/modules` | 等价替代 | 同次包签名／模块依赖与启动日志 | 不需要旧模块修补 |
| KeyMint 与 Android 16 ABI | 旧新底包启动记录有限；不能代表全部密钥功能 | `extract-files.py` 使用固定 KeyMint V3 prebuilt ABI；源码 SELinux/init 启动配置 | 标准提取与源码策略替代 | 新候选加密 data 解锁、keystore／证明能力；不伪造硬件安全级别 | 固定官方输入，无旧镜像依赖 |
| Codec2 AIDL 服务 | 旧归档为手写 AIDL/HIDL 包装器，不是完整媒体验收 | 匹配 Global 原厂 64 位 Codec2 服务和必要 ARM 库；主线有期限的解码探针 | 厂商服务替代旧包装器 | c36757a 条件运行下 c2.mtk AVC 编码与 29 帧解码/EOS 通过；不等于渲染、相机录像、DRM 或性能验收；修正版需复验 | 不需要旧 Codec2 patch |
| mi_ext OEM APK mask／渠道 init | 旧 hybrid 需清理 overlay 分区内空 APK 与渠道 init | 当前标准 OTA 分区集合不包含 mi_ext，fstab 不把旧 mi_ext 作为上层应用覆盖 | 有依据取消 | 新候选 mount／软件包路径，确认旧物理内容未参与系统 | 不需要重新打包 mi_ext |
| AVB／FEC／父 vbmeta／OTA 二次签名 | 旧脚本重建 hash tree、FEC、vbmeta；旧签名记录独立 | 标准 `bacon target-files-package`、AOSP 签名/VINTF/SELinux/分区校验；`build-source.py` 是唯一产品构建入口 | 标准构建等价替代 | 97969dc 的 14 分区／20 文件、2cd2675 的 14 分区／21 文件检查通过；c36757a 的 14 分区／29 文件检查通过；正式发行密钥未验收 | 不需要旧签名或旧加工镜像 |
| Recovery 镜像碎片再拼装 | 旧 `build-recovery.py` 用已生成片段重装 vendor_boot | BoardConfig 与标准 vendor_boot init_boot/recovery 片段生成 | 标准构建等价替代 | 新候选 Recovery 安装、往返、分区读回 | 不需要旧 Recovery 脚本 |
| 只读启动观察／槽位判定 | 旧观察工具有 36 项模拟测试 | 主线 `tools/capture_boot.py` 与测试；2cca323 无 archive 导出仍通过 75 项且 IMS 哈希匹配 | 归入主线保留 | 97969dc B 槽稳定观察通过；c36757a 原始启动观察 timeout，临时 DAC 后 boot_complete 不转记为通过 | 不需要归档路径 |
| MDDP WH／全运营商 IMS／持续性能 | 旧记录没有 WH modem 能力位，也未完成这些完整验收 | 不伪造 WH、不全局强制 carrier override；性能按测量决定 | MDDP 无依据功能不导入；其余如实保留未完成状态 | 实际能力与测试条件 | 不作为旧版已通过的遗失能力 |

**当前结论：尚不可删除。** 源码运行入口已不调用旧拼装脚本，但 Power 修正版的构建／原始启动及真实调用／性能实测、IMS 注册与恢复，以及 Wi-Fi 关联仍未闭合。以下路径是满足退出条件后的精确代码删除候选，不是本轮已删除项：

- 本机仓库 `archive/hybrid/`：`README.md`、`stock/vendor-compat.patch`、`patches/hardware__mediatek/0001-aidl-codec2-service.patch`，以及 `tools/` 下 `build-recovery.py`、`build-stock-base.py`、`verify-stock-base.py`、`hybrid_policy.py`、`hybrid_properties.py`、`hybrid_modules.py`、`hybrid_zygote.py`、`capture_boot.py` 和四份测试 `test_capture_boot.py`、`test_hybrid_modules.py`、`test_hybrid_properties.py`、`test_hybrid_zygote.py`。镜像修补功能由上表标准源码／构建替代，唯一需保留的观察工具和测试已经归入主线。
- 科研机集成仓库同名 `project/archive/hybrid/`：与本机受管代码相同；实际合并源码没有此处运行依赖。已盘点科研机任务、systemd、project、history、vendor 中 211 份脚本；相关运行引用只在归档自身，未发现指向 history/hybrid 的符号链接。本机脚本及自动化也未发现归档运行引用。盘点排除原始 dump、proprietary 和镜像目录；其中的历史镜像／唯一输入仍须保留，不能把整个 `history/`、`vendor/` 或 OverlayFS 层当作删除候选。
- 主线仍保留 `prepare-stock.py`、`prepare-vendor.py`、`extract-files.py`、`setup-makefiles.py`、`apply-patches.py`、`build-source.py`、各 `check-*.py`、`capture_boot.py` 和 IMS 兼容验证工具。Python 语言不是删除依据。

## Dhterech 参考

| 参考改动 | 当前决定与依据 |
|---|---|
| `3dce0bb` 32 位媒体图形依赖 | 合并。固定底包存在 `mapper.mediatek.so`、`libgpud.so`、`libgralloc_metadata.so`、`libgralloctypes_mtk.so`、`arm.graphics-V5-ndk.so` 的 32 位版本；旧生成目录/输出缺失。readelf 确认 mapper 的依赖及 graphics-common V5→V7 的现有适配需求 |
| `70fa7c9` 功耗资源安装路径 | 合并到 `res/xml/power_profile.xml`。对照本机固定 Global AospFrameworkResOverlay，38 项数值一致；原厂 `u.core_power.cluster1` 修正为框架读取的 `cpu.core_power.cluster1`。它改善电量归因，不改变 CPU/GPU 频率 |
| `500a352` 刷新率选择 | 合并。当前 Settings 用 `Display.getSupportedModes()` 生成列表，不硬编码 90/120 Hz，不绕过热控 |
| IMS feature 声明 | 实机验收发现遗漏，现补入 AOSP `android.hardware.telephony.ims.xml`。参考树已有等效 prebuilt；当前框架的 PhoneFactory / PhoneGlobals 明确在缺少该 feature 时跳过 ImsPhone / ImsResolver。此修复恢复初始化入口，注册与通话仍需实测 |
| 显示形状 | 采用与固定 Global DevicesAndroidOverlay 相同的轮廓；已有挖孔和圆角保持一致 |
| `2b88853` 旧属性清理 | 移除无读取方的 `ro.telephony.sim.count`、`wifi.supplicant_scan_interval`；同时消除三个相同值重复属性 |
| `376936c` system_dlkm | 不重复应用。主线已经从匹配内核模块通过标准构建生成 system_dlkm |
| `a02e29c` USB 自定义 rc | 已有等效配置，无新增改动 |
| USB NCM | 已包含 Lineage NcmTetheringOverlay；不重复添加设备覆盖 |
| `204c251` ADB 鉴权 | 正常系统保留鉴权。按用户明确要求，90748eb 仅在 userdebug Recovery 启动时设置 ro.adb.secure.recovery=0；不启用全局 WITH_ADB_INSECURE；下一候选待实测 |
| `b1790f9` mmstat 调试删除 | 主线已经没有该 tracing 配置；其 modem 目录删除没有适配证据，不跟随扩大清理 |
| `19a71ff`/`85ca188` Health HAL | 采用独立 Health wrapper；依据当前 6.6.118 实机证据将 charge_counter 从 mAh 转成 µAh，同时覆盖单项查询和 HealthInfo 更新。电流、满充容量保持原有微单位，拒绝负值与整数溢出。不合并按 SOC/数值大小猜测单位的逻辑 |
| `1d8d063` 关机充电 | 主线已有驱动就绪、DRM 等待和显式启动顺序；不叠加另一套 charger 服务 |
| `7b66ebb` 性能 hint/定时数值 | 不照搬旧频率或时长。3ee80e9 用同一资源仲裁器接入实际硬件，框架额外 boost 默认为 0；须同机对照证明收益后再采纳默认值 |
| AOD、相机 UW/macro SKU overlay | 当前 gold_cn 枚举四个相机 ID，但未证明 UW/macro 角色；仍需焦距/镜头、实际拍照及 doze/亮度/唤醒验证 |
| `3d3bf28` 额外 SELinux 规则 | 不整批复制。匹配当前域、对象和实际拒绝后才增加最小规则；保持 neverallow 检查 |
| GS101 memtrack | 未证实当前 GPU 内核接口与实现匹配，不盲换服务 |

## 自有代码修正

振动 HAL 原先声明六种预设效果并设置 `CAP_PERFORM_CALLBACK`，但 `perform()` 永远失败；`on()` 又另起无取消控制的计时线程。现在只报告实际的定时 on/off 能力，框架使用效果 fallback；无支持的 callback 和非法时长在访问驱动前返回明确错误。移除构造函数中无用途的未关闭 fd，sysfs 写入不再包含 NUL。

相机服务实际以 `cameraserver` 运行且属于 `camera` 组。运行目录归属该服务，标定目录保留 system/camera，移除通用 0777/0666 权限和对只读 `/vendor` 的无效 chmod；不改写标定数据。保持原有 SELinux 域与相机标签。

原来只存在于科研机的 Betterr 设置条目现在进入 `patches/series.json`。科研机用于 Soong 的内存环境转发保存于 `tools/host/soong-memory-env.patch`，属于可选宿主补丁，不影响手机运行行为。

## Power 实现与验收边界

`3ee80e9` 用单个 `android.hardware.power-service.gold` 替代 Pixel Power HAL 和 MTK 空服务，ARM／ARM64 的 `libmtkperf_client_vendor` 将真实四参数 C ABI 转入同步 HIDL 1.2；框架 AIDL V6 与厂商请求共享资源表，避免两套控制器重复加速或互相提前释放。

内核节点来自本机 6.6.118 的实际读取。匹配 Global `mtk_ppm_v3.ko`（SHA-256 `16155cde99621ace09384e423f76bc48bc3a685e903b92357a04cf34264d9acc`）反汇编确认 PPM 写协议为 user、cluster、min kHz、max kHz 四个整数；只使用 PERFSERV user 2 的独立票值，-1 释放，读回是 OPP 索引。proc write 返回写入字节数不代表请求有效，因此实现必须验证读回。温控／DLPT 策略保持启用，不修改全局频率上限、governor 或 core_ctl。

统一管理器验证 UID/PID/进程 starttime，处理更新、超时、并发聚合、进程退出、失败回滚和独立的熄屏／省电／空闲／温控限制。所有当前采用的性能资源都限定在 2000 ms 内，当前没有允许零时长持有的资源。无法鉴别 PID 的旧 oneway release 不猜测身份，当前 C 客户端使用可认证的同步释放。未确认的核心数约束和私有 hint 返回明确不支持。

`c36757a` 原始启动失败：`/proc/displowpower/idletime` 为 root:root 0440，HAL 写入失败后在 Binder 注册前退出，框架无法继续。单节点临时 DAC 修正后才 boot_completed=1；这是诊断条件，不是原候选通过。匹配内核 `mediatek-drm.ko`（SHA-256 `18a3559e23dcfa233312a93d0e0c228b0f56c2ed68d56d089b6285c8719384d6`）证明 proc setter 直接写全局 interval，没有每客户端票值／释放协议；实机显示状态也将它改变为 34，不能把 50 当作固定复位。因此 `2cca323` 不扩大其权限、不接管该节点，对 `0x0240c000` 明确返回不支持。普通性能后端故障仍发布控制接口、拒绝资源申请、限速重试，并保持熄屏／省电／空闲及新鲜温控约束。

同次运行的 AVC 解码实际调用者是 `vpud_native` 域的 `v3avpud`，请求 display idle=100 和私有 `0x01468000=0`；后者明确拒绝。1080×1920 的自建 3 秒片段由 `c2.mtk.avc.encoder` 编码，`c2.mtk.avc.decoder` 完成 29 帧和 EOS；无渲染的 276 ms 解码不是播放或能耗成绩。root C ABI 探针则因 HAL 无权读取 su 进程 starttime 返回 EPERM；仅调试版本按该实际 AVC 加最小读权限，不扩展到未经证实的媒体域。

`2cca323` 的 75 项 Python、27 项请求核心及 32 项节点／引擎 Mac arm64 测试通过；完全不含 archive 的新 Git 导出仍通过 75 项且 IMS pin 一致。c36757a 的 Linux 和 ARM／ARM64 确定性测试各为 26+28 项，不能替代新修正实机验证。LAUNCH／INTERACTION 的额外 uclamp 默认均为 0；有界 C ABI 探针增加所有者退出和 HAL 重启，后续必须核对真实节点复位、AVC、启动／帧时间／能耗。无可重复收益则不采用额外 boost。

## IMS 初始化缺口

97969dc 现场完整属性快照缺少 `persist.vendor.ims_support`、`persist.vendor.volte_support` 和 `ro.vendor.md_auto_setup_ims`，仅保留 `persist.vendor.mims_support=2`。固定 APK 的 `ImsApp.onCreate()` 在 ims_support 不是 1 时直接返回；`MtkMmTelFeature` 随后以 3 次、每次 5 秒等待获取未创建的后端。现场实际绑定、长时间 Binder 等待和 UNAVAILABLE 与这条路径吻合。3ee80e9 按匹配 Global 底包恢复这三个启动配置，包检查同时验证最终 vendor/build.prop 与属性标签；不设置每张 SIM 的启用位，不添加全局运营商开通覆盖。

此修复已在 c36757a 的临时 Power DAC 条件下观测到初始化成功，仍不能声称已经注册。当前仍是第二槽漫游 eSIM，需区分正常启动、SIM／运营商开通和漫游限制。现有许可不包含真实通话或短信；先完成无需这些操作的初始化、能力和恢复验证。

构建工具在重写可变 OTA 前拆开历史日期文件的硬链接，避免下一次构建覆盖上一份证据。新增回归测试实际覆写可变路径后检查历史文件内容不变。

## 本轮实机依据

[只读基线记录](../validation/device-baseline-20260920.json) 属于手机原有系统：6.6.118、B 槽、Enforcing、已完成启动并运行约 70 小时，非本轮候选验收。91% 时 charge_counter=4515，而 charge_full=4962300、设计容量=5000000；Android 错将 4515 作为 µAh 上报。这是引入确定性单位适配的依据。刷新率由屏幕报告 60/90/120 Hz。shell 无权读取 persist/相机目录，未更改设备权限。

9 月 20 日首次候选保数据 OTA 后，A 槽正常启动，Health 已将内核 4952 mAh 正确换算为 Android 的 4952000 µAh，ARM64 / ARM 振动契约测试各通过 4 项。漫游 eSIM 可注册 LTE，但系统没有 IMS feature，标准框架因而未初始化 IMS；已经存在 APK 和 overlay 并不足以提供该功能。详见 [实机记录](../validation/device-acceptance-20260920.json)。

97969dc 已于本轮保数据侧载后从 B 槽正常启动，Enforcing、data/persist、Virtual A/B state none 和两个校验文件保留均已确认。最终 Recovery status 0、安装器 14 项哈希及独立 B 槽 14 分区镜像范围回读均已取得并匹配。c36757a 已完成编译和独立产物校验，当前正通过标准 update_engine 向非活动 A 槽安装；新候选启动和硬件结果尚未取得。现场 IMS 已绑定但 UNAVAILABLE，Wi-Fi 仍未关联。详见 [本轮汇总证据](../validation/mainline-convergence-20260920.json)。

在 c36757a 的临时 Power DAC 诊断条件下，三项 IMS 属性均为 1，mtkIms 后端和双槽 MMTEL READY 已观测到，注册和 Voice/Video/UT/SMS 能力仍未成立。通过 `cmd phone cc get-value -s 1` 单独读取所用卡的有效配置：carrier_config_applied=true、carrier_volte_available=false；不是把 dumpsys 开头的框架默认值误当有效配置。框架 isVolteEnabledByPlatform=false，与配置一致；套餐语音资格和漫游条件未知，未全局覆盖运营商，也未改 SIM 或发送通话／短信。新候选的正常启动与恢复仍需复验。
