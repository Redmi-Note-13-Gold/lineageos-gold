# 适配来源与取舍

本轮接手基线 `462fab1`，未回退。当前手机为 bd50b19 原镜像 A 槽、incremental 1789938387：保数据 OTA、安装器与独立回读各 14 项、正常启动、两份 canary 和 Recovery 自动 ADB 往返通过。Codec2 的 336／352 字节 ABI 修复已独立通过 3 次冷服务启动与 11 轮编解码；Power 生命周期、节点和诊断入口复验通过。参考树固定到 Dhterech `3dce0bbc357c63b28008e329593a412587618edc`；旧版对照为 Git `e14a7fa` 与 `0fed0d2` 中的历史 `archive/hybrid/`。

## 旧版到主线的完整收敛对照

对照 Git `e14a7fa` 与 `0fed0d2` 中的历史 `archive/hybrid/`，并检查实际合并源码。旧证据只属于旧版。在 bd50b19 对照阶段，五份迁入平台补丁逐字一致；本轮 OpenEUICC 和 SystemUI 后续修复仍在这些主线入口维护。97969dc 的 143 项、2cca323／3cb28c3 的 158 项以及 bd50b19 的 161 项合并输入分别核对通过。新 Codec2 入口使 Android.bp 有实际变化；仅重生成对应 vendor 定义，未重提取。额外启动／交互 boost 默认关闭。

