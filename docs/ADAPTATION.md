# 适配来源与取舍

本轮接手基线 `462fab1`；`97969dc` 已安装并在 B 槽启动；`2cd2675` 已完成构建和包验证但未安装；IMS 初始化、Power 接入及调试 Recovery 的集成版本 `3ee80e9` 因性能属性写权限违反 neverallow 构建失败；`f17a75a` 的客户端句柄隔离／探针和 `c36757a` 的 vendor 自有配置入口已同步，正在增量构建；参考树固定到 Dhterech `3dce0bbc357c63b28008e329593a412587618edc`。v1 对照重构前 `e14a7fa` 和 `archive/hybrid/`。迁移报告只用于寻找材料；下面的取舍依据实际源码、构建输入、接口实现与已保留证据。

## 旧版到主线的完整收敛对照

对照 Git `e14a7fa` 与 `archive/hybrid/`，并检查实际合并源码。下表的旧证据只属于旧版；当前候选尚需独立实机验收。2026-09-20 本轮再次确认五份平台补丁逐字一致；`97969dc` 的 143 个输入文件核对通过；当前 `c36757a` 的 158 个合并源码文件与受管输入一致。Power 已接入待编译候选，尚未上机；额外启动／交互 boost 默认关闭。

| 旧版项目／解决的问题 | 旧版实际证据及边界 | 主线实现与位置 | 决定 | 仍缺的验证 | 是否依赖旧流程／旧产物 |
|---|---|---|---|---|---|
| Recovery 侧载缓存，避免缓存随大 OTA 无界增长 | `e14a7fa` 补丁和旧 Recovery 安装记录；不是新 Recovery 内存实测 | `patches/bootable__recovery/0001-sideload-memory.patch`；字节一致，合并源码一致 | 保留 | 新候选侧载、最终 status、内存峰值 | 不需要旧拼装 |
| SystemUI 状态图标排列 | 旧平台补丁及旧版显示记录 | `patches/frameworks__base/0001-status-icon-packing-r2.patch`；字节一致 | 保留 | 新候选多图标／缺口／旋转截图与溢出行为 | 不需要 |
| 状态栏 20dp 边距 | 旧 device 集成 overlay | `device/xiaomi/gold/overlay/GoldStatusBarOverlay` | 保留 | 新候选实际 overlay 生效与横竖屏 | 不需要 |
| TCP conntrack／BPF 回收 | 旧实现和测试差异；没有所有热点场景验收 | `patches/packages__modules__Connectivity/0001-tcp-conntrack-recycling.patch`；字节一致 | 保留 | 定向平台测试和实机连接回收／热点 | 不需要 |
| DeviceDiagnostics 电池信息有效值 | 旧补丁；错误值过滤逻辑可查 | `patches/packages__apps__DeviceDiagnostics/0001-battery-information.patch`；字节一致 | 保留 | 新候选界面和异常值路径 | 不需要 |
| OpenEUICC 物理槽位／设置入口 | 旧补丁、固定子模块；未证明所有 eUICC 场景或本机号码 | `patches/external__openeuicc/0001-service-slot-integration.patch` 与两个固定子模块；字节一致 | 保留 | 当前 eSIM 槽位、入口、运营商配置；不修改用户配置 | 不需要 |
| IMS 动态广播及视频 guard | 旧版有注册与 voice/SMS/UT 能力记录；没有完整通话／全运营商验收 | `vendor/xiaomi/gold/ims/` 管理 APK、权限、补丁、兼容 Java 和限定 MCC/MNC overlay | 保留受管 prebuilt | 97969dc 已绑定但 MMTEL 为 UNAVAILABLE；修正版需验证 modem 初始化、注册、能力和重启恢复；通话／短信尚未获授权 | APK 为主线 Git blob，不依赖旧目录；完整原厂依赖打包仍不可重建，但不阻塞独立取得输入 |
| IMS 框架发现和 modem 初始化 | 首次标准候选漏 feature；97969dc 补 feature 后实际绑定，但现场属性缺 IMS 启动开关，APK 提前退出后端初始化 | `device.mk` 标准 feature；`vendor.prop` 补匹配 Global 的 ims_support、volte_support、md_auto_setup_ims；包检查覆盖 47 个 APK 载荷、权限、属性和标签 | 主线修复，待上机 | 绑定已在 97969dc 证明；3ee80e9 尚需 modem 后端和真实注册／能力，不强制所有运营商 | 不需要旧流程 |
| TelephonyMetrics 兼容 dex | 固定旧 v5 加 `classes2.dex` 的配方 | 主线 `ims/compat/rebuild.py` 从受管 APK 重编兼容 Java；实际 dex 和全载荷一致 | 保留，移除对旧 v5 目录的必需依赖 | ZIP 字节因宿主压缩元数据不同；新 APK 如要采用必须重新评审 pin | 不需要；闭源主 dex 明确保留 |
| 框架启动／交互 boost 与原厂写权限 | 旧 restorecon/CIL、原厂动作可查；没有持续性能与功耗对照 | `power/` 统一 AIDL/HIDL 管理器、实际 PPM/uclamp/display 节点和源码 SELinux；LAUNCH/INTERACTION 策略默认关闭供同二进制对照 | 主线实现，尚未运行验收 | Android 编译、SELinux 下动作／复位、同温度启动耗时／帧时间／能耗 | 不调用旧流程；未达到性能验收 |
| 厂商性能锁 | 旧原厂 HAL 有实际实现；2 个 OAL 直接导入者及 16 个动态查找者来自匹配 Global；尚无运行调用轨迹 | `0002-perf-client-forwarding.patch` 修正 ARM/ARM64 C ABI，并通过 HIDL 1.2 转入同一 PowerEngine；所有者、超时、并发、温控、省电和回读失败处理有主机测试；f17a75a 防止重启后的远端句柄复用误伤新请求，并提供实际 C ABI 探针及有界调用记录 | 替代空实现，待编译与实测 | 实际调用参数／未支持 core 约束、进程退出、重连、媒体行为；不把错误返回或虚构句柄当成功 | 不依赖旧拼装；功能验收仍阻塞退出 |
| 32 位应用／双 zygote | 旧工具可修 zygote64_32 闭包，但不是本轮保留目标 | `ro.zygote=zygote64`；包检查验证选中 RC | 按用户要求明确放弃 | 检查无第二 zygote；不做 32 位 APK 兼容 | 不需要旧 zygote 工具 |
| 底层 ARM 库、媒体与图形 ABI | 固定 Global ROM 存在 ARM 文件；首次主线曾缺五个图形库 | BoardConfig 保留 native ARM ABI；提取清单及 graphics-common V7 修正；包检查验证五库与 AIDL 依赖 | 保留 | 新候选媒体／图形实际路径与所有依赖 | 从固定官方镜像提取，不从旧 hybrid 镜像取 |
| 显示模式／刷新率／轮廓 | 旧版与当前基线观察到 60/90/120 Hz；不是新候选省电验证 | Settings 读取实际 supported modes；显示形状来自固定 Global overlay | 保留、标准 overlay 替代 | 新候选切换、熄屏、热控、帧时间 | 不需要 |
| Wi-Fi PMF 与保数据升级 | SAE 鉴权成功后关联拒绝 12；97969dc 上机证明 data pmf=0、vendor 基础模板=1 且 overlay 未覆盖 | `2cd2675` 把 PMF=1 同时纳入基础模板及每次加载的 vendor overlay，不修改网络凭据 | 主线修复，已构建，待上机 | 关联、DHCP、联网、重连及网络 ADB；不以修改热点兼容模式作为完成依据 | 不依赖旧流程或清数据 |
| 电量统计与 Health | 旧模板功耗 XML 路径有误，首次候选 Health 单位修复已实测 | `res/xml/power_profile.xml`、Gold Health；完整包检查与 8 项单位测试 | 标准源码实现 | 新候选正常系统和关机充电；不挪用旧候选结果 | 不需要 |
| 热控缺失节点诊断 | 旧错误节点诊断有源码依据；权限不能创造控制节点 | `patches/hardware__mediatek/0001-thermal-missing-cooling-diagnostic.patch`，保留实际温控 | 保留 | 新候选持续负载／热控恢复 | 不需要 |
| property contexts 重复归属 | 旧脚本修 `persist.vendor.pco5.radio.ctrl` 和 `vendor.camera.aux.packagelist` 的镜像标签 | 标准源码 SELinux 生成最终 contexts，不再修镜像 | 等价替代 | `97969dc` 正常系统和 Recovery 各有唯一正确标签；仍需新候选运行 AVC | 不需要旧上下层镜像 |
| CIL 版本映射／错误 Binder 规则／neverallow 冲突 | 旧脚本只针对混合 stock vendor 与上层的特定 CIL 语句 | 同一源码策略构建、neverallow 检查；不导入旧版本的手工 CIL | 有依据取消镜像修补 | 新包策略验证；userdebug 调试域与全局 Enforcing 分开记录 | 不需要手工 CIL |
| 内核模块路径／链接／加载闭包 | 旧工具修链接、fs_config 和 labels；旧安装读回不证明新模块启动 | 匹配 Global kernel/modules；标准 system_dlkm/vendor_dlkm，包检查 `/system/lib/modules` 和 `/vendor/lib/modules` | 等价替代 | 同次包签名／模块依赖与启动日志 | 不需要旧模块修补 |
| KeyMint 与 Android 16 ABI | 旧新底包启动记录有限；不能代表全部密钥功能 | `extract-files.py` 使用固定 KeyMint V3 prebuilt ABI；源码 SELinux/init 启动配置 | 标准提取与源码策略替代 | 新候选加密 data 解锁、keystore／证明能力；不伪造硬件安全级别 | 固定官方输入，无旧镜像依赖 |
| Codec2 AIDL 服务 | 旧归档 patch 包含手写 AIDL/HIDL 包装器；并非完整编解码验收 | 固定 Global `android.hardware.media.c2-mediatek-64b` 提取为标准服务，AIDL IComponentStore/default；保留需要的 ARM 库 | 厂商匹配服务替代旧包装器 | 新候选编解码、相机视频、DRM／媒体性能锁 | 不需要归档 Codec2 patch |
| mi_ext OEM APK mask／渠道 init | 旧 hybrid 需清理 overlay 分区内空 APK 与渠道 init | 当前标准 OTA 分区集合不包含 mi_ext，fstab 不把旧 mi_ext 作为上层应用覆盖 | 有依据取消 | 新候选 mount／软件包路径，确认旧物理内容未参与系统 | 不需要重新打包 mi_ext |
| AVB／FEC／父 vbmeta／OTA 二次签名 | 旧脚本重建 hash tree、FEC、vbmeta；旧签名记录独立 | 标准 `bacon target-files-package`、AOSP 签名/VINTF/SELinux/分区校验；`build-source.py` 是唯一产品构建入口 | 标准构建等价替代 | 97969dc 的 14 分区／20 文件、2cd2675 的 14 分区／21 文件检查通过；c36757a 待终态；正式发行密钥未验收 | 不需要旧签名或旧加工镜像 |
| Recovery 镜像碎片再拼装 | 旧 `build-recovery.py` 用已生成片段重装 vendor_boot | BoardConfig 与标准 vendor_boot init_boot/recovery 片段生成 | 标准构建等价替代 | 新候选 Recovery 安装、往返、分区读回 | 不需要旧 Recovery 脚本 |
| 只读启动观察／槽位判定 | 旧 capture_boot 有 36 项客户端／时钟模拟测试 | `tools/capture_boot.py` 与 `tests/test_capture_boot.py`；f17a75a 主线无 archive 导出 71 项测试通过 | 归入主线保留 | 97969dc B 槽 9 个稳定样本、21.47 秒观察通过；c36757a 尚未安装 | 不需要归档路径 |
| MDDP WH／全运营商 IMS／持续性能 | 旧记录没有 WH modem 能力位，也未完成这些完整验收 | 不伪造 WH、不全局强制 carrier override；性能按测量决定 | MDDP 无依据功能不导入；其余如实保留未完成状态 | 实际能力与测试条件 | 不作为旧版已通过的遗失能力 |

