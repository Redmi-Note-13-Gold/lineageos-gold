# CN R1 历史功能与验收状态

状态更新于 2026-09-14。**手机已从完整 R1 OTA 安装并启动 LineageOS 23.2-20260913 / OS3.0.10，运行于 B 槽、SELinux Enforcing。** Recovery 最终日志 status 0，B 槽启动链回读匹配。安装后再次进入 Recovery、完整硬件与长期稳定性仍待验收；下方旧基线功能记录不自动视为新基线通过。见 [FULL_BUILD.md](FULL_BUILD.md) 和 [测试版安装说明](INSTALL_TEST.md)。

## 新底包首次运行

- 初始化完成，首轮未见 crash、tombstone 或 ANR。
- 图形帧积压复现，伴随 HWC buffer-recorder 报错；仍未解决。
- 热点驱动有认证发送完成超时和 MDDP 状态错误；硬件加速未验收。
- Power HAL 可见 LAUNCH 请求及释放，观察片段未见对应权限错误；性能、温控尚未验收。

## 旧底包上已部署的修复与配置

| 项目 | 当前实现与证据 | 验收边界 |
|---|---|---|
| 状态栏统一 20dp | 设备 overlay 已部署 | 与溢出布局分别记录 |
| 状态栏图标溢出 | 23.2 独立实现；实际部署 R2，修正无 ID 的 DemoStatusIcons 预算；SystemUI 哈希及分区回读匹配 | 841203 组算法检查及 Java 编译通过；新增 Android View 测试未运行，拥挤/RTL 全场景验收未完成 |
| 热点 TCP/BPF 回收 | 解析真实 TCP 状态并回收 flow；3 个实现文件和 3 个测试文件；已编译刷入 | 长时间、多客户端、移动网络切换和息屏场景仍需覆盖 |
| IMS / VoLTE 集成 | v5 广播 export/视频 guard、权限、overlay，加上 23.2 TelephonyMetrics 兼容层；已部署并观察到 IMS 注册与 voice/SMS/UT 能力 | 注册和能力标记不替代全部通话/SMS/双卡场景测试；不保证所有运营商 |
| OpenEUICC / eSIM 集成 | 槽位处理、JNI/原生入口、权限与产品注册已迁入 | 本机号码为空是独立问题，见下表；不能保证所有 eUICC 卡片 |
| DeviceDiagnostics 电池信息 | 23.2 编译，通过应用更新安装 | 与 Settings 的电池日期选项不同；底层未提供的元数据不会凭空出现 |
| Power HAL boost 权限 | R3 已刷入、回读、Enforcing 冷启动；实际 HAL 的 boost:1 写入 44 字节、boost:0 写入 7 字节均成功；观察窗口内对应权限错误为 0 | 权限与请求写入/复位验收通过，未完成持续负载温控或性能收益评测 |
| MDDP 设备节点权限 | hybrid vendor 配置 `/dev/mddp 0640 system system`，HAL 可以打开设备 | 仅解除访问阻塞，WH 硬件加速仍不工作 |
| 混合启动修复 | 重复 property contexts、双 zygote、6.6 模块路径、KeyMint 策略等已用于现有系统 | 尚未统一接入普通整包构建；部分 hybrid 策略已有 27 项严格 neverallow 冲突，不是严格策略/CTS 通过声明 |

## 未解决、实验或不适用

| 项目 | 已知事实 | 后续工作 |
|---|---|---|
| MDDP WH 硬件加速 | 基带报告能力 `0x00000003`，缺少 WH 位 `0x4`；权限修复后仍阻塞 | 公共源码重建候选仅编译/离线验证，默认关闭，未加载/刷入；需真实 modem 握手、转发、统计和稳定性验证 |
| eSIM 本机号码 | 两条 EF_MSISDN 成功读取但内容为空；UICC/运营商/IMS 号码源也为空 | 未找到可恢复号码，不伪造本机号码；不代表运营商未分配号码 |
| 图形帧积压 | 仍有待定位现象 | 尚无已验收专用修复 |
| Recovery USB 偶发未授权 | 多次刷机验证曾需重新插拔/授权 | 尚无已验收专用修复 |
| 全新源码整包恢复 | 有当前改动，但独立依赖与混合镜像流程尚未完全统一 | 补齐干净机器端到端构建和 OTA 验证 |
| Settings 电池日期 | 当前 23.2 基线默认隐藏两个日期字段，避免无效日期显示 | 23.0 的“有效日期才显示”属于可选定制，未移植，不列作故障 |

[`experimental` 分支](https://github.com/Redmi-Note-13-Gold/lineageos-gold/tree/experimental)内容不代表 main、默认启用或已部署。旧候选和旧说明中的状态不能覆盖本表所列后续验证记录。