| 旧版项目／解决的问题 | 旧版实际证据及边界 | 主线实现与位置 | 决定 | 仍缺的验证 | 是否依赖旧流程／旧产物 |
|---|---|---|---|---|---|
| Recovery 侧载缓存，避免缓存随大 OTA 无界增长 | `e14a7fa` 补丁和旧 Recovery 安装记录；不是新 Recovery 内存实测 | `patches/bootable__recovery/0001-sideload-memory.patch`；字节及合并源码一致；实际源码 Linux FUSE 3 项通过，32 MiB 上限、重读校验与 malloc 失败降级有效 | 保留 | 设备签名侧载／32 MiB 缓存／RSS 已定向通过；尚未做设备分配失败注入或完整 Recovery OTA | 不需要旧拼装 |
| SystemUI 状态图标排列 | 旧平台补丁及旧版显示记录 | `patches/frameworks__base/0001-status-icon-packing-r2.patch`；字节一致；bd50b19 横竖屏现有时钟／网络／电量图标未见重叠裁切 | 保留 | 本轮溢出／RTL 已补验，发现横屏 111px／55px 不对称；新修复待镜像 | 不需要 |
| 状态栏 20dp 边距 | 旧 device 集成 overlay | `device/xiaomi/gold/overlay/GoldStatusBarOverlay`；bd50b19 实际资源 55px／density 2.75=20dp，横竖屏已目视 | 保留且定向验证通过 | 横屏非对称边距已复现，修复后需再验 LTR／RTL | 不需要 |
| TCP conntrack／BPF 回收 | 旧实现和测试差异；没有所有热点场景验收 | `patches/packages__modules__Connectivity/0001-tcp-conntrack-recycling.patch`；字节一致；实际已装 TetheringNext 解析器与事件类 13 项通过，缺失／非法字段返回 UNKNOWN | 保留 | 实机 BPF 双向规则删除、连接回收／热点；当前探针不写 BPF | 不需要 |
| DeviceDiagnostics 电池信息有效值 | 旧补丁；错误值过滤逻辑可查 | `patches/packages__apps__DeviceDiagnostics/0001-battery-information.patch`；字节一致 | 保留 | bd50b19 界面与实际不可用值隐藏通过；非法边界注入未做 | 不需要 |
| OpenEUICC 物理槽位／设置入口 | 旧补丁、固定子模块；未证明所有 eUICC 场景或本机号码 | `patches/external__openeuicc/0001-service-slot-integration.patch` 与两个固定子模块；字节一致 | 保留 | 已发现管理入口和快捷方式崩溃；主线修复后需只读管理页验收，不修改 SIM | 不需要 |
| IMS 动态广播及视频 guard | 旧版有注册与 voice/SMS/UT 能力记录；无完整通话／全运营商验收 | `vendor/xiaomi/gold/ims/` 管理 APK、权限、兼容 Java 和限定 MCC/MNC overlay | 保留受管 prebuilt | bd50b19 原镜像及 Recovery 往返后已绑定且 MMTEL READY；尚未注册，需核对有效配置、套餐与漫游条件；无通话／短信授权 | APK 是主线 Git blob；完整原厂依赖打包不可重建是已声明 prebuilt 限制，不要求旧目录 |
| IMS 框架发现和 modem 初始化 | 首次标准候选漏 feature；97969dc 已绑定但缺启动属性，APK 提前退出 | `device.mk` feature、`vendor.prop` 三项匹配 Global 启动配置及包／标签检查 | 主线修复，初始化及重启恢复已验证 | bd50b19 原镜像的 mtkIms Binder、双槽 MMTEL READY 和 Recovery 往返恢复通过；有效 carrier VoLTE=false，注册／能力仍未通过，不能直接归因运营商 | 不需要旧流程 |
| TelephonyMetrics 兼容 dex | 固定旧 v5 加 `classes2.dex` 的配方 | 主线 `ims/compat/rebuild.py` 从受管 APK 重编兼容 Java；实际 dex 和全载荷一致 | 保留，移除对旧 v5 目录的必需依赖 | ZIP 字节因宿主压缩元数据不同；新 APK 如要采用必须重新评审 pin | 不需要；闭源主 dex 明确保留 |
| 框架启动／交互 boost 与原厂写权限 | 旧原厂动作与权限可查；无持续收益和功耗对照 | `power/` 统一 AIDL/HIDL、PPM/uclamp，框架启动与独立交互请求实读动作及释放通过；不接管共享 display idle | 主线资源管理保留，额外 20 策略无可靠收益不采用 | 同机无外部电源 11 组启动／4 组滚动对照已完成；默认 0／0。未证明所有应用或长期续航等价 | 不调用旧流程 |
| 厂商性能锁 | 旧原厂 HAL 有实际实现；Global 有 2 个直接导入者和 16 个动态查找者；已捕获 vpud_native/v3avpud 的实际请求 | ARM/ARM64 C ABI→同步 HIDL 1.2；统一身份、生命周期、门控及回滚；句柄绑定原 Binder | 替代空实现；未支持请求明确报错 | bd50b19 两 ABI 生命周期、退出及重启通过；实际媒体 0x0240c000 为无独占释放语义的共享显示节点，0x01468000 不在匹配底包 180 项配置表中，未支持仍需限定需求；不声称闭源代码也无该资源 | 无旧拼装依赖；不把未支持请求返回成功 |
| 32 位应用／双 zygote | 旧工具可修 zygote64_32 闭包，但不是本轮保留目标 | `ro.zygote=zygote64`；包检查验证选中 RC | 按用户要求明确放弃 | 检查无第二 zygote；不做 32 位 APK 兼容 | 不需要旧 zygote 工具 |
| 底层 ARM 库、媒体与图形 ABI | 固定 Global ROM 存在 ARM 文件；首次主线曾缺五个图形库 | BoardConfig 保留 native ARM ABI；提取清单及 graphics-common V7 修正；包检查验证五库与 AIDL 依赖 | 保留 | 新候选媒体／图形实际路径与所有依赖 | 从固定官方镜像提取，不从旧 hybrid 镜像取 |
| 显示模式／刷新率／轮廓 | 旧版与基线有 60/90/120 Hz；不是新候选省电验证 | Settings 读取实际 supported modes；固定 Global 轮廓；bd50b19 三种窗口请求均实际切换并采样 vsync | 保留、标准 overlay 替代 | Settings 各入口及长期热控；Choreographer 采样不冒充面板精密测量 | 不需要 |
| Wi-Fi PMF 与保数据升级 | 97969dc SAE 后关联拒绝 12；data pmf=0 而 vendor 基础模板=1 | 每次加载的 vendor PMF overlay 已随 2cca323 原镜像安装，不改网络凭据 | bd50b19 关联与联网通过 | WPA3／DHCP／HTTPS 和网络 ADB 通过；两次重连一次显式、一次自动。部分连接探测与恢复后一致自动重连仍需区分验证 | 不依赖旧流程或清数据 |
| 电量统计与 Health | 旧模板功耗 XML 路径有误，首次候选 Health 单位修复已实测 | `res/xml/power_profile.xml`、Gold Health；完整包检查与 8 项单位测试 | 标准源码实现 | 新候选正常系统和关机充电；不挪用旧候选结果 | 不需要 |
| 热控缺失节点诊断 | 旧错误节点诊断有源码依据；权限不能创造控制节点 | `patches/hardware__mediatek/0001-thermal-missing-cooling-diagnostic.patch`，保留实际温控 | 保留 | 新候选持续负载／热控恢复 | 不需要 |
| property contexts 重复归属 | 旧脚本修 `persist.vendor.pco5.radio.ctrl` 和 `vendor.camera.aux.packagelist` 的镜像标签 | 标准源码 SELinux 生成最终 contexts；bd50b19 实读对应 system_mtk_pco_prop／vendor_persist_camera_prop，IMS 为 vendor_mtk_ims_prop | 等价替代 | 持续实际工作负载 AVC，不以短窗口冒充全部场景 | 不需要旧上下层镜像 |
| CIL 版本映射／错误 Binder 规则／neverallow 冲突 | 旧脚本只针对混合 stock vendor 与上层的特定 CIL 语句 | 同一源码策略构建、neverallow 检查；不导入旧版本的手工 CIL | 有依据取消镜像修补 | 新包策略验证；userdebug 调试域与全局 Enforcing 分开记录 | 不需要手工 CIL |
| 内核模块路径／链接／加载闭包 | 旧工具修链接、fs_config 和 labels；旧读回不证明新模块启动 | 匹配 Global kernel/modules；标准 system_dlkm/vendor_dlkm，bd50b19 两模块链接与 421 个已加载模块条目实读 | 等价替代 | 各模块对应硬件的完整工作负载仍单列 | 不需要旧模块修补 |
| KeyMint 与 Android 16 ABI | 旧新底包启动记录有限；不代表全部密钥功能 | 固定 KeyMint V3 prebuilt ABI＋源码策略；bd50b19 普通应用经 Enforcing HAL 的 TEE EC／RSA／AES-GCM 正常操作与篡改拒绝通过，3 把自建密钥清理 | 标准提取与源码策略替代 | 硬件证明、认证绑定密钥未测；不伪造硬件安全级别 | 固定官方输入，无旧镜像依赖 |
| Codec2 AIDL 服务 | 旧源码入口有价值，但旧 AIDL/HIDL 包装器不等于完整媒体验收；2cca323 原厂入口首次编码崩溃推翻其等价替代判断 | `device/xiaomi/gold/codec2/` 按当前平台头文件编译 AIDL 入口，保留 Global store／编解码库、原服务与沙箱；不硬改二进制 malloc 常数 | 归入主线源码，替代旧包装器与失配原厂入口 | bd50b19 编译及包门禁、3 次冷启动／11 轮 AVC 编解码通过，实际日志 352 字节且 PID 稳定无相关崩溃；实际 1080p 录像及 216 帧 MTK 解码已通过；全部格式／画质／长时仍未测 | 不调用 archive patch；旧入口源码替代已完成针对性构建／运行验证 |
| mi_ext OEM APK mask／渠道 init | 旧 hybrid 需清理 overlay 分区内空 APK 与渠道 init | 当前标准 OTA 分区集合不包含 mi_ext，fstab 不把旧 mi_ext 作为上层应用覆盖 | 有依据取消 | 新候选 mount／软件包路径，确认旧物理内容未参与系统 | 不需要重新打包 mi_ext |
| AVB／FEC／父 vbmeta／OTA 二次签名 | 旧脚本重建 hash tree、FEC、vbmeta；旧签名记录独立 | 标准 `bacon target-files-package`、AOSP 签名/VINTF/SELinux/分区校验；`build-source.py` 是唯一产品构建入口 | 标准构建等价替代 | 2cca323／3cb28c3 各 14 分区／29 实际文件门禁通过；bd50b19 的 35 文件／14 分区、安装器与独立 A14 回读通过；正式发行密钥未验收 | 不需要旧签名或旧加工镜像 |
| Recovery 镜像碎片再拼装 | 旧 `build-recovery.py` 用已生成片段重装 vendor_boot | BoardConfig 与标准 vendor_boot init_boot/recovery 片段生成 | 标准构建等价替代 | bd50b19 vendor_boot 回读、Recovery 自动 ADB、Enforcing 与往返独立通过，侧载签名验证的缓存内存峰值已补验；完整 Recovery OTA 安装未重复 | 不需要旧 Recovery 脚本 |
| 只读启动观察／槽位判定 | 旧观察工具有 36 项模拟测试 | 主线 `tools/capture_boot.py` 与测试；无 archive 的 3dcd922 新导出通过 75 项且 IMS 哈希匹配 | 归入主线保留 | bd50b19 两次 A 槽启动观察 exit 0、各稳定超过 20 秒；c36757a 原始启动失败仍保留，不把临时 DAC 当成功 | 不需要归档路径 |
| MDDP WH／全运营商 IMS／持续性能 | 旧记录没有 WH modem 能力位，也未完成这些完整验收 | 不伪造 WH、不全局强制 carrier override；性能按测量决定 | MDDP 无依据功能不导入；其余如实保留未完成状态 | 实际能力与测试条件 | 不作为旧版已通过的遗失能力 |