**当前结论：尚不可删除。** 源码运行入口已不调用旧拼装脚本，但 Power 的 Android 构建与真实调用／性能实测、IMS 后端初始化修复后的注册与恢复，以及 Wi-Fi 关联故障仍未闭合。以下路径是满足退出条件后的精确代码删除候选，不是本轮已删除项：

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

统一管理器验证 UID/PID/进程 starttime，处理更新、超时、并发聚合、进程退出、失败回滚和独立的熄屏／省电／空闲／温控限制。频率请求上限 2000 ms；只有已经确认实际调用的 display idle 资源允许零时长持有。无法鉴别 PID 的旧 oneway release 不猜测身份，当前 C 客户端使用可认证的同步释放。未确认的核心数约束和私有 hint 返回明确不支持。

请求核心 26 项 Mac arm64 和 26 项 Soong 构建的 Linux x86_64 测试通过；节点／引擎额外 26 项 Mac arm64 用例通过。Android 服务、C ABI 转发与 SELinux 下硬件动作尚未验证，不能把这些主机测试记作性能收益。LAUNCH／INTERACTION 的额外 uclamp 默认均为 0；受限临时属性仅供同二进制 A/B 测试。下一步需要实际厂商调用记录、独立 kernel 读回和复位，再对照启动耗时、交互帧时间与能耗／温升；没有可重复收益就不采用额外 boost。

