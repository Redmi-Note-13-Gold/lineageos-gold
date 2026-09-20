# 当前适配状态

更新于 2026-09-20。主线为 Global OS3.0.5.0.VNQMIXM / 6.6.118 / LineageOS 23.2，开发目标 `lineage_gold-bp4a-userdebug`。

## 本轮源码候选

已修改：补齐 32 位 mapper 的五个厂商库及对应 AIDL 依赖修正；恢复原厂功耗统计资源并纠正大核字段名；启用按实际屏幕模式生成的刷新率选择；补齐显示轮廓；按当前内核实际单位修复电量计数器；撤下未有效调校的持续性能能力声明；修复振动 HAL 虚报能力和文件描述符泄漏；收窄相机数据/标定目录权限；清理重复及无读取方的属性；将实际编译树中的 Betterr 设置条目纳入恢复补丁。

| 验证层次 | 当前结论 |
|---|---|
| 主机工具 | 26 项 Python 测试通过；原生 arm64 C++ 和本轮生成的 Linux x86_64 Health 测试均通过 8 个电量单位/边界用例 |
| 本轮 Android 构建 | 源码 `4cdee4a` 完整构建成功；target-files、AVB、VINTF、OTA/payload 签名及 Gold 包内容检查通过 |
| 振动契约测试 | ARM64 / ARM 测试程序已编译，未在手机执行 |
| 本轮安装、分区回读、开机 | 尚未执行 |
| 本轮硬件 | 本轮候选未安装；已读取现有系统基线，见下文 |

具体采用与暂缓理由见 [ADAPTATION](ADAPTATION.md)。新增振动契约测试需要 Android 目标构建和运行，不把编译测试程序计作测试通过。

## 9 月 20 日候选产物

科研机在 13:21:39（UTC+8）完成构建及自动验证，Android 构建耗时 2:56:08。复用原 `out-gold-standard`，未 clean 或创建另一完整输出。最终证据见 [final-build-20260920.json](../validation/final-build-20260920.json)。

产物根目录为 `/srv/build/migration/gold-architecture-20260914/source/out-gold-standard/target/product/gold/`：

| 产物 | 相对路径 | 字节数 |
|---|---|---|
| 完整 OTA | `lineage-23.2-20260920-UNOFFICIAL-gold.zip` | 1174542977 |
| target-files | `obj/PACKAGING/target_files_intermediates/lineage_gold-target_files.zip` | 2903486079 |

SHA-256 见 [校验清单](../validation/final-build-20260920-SHA256SUMS)。已再次确认 9 月 19 日 OTA 哈希不变，且与本轮可变 OTA 文件分离。

五个 ARM 图形库及 graphics-common V7 依赖、Gold Health 正常/Recovery 服务、标签与各自唯一的 VINTF 声明、正常系统唯一 charger、Settings 维护者资源和刷新率 overlay、38 项功耗配置均已核验。`tools/check-gold-package.py` 可复查这些包内容。

这是 **userdebug / test-keys** 候选，签名完整性通过不等于正式发行密钥验收。包内策略的 permissive 域为上游调试域 `su`、`osi`、`backuptool`；没有把新 Health/Vibrator 域设为 permissive，也未关闭全局 SELinux。VINTF 详细检查返回 `COMPATIBLE`，保留了路径回退、空 boot ramdisk及 kernel level 提示的原始日志，详见验证记录。

构建期间的四项 VM 临时参数已经自动恢复并与实时值核对：swappiness=0、zswap=N、zpool=zbud、shrinker_enabled=Y。既有 swap 文件保留。本轮未安装候选，不将原手机系统的运行状态计入新包验收。

## 本轮读取的原有系统

[9 月 20 日只读基线](../validation/device-baseline-20260920.json)：设备已连接，内核 6.6.118，B 槽，boot_completed=1，Enforcing，加密 data，连续运行约 70 小时。确认电量计数单位错误、屏幕 60/90/120 Hz 及四个相机枚举。没有 adb root、重启、安装或刷写；受 shell 权限限制，未验证 persist 与相机目录 DAC。

## 可追溯的已有结果

- 9 月 19 日科研机日志确实以 `build completed successfully (13:38)` 结束，产物为 `lineage-23.2-20260919-UNOFFICIAL-gold.zip`。它早于本轮修改；包内容的重新核查记录见 [final-build-20260919.json](../validation/final-build-20260919.json)。
- 9 月 16 日已有最终增量镜像的 [设备记录](../validation/device-fixes-20260916.json)：记录包含 B 槽 14 项回读一致、短时正常开机、加密 data/persist 正常和 Enforcing。这是历史记录，本轮没有重现实机检查。
- 该记录只证明服务就绪和有限日志窗口；没有完成相机拍照、指纹录入、Wi-Fi 联网、蓝牙音频、通话/蜂窝数据和长时稳定性测试。
- 关机充电图案曾由用户在包含相同永久修复的诊断版确认；最终清理版的完整插电循环及熄屏唤醒仍需测试。

## 尚需完成

完成新完整包及安装验证后，依次验收相机、指纹、双卡与 IMS、Wi-Fi/热点、蓝牙音频、GNSS、传感器、振动、USB、关机充电和温控功耗。再验证同基线保数据 OTA、Virtual A/B 合并和回退。

当前 Power HAL 缺少 launch/interaction 动作，不能宣称 v1 boost 已完整继承。Health 单位问题已有实机证据并已修源码，但新 HAL 的安装后验收与持续性能调校仍未完成，详见 ADAPTATION。

IMS 仍依赖指定哈希的兼容 APK，从原厂 APK 独立重建完整依赖的流程尚未闭合。未用关闭 SELinux、跳过 neverallow、伪造硬件能力或强行声明 MDDP WH 支持来代替验证。