**当前结论：旧 hybrid 运行代码已按用户后续明确授权退出工作树，完整功能验收仍未完成。** 当前维护、构建和验证入口不调用旧拼装。bd50b19 的构建、安装、回读、启动、Codec2 和 Power 等通过范围保持不变；IMS 注册／能力按用户要求延后；Recovery 峰值已补验，实际 BPF 回收和界面缺陷继续在主线跟进。删除不将这些项目改记为通过，也不宣称完成从零 Android 全量重建。

2026-09-21 用户在区分运行依赖与功能验收后明确要求删除不再需要的旧实现。下列 15 个受管文件已成组移除（旧 Codec2 补丁此前已局部删除）；原内容可从 Git 提交 `0fed0d2e8f5d60fa1c7e5a3ecbe4a18377e5964f` 的同名路径读取，不复制另一套可运行工程：

- `archive/hybrid/README.md`：当前说明统一到本文件及 STATUS/LAYOUT。
- `archive/hybrid/patches/hardware__mediatek/0001-aidl-codec2-service.patch`：主线当前平台 AIDL 入口已完成针对性构建和设备生命周期验证。
- `archive/hybrid/stock/vendor-compat.patch`，以及 `archive/hybrid/tools/` 下的 `build-stock-base.py`、`verify-stock-base.py`、`build-recovery.py`、`hybrid_policy.py`、`hybrid_properties.py`、`hybrid_modules.py`：标准源码策略、镜像/DLKM生成和产物校验已接管；内部调用者与补丁一并退役。
- 同一旧 tools 目录的 `hybrid_zygote.py`、`test_hybrid_zygote.py`：双 zygote 应用兼容已明确放弃，底层 ARM 库仍由主线保留。
- 同一旧 tools 目录的 `capture_boot.py`、`test_capture_boot.py`：观察工具与主线逐字一致，测试差异仅为主线导入路径，当前工具及测试继续维护。
- 同一旧 tools 目录的 `test_hybrid_modules.py`、`test_hybrid_properties.py`：只验证已退役的镜像修补实现，与对应旧实现一起退出。