## IMS 初始化缺口

97969dc 现场完整属性快照缺少 `persist.vendor.ims_support`、`persist.vendor.volte_support` 和 `ro.vendor.md_auto_setup_ims`，仅保留 `persist.vendor.mims_support=2`。固定 APK 的 `ImsApp.onCreate()` 在 ims_support 不是 1 时直接返回；`MtkMmTelFeature` 随后以 3 次、每次 5 秒等待获取未创建的后端。现场实际绑定、长时间 Binder 等待和 UNAVAILABLE 与这条路径吻合。3ee80e9 按匹配 Global 底包恢复这三个启动配置，包检查同时验证最终 vendor/build.prop 与属性标签；不设置每张 SIM 的启用位，不添加全局运营商开通覆盖。

此修复尚未上机，不能据此声称已经注册。当前仍是第二槽漫游 eSIM，需区分后端初始化错误、SIM／运营商开通和漫游限制。现有许可不包含真实通话或短信；先完成无需这些操作的初始化、能力和恢复验证。

构建工具在重写可变 OTA 前拆开历史日期文件的硬链接，避免下一次构建覆盖上一份证据。新增回归测试实际覆写可变路径后检查历史文件内容不变。

## 本轮实机依据

[只读基线记录](../validation/device-baseline-20260920.json) 属于手机原有系统：6.6.118、B 槽、Enforcing、已完成启动并运行约 70 小时，非本轮候选验收。91% 时 charge_counter=4515，而 charge_full=4962300、设计容量=5000000；Android 错将 4515 作为 µAh 上报。这是引入确定性单位适配的依据。刷新率由屏幕报告 60/90/120 Hz。shell 无权读取 persist/相机目录，未更改设备权限。

9 月 20 日首次候选保数据 OTA 后，A 槽正常启动，Health 已将内核 4952 mAh 正确换算为 Android 的 4952000 µAh，ARM64 / ARM 振动契约测试各通过 4 项。漫游 eSIM 可注册 LTE，但系统没有 IMS feature，标准框架因而未初始化 IMS；已经存在 APK 和 overlay 并不足以提供该功能。详见 [实机记录](../validation/device-acceptance-20260920.json)。

97969dc 已于本轮保数据侧载后从 B 槽正常启动，Enforcing、data/persist、Virtual A/B state none 和两个校验文件保留均已确认。最终 Recovery 日志和独立分区回读尚未取得；新集成候选未安装。现场 IMS 已绑定但 UNAVAILABLE，Wi-Fi 仍未关联。详见 [本轮汇总证据](../validation/mainline-convergence-20260920.json)。
