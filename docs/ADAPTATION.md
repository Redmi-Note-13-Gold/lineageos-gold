# 适配来源与取舍

审查基线：主线 `95f8b0b` 加科研机记录提交 `bc8f315`；参考树固定到 Dhterech `3dce0bbc357c63b28008e329593a412587618edc`。v1 对照重构前 `e14a7fa` 和 `archive/hybrid/`。迁移报告只用于寻找材料；下面的取舍依据实际源码、构建输入、接口实现与已保留证据。

## v1 功能

| 内容 | 当前处理 |
|---|---|
| Recovery 侧载缓存上限 | 保留源码补丁；科研机对应文件可反向应用该补丁 |
| SystemUI 图标打包、20dp inset | 保留平台补丁和 GoldStatusBarOverlay；不将旧设备验证算作本轮通过 |
| TCP conntrack/BPF 回收 | 保留实现与上游基线测试差异 |
| 电池信息有效值校验 | 保留 DeviceDiagnostics 补丁 |
| OpenEUICC 物理槽位与设置入口 | 保留两处补丁和固定子模块；不伪造 SIM 本机号码 |
| v1 power boost restorecon | 标签修复仍在，但当前使用 Pixel libperfmgr + MTK stub，不能据此认定旧原厂 boost 行为仍在；见下文缺口 |
| thermal 缺失节点诊断 | 保留诊断补丁，错误节点与真正热控制分开处理 |
| IMS | 保留兼容 APK、权限与限定运营商的 overlay；重建限制见 BUILD |
| 混合镜像 property contexts 修补 | 标准源码策略负责生成最终属性标签；不再修改成品 CIL |
| 混合镜像 zygote 闭包、system 模块链接 | 检查标准 target-files 的 rc 和 `/system/lib/modules` 链接；不用旧脚本二次加工 |
| 旧 CIL neverallow/属性归属改写 | 仅留作历史参考，不导入当前标准源码策略 |
| MDDP 实验模块 | 不导入。旧证据的 modem 能力缺少 WH 位，节点权限不能创造能力 |

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
| `204c251` ADB 鉴权 | 主线未配置 WITH_ADB_INSECURE，无需新补丁；历史实机 debug Recovery 与正式产物分开记录 |
| `b1790f9` mmstat 调试删除 | 主线已经没有该 tracing 配置；其 modem 目录删除没有适配证据，不跟随扩大清理 |
| `19a71ff`/`85ca188` Health HAL | 采用独立 Health wrapper；依据当前 6.6.118 实机证据将 charge_counter 从 mAh 转成 µAh，同时覆盖单项查询和 HealthInfo 更新。电流、满充容量保持原有微单位，拒绝负值与整数溢出。不合并按 SOC/数值大小猜测单位的逻辑 |
| `1d8d063` 关机充电 | 主线已有驱动就绪、DRM 等待和显式启动顺序；不叠加另一套 charger 服务 |
| `7b66ebb` 性能 hint/定时数值 | 不导入任意 hint 数值。实机小核最高 2 GHz，原有持续性能动作也写 2 GHz；框架不再宣称支持已调校的持续性能模式。启动/交互 boost 仍待实现和测量 |
| AOD、相机 UW/macro SKU overlay | 当前 gold_cn 枚举四个相机 ID，但未证明 UW/macro 角色；仍需焦距/镜头、实际拍照及 doze/亮度/唤醒验证 |
| `3d3bf28` 额外 SELinux 规则 | 不整批复制。匹配当前域、对象和实际拒绝后才增加最小规则；保持 neverallow 检查 |
| GS101 memtrack | 未证实当前 GPU 内核接口与实现匹配，不盲换服务 |

## 自有代码修正

振动 HAL 原先声明六种预设效果并设置 `CAP_PERFORM_CALLBACK`，但 `perform()` 永远失败；`on()` 又另起无取消控制的计时线程。现在只报告实际的定时 on/off 能力，框架使用效果 fallback；无支持的 callback 和非法时长在访问驱动前返回明确错误。移除构造函数中无用途的未关闭 fd，sysfs 写入不再包含 NUL。

相机服务实际以 `cameraserver` 运行且属于 `camera` 组。运行目录归属该服务，标定目录保留 system/camera，移除通用 0777/0666 权限和对只读 `/vendor` 的无效 chmod；不改写标定数据。保持原有 SELinux 域与相机标签。

原来只存在于科研机的 Betterr 设置条目现在进入 `patches/series.json`。科研机用于 Soong 的内存环境转发保存于 `tools/host/soong-memory-env.patch`，属于可选宿主补丁，不影响手机运行行为。

## 电源接口缺口

实际源码的 Pixel libperfmgr 依赖 powerhint.json；原配置只有小核最高频率的 SUSTAINED_PERFORMANCE 动作，没有 LAUNCH/INTERACTION。MTK perf stub 的锁接口仅返回句柄/常数，libmtkperf_client_vendor 也是空实现，不会转交原厂调频请求。因此旧 restorecon 规则只能修标签，不能证明 boost 已保留。实机确认小核正常最高频率就是 2 GHz，原配置不能作为持续性能控制的证据，已关闭框架对此能力的声明。启动/交互 boost 仍不能列为已完成优化；需结合原厂 hint 语义与温控约束实现和测量。

构建工具在重写可变 OTA 前拆开历史日期文件的硬链接，避免下一次构建覆盖上一份证据。新增回归测试实际覆写可变路径后检查历史文件内容不变。

## 本轮实机依据

[只读基线记录](../validation/device-baseline-20260920.json) 属于手机原有系统：6.6.118、B 槽、Enforcing、已完成启动并运行约 70 小时，非本轮候选验收。91% 时 charge_counter=4515，而 charge_full=4962300、设计容量=5000000；Android 错将 4515 作为 µAh 上报。这是引入确定性单位适配的依据。刷新率由屏幕报告 60/90/120 Hz。shell 无权读取 persist/相机目录，未更改设备权限。

9 月 20 日首次候选保数据 OTA 后，A 槽正常启动，Health 已将内核 4952 mAh 正确换算为 Android 的 4952000 µAh，ARM64 / ARM 振动契约测试各通过 4 项。漫游 eSIM 可注册 LTE，但系统没有 IMS feature，标准框架因而未初始化 IMS；已经存在 APK 和 overlay 并不足以提供该功能。详见 [实机记录](../validation/device-acceptance-20260920.json)。