科研机执行与验证记录：`/srv/build/gold/jobs/gold-mainline-20260920/archive-retirement-20260921.json`。核验包括归档外运行引用、当前主机工具测试、固定 IMS 输入及 161 项实际合并输入；设备 README 只更新历史定位，编译配置、服务源码、输出、OverlayFS 和缓存保持原状。历史镜像、官方输入、Git 历史及所有许可证继续保留。若交互终端仍位于原目录，可暂留空目录；它不包含可运行旧流程。

主线继续维护 `prepare-stock.py`、`prepare-vendor.py`、`extract-files.py`、`setup-makefiles.py`、`apply-patches.py`、`build-source.py`、各 `check-*.py`、`capture_boot.py`、IMS 兼容工具和测试。Python 语言不是删除依据。

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
| `204c251` ADB 鉴权 | 正常系统保留鉴权。按用户明确要求，90748eb 仅在 userdebug Recovery 启动时设置 ro.adb.secure.recovery=0；不启用全局 WITH_ADB_INSECURE；2cca323 的 Recovery 自动 ADB 已实测通过，正常系统仍鉴权 |
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

2cca323 的 ARM64／ARM 各 27 项请求、32 项节点／引擎确定性测试通过，两 ABI 经已安装 C 库和运行中的 Enforcing HAL 完成申请、并发聚合、更新、独立释放、超时及明确拒绝测试。2000 ms 请求不 release 而退出后，按采样窗口的保守上界 339.39 ms 已归零；真实 HAL 重启后旧 Binder 不自动重放申请，旧句柄不能释放新票值。另在确认无竞争票值并受控停 HAL 后，用 150 ms 探针写入 uclamp=10 和 1048000 kHz 下限，读回、到期复位与 HAL 恢复通过。硬件探针不替代前述运行 HAL 权限测试。

2cca323 的普通 shell dump 因 HAL 写 shell FIFO 的 AVC 失败，root 策略命令因上游 Lineage userdebug 固定 ro.debuggable=0 被错误拒绝。3cb28c3 仅补实际 FIFO 写权限，并以不可变 ro.build.type 的 userdebug/eng 加 UID 0 作为调试入口；不扩大 shell/su 的 vendor 属性权限。该修正的独立 3cb28c3 包未安装；随 bd50b19 原镜像已验证普通 shell dump、UID 0 设置／拒绝越界／重启生效／复位，普通 shell 设置被拒绝。

媒体实际调用者为 `vpud_native` 域 `v3avpud`，零时长请求 `0x0240c000=100` 和私有 `0x01468000=0` 均明确不支持。2cca323 的 3 秒 MTK AVC 编码与 41 帧硬件解码/EOS 能在自动重试后完成，但首次组件创建发生 SIGSEGV，不能据此认定 Codec2 稳定性通过。匹配 `libcodec2_aidl` 哈希、LLDB 崩溃位置和 DWARF 证明原厂入口少分配 16 字节。bd50b19 的主线 AIDL 入口按当前 352 字节类型编译，继续用原厂 codec store／库，Android 编译通过，bd50b19 已独立通过 3 次冷服务启动和总计 11 轮编解码，相关 PID 稳定无崩溃；其余媒体场景仍单列。

bd50b19 的 75 项主线 Python 测试通过；2cca323 无 archive 导出 75 项与 IMS pin 核验、Mac／Linux／两种 Android ABI 的 27+32 项分别保留版本。LAUNCH／INTERACTION 额外 uclamp 默认均为 0，已有下文同机无外部电源的可比温度／设置对照，但未证明可靠、可重复收益。不能把资源探针通过当作策略有收益。

## IMS 初始化缺口

97969dc 现场完整属性快照缺少 `persist.vendor.ims_support`、`persist.vendor.volte_support` 和 `ro.vendor.md_auto_setup_ims`，仅保留 `persist.vendor.mims_support=2`。固定 APK 的 `ImsApp.onCreate()` 在 ims_support 不是 1 时直接返回；`MtkMmTelFeature` 随后以 3 次、每次 5 秒等待获取未创建的后端。现场实际绑定、长时间 Binder 等待和 UNAVAILABLE 与这条路径吻合。3ee80e9 按匹配 Global 底包恢复这三个启动配置，包检查同时验证最终 vendor/build.prop 与属性标签；不设置每张 SIM 的启用位，不添加全局运营商开通覆盖。

此修复已在 2cca323 原镜像正常启动及 Recovery 往返后独立观测到：三项属性为 1、后端存在、双槽 MMTEL READY。注册与 Voice/Video/UT/SMS 能力仍未就绪。第二槽仍为漫游 eSIM，有效 carrier config 已应用而 VoLTE=false；语音套餐未知，不能直接把问题归给运营商。现有许可不包含真实通话或短信，未更改 SIM 配置。

构建工具在重写可变 OTA 前拆开历史日期文件的硬链接，避免下一次构建覆盖上一份证据。新增回归测试实际覆写可变路径后检查历史文件内容不变。

## 本轮实机依据

[只读基线记录](../validation/device-baseline-20260920.json) 属于手机原有系统：6.6.118、B 槽、Enforcing、已完成启动并运行约 70 小时，非本轮候选验收。91% 时 charge_counter=4515，而 charge_full=4962300、设计容量=5000000；Android 错将 4515 作为 µAh 上报。这是引入确定性单位适配的依据。刷新率由屏幕报告 60/90/120 Hz。shell 无权读取 persist/相机目录，未更改设备权限。

9 月 20 日首次候选保数据 OTA 后，A 槽正常启动，Health 已将内核 4952 mAh 正确换算为 Android 的 4952000 µAh，ARM64 / ARM 振动契约测试各通过 4 项。漫游 eSIM 可注册 LTE，但系统没有 IMS feature，标准框架因而未初始化 IMS；已经存在 APK 和 overlay 并不足以提供该功能。详见 [实机记录](../validation/device-acceptance-20260920.json)。

97969dc 的 Recovery status 0、安装器及独立 B 槽 14 项回读已齐备，只作为历史版本。c36757a 的标准安装和 A 槽回读通过，原始启动失败、临时 DAC 诊断条件单独保留。2cca323 标准保数据 OTA 到 B 以 kSuccess(0) 结束，安装器与独立 B 槽各 14 项匹配，原镜像两次稳定启动及 Recovery 自动 ADB 往返通过。Recovery Enforcing、Health 域正确，但未完整测试 Recovery 电量功能或侧载峰值。data/persist 和内部 canary 通过；用户 0 仍 RUNNING_LOCKED，共享存储 canary 待首次解锁，不能记作丢失。

2cca323 运行中 IMS 已独立验证初始化和 Recovery 往返恢复，尚未注册；CLI 读取所用卡的有效配置 carrier_config_applied=true、carrier_volte_available=false，未混用框架默认值。Wi-Fi 新扫描未见保存的测试热点，关联／联网与网络 ADB 未完成。首次解锁、热点和语音套餐条件已询问，不重复索取。原始无线和调试日志留在私有目录，Git 只记录脱敏结论；本次设备测试程序、LLDB server、自建片段／dex 和端口转发已清理。详见 [本轮汇总证据](../validation/mainline-convergence-20260920.json)。


## bd50b19 当前独立验收

上述 2cca323 段落保留历史边界。bd50b19 已于 09:25 完成 A 槽保数据 OTA，安装器与独立 14 项读回均匹配；正常／Recovery 往返后稳定启动、Enforcing、data/persist、snapshot none、两份 canary 全部通过。Power 的两 ABI 27+32、C ABI 生命周期、所有者退出、HAL 重启隔离、短时硬件节点及 root 策略设置／复位已在此次原镜像上重做；相关 AVC 为 0。Codec2 的 5 轮初始探针加 3 次冷启动各 2 轮均成功且服务 PID 稳定。

IMS 初始化／恢复通过，注册与 Voice/Video/UT/SMS 仍为 false，实际 carrier VoLTE=false。Wi-Fi 已获得 DHCP 并通过 HTTPS，保存配置的无互联网禁用状态导致一次重连需显式选择，下一次自动恢复；Mac ADB server 重启后已用鉴权网络 ADB 操作同一手机。首次解锁和保留文件不再是当前阻塞；性能、TEE／显示、基础 SystemUI、Recovery 缓存主机测试及实际 conntrack 解析器已补测，详情见下文与聚合 JSON；其余界面／硬件仍单列。

## bd50b19 定向补验与性能决定

测试代码提交 `3dcd922` 不改变 ROM。手机无外部电源、温控状态 0、省电关闭、窗口亮度 0.35、相同初始 120 Hz；策略 0／20 按 AB／BA 交替。12 组启动中一组温差 1°C 超过 0.5°C 协议阈值，被排除；其余 11 组进程冷启动平均 258.3→252.5 ms，配对差值 −5.73 ms，探索性 95% 区间 [−11.64,+1.55] ms。4 组各 60 秒滚动的每次 p95 平均 7.45→7.95 ms；电池侧电流×电压估算 2.718→2.691 W，差值 −0.0266 W，区间 [−0.0965,+0.0433] W。所有差值区间跨 0，未证明额外 boost 有可重复收益，默认 LAUNCH／INTERACTION 保持 0／0。

这是单个合成应用、小样本对照；文件缓存未清，实际滑动 105–110 次／轮，网络输入开销并非严格相同工作量。电流估算不是外接功耗仪；charge_counter 更新粗糙且滞后，未用它声称精细功耗精度。帧时间不等于完整触摸到显示延迟，不把数千帧当数千个独立样本，也不推导长期续航或所有应用等价。启动投票及 LAUNCH=0 时的独立交互投票均实读达到 20 后归零；最后经同一 HAL 入口恢复 0／0，活动请求 0。

普通应用测试了 TEE EC-256／RSA-2048 签名及篡改拒绝、AES-256-GCM 加解密及坏标签拒绝，三把自建密钥均清理；未读取或导出用户密钥，当时未验证硬件证明；本轮设备属性证明 -66 失败及修复输入另见下文。60／90／120 Hz 窗口模式实际接受，横竖屏既有状态图标与 20dp 边距已查看；本轮补验多图标溢出／RTL 后发现横屏非对称边距，修复仍待新候选。

Recovery 主机探针链接实际合并的 fuse_sideload.cpp：读取 1,174,891,230 字节合成文件，缓存峰值 32 MiB、进程 RSS 38,648 KiB，淘汰重读成功；篡改返回 EIO；单次分配失败后降级到 2 MiB，三轮无遗留分配／挂载。这是 Linux glibc FUSE 证据，不是手机 Android Scudo 或真实侧载峰值。安装中的 TetheringNext 类加载来源已核验，真实 TCP 解析器到事件传递的 13 项状态／非法输入通过；未写 BPF，真实双向规则删除和热点未测。

两款自建探针 APK 和专属目录内 8 个文件已清理，临时 adb root 恢复 UID 2000 且鉴权网络 ADB 实测保持，用户请求的 Key Attestation 1.8.4 保留。11:06 经网络 ADB 再验解锁状态、两份 canary 和策略复位；用户正在使用该应用，DeviceDiagnostics／OpenEUICC 界面验收待设备空闲时继续，未把注册服务或包存在记作界面通过。

## 9 月 21 日非 IMS 后续修复

本轮实机仍为 bd50b19，源码改动待新候选验收：Wi-Fi 用 GoldNetworkStackOverlay 保留 Google HTTPS 并增加实测 TLS/204 成功的 gstatic 地址；OpenEUICC 把系统管理 action 接到受 BIND_EUICC_SERVICE 保护的配置列表，缺 launcher 时不注册动态快捷方式；SystemUI 只对真正与状态栏区域相交的挖孔及相机保护区留边，避免横屏中心挖孔引入多余单侧空白。原代码在同一用例失败，修改后的实际纯 Kotlin 函数 40 项通过；主机 Rect 类型替身不冒充 Android 界面验收。

KeyMint 的 -66 目前仅证实为设备属性证明失败。重新从锁定 Global OTA 提取 vendor，SHA-256 与 firmware/gold-global.json 相符，实际 build.prop 的 product/model 为 vnd_gold/gold；只用 PRODUCT_NAME_FOR_ATTESTATION／PRODUCT_MODEL_FOR_ATTESTATION 提供这些原值，不改变显示型号、TEE 安全级别或 orange 引导状态，不导入 keybox。是否解决真实 TEE 拒绝必须安装后重测。

双击唤醒的 Lineage 设置和 Power AIDL DOUBLE_TAP_TO_WAKE 原本未在 Gold 接通。匹配内核模块反汇编及 Xiaomi gold-s-oss 原始接口确认 /dev/xiaomi-touch 的 SET_CUR_VALUE payload 是 256 个 int32、[mode, value]，没有 touch-id 前缀；mode 14 只更新双击位，保留 AOD 位。临时 root 探针成功进入手势模式并观察到两组触摸 KEY_POWER、gesture ID 0x24，用户确认两次亮屏，之后恢复 Off。主线用实际 ioctl 返回值和内核回传错误，不空报成功；只给 Power 域特定设备类型和 0x5400 ioctl，保留 DAC 与 Enforcing。9 项协议／错误测试通过，正式系统开关、HAL 权限及重启后状态待安装验证。当前硬件证据来自 FT3683G，其他面板不冒充已测。

Recovery 真实签名侧载使用无 payload／updater 的专用 fixture，完整验签后在产品名检查明确拒绝，未安装 ROM；32 MiB 缓存，minadbd HWM 43,436 KiB、Recovery HWM 99,284 KiB，返回正常系统、两份 canary 和原槽位／版本保持。未见 Scudo abort，不等于做过设备分配失败注入。USB NCM 的真连接状态已从 ESTABLISHED 变为 TIME_WAIT；Wi-Fi 上行未建 IPv4 BPF 规则，用户拒绝开启移动数据，所以双向规则回收仍缺允许的 raw-IP 条件。用户确认相机、麦克风、扬声器和震动实际体验正常。完整脱敏结果见 mainline-convergence validation 的 non_ims_followup_20260921。
