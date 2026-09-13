# Redmi Note 13 5G（gold）LineageOS 23.2 测试版

版本：23.2-20260913-UNOFFICIAL-gold / Recovery R1  
Android 16；官方底包 OS3.0.10.0.VNQCNXM；官方内核 6.6.89。  
测试记录更新于 2026-09-14。本项目是非官方适配，与 LineageOS 官方无隶属关系。

## 安装前必读

- 仅用于设备代号 **gold**。本次实测型号为 **2312DRAABG**；其他代号不可刷，即使商品名称相似。其他地区型号尚未逐一验证。
- 这是供反馈问题的测试版，尚未完成全部硬件与长期稳定性验收。
- 本文是**全新安装**流程，会清除应用、账号及内部存储文件。先备份照片、文件、验证器和其他重要数据；不要把手机内部存储作为唯一备份。
- 需要已解锁 Bootloader、可用 USB 数据线和 Android SDK Platform-Tools。电脑连接独立网络，不依赖被刷手机的热点。全新刷机前建议电量至少 50%。
- 使用公开开发测试密钥，**安装后不要锁回 Bootloader**。不要混用其他版本 boot、vendor_boot、DTBO、LK 或 vbmeta。
- 本包包含当前组合所需的官方固件分区；本次测试从旧 LineageOS 23.2 / OS3.0.9 混合环境开始，不等于已经验证从全套原厂 HyperOS 或任意旧固件直接安装。

## 文件

- `rom/`：通过 Recovery 的 ADB sideload 安装的完整 ROM ZIP，保持 ZIP 原样，不要解压刷入。
- `rec/`：配套 Recovery 启动链：`lk.img`、`boot.img`、`dtbo.img`、`vendor_boot.img`、`vbmeta.img`。Recovery 位于 vendor_boot，**没有独立的 recovery.img，也不要使用 fastboot flash recovery**。
- `rec/super_empty.img`：用于修复本次遇到的旧动态分区布局冲突；不是 ROM，仅在下文对应情形使用。
- `SHA256SUMS`：以上文件与本 README 的 SHA-256 校验清单。

ROM SHA-256：

```text
cf04a5d81fb6b897165978f0b0982fd67ec0128585fdc234d8f5cef4b3a20a74
```

在本文件夹中打开终端执行下列命令。Windows PowerShell 如需调用当前目录的工具，请将 `adb` / `fastboot` 写为 `.\adb.exe` / `.\fastboot.exe`，或先把 Platform-Tools 加入 PATH。

macOS 校验全部文件：`shasum -a 256 -c SHA256SUMS`；Linux：`sha256sum -c SHA256SUMS`。Windows 可用 `Get-FileHash -Algorithm SHA256` 校验各文件并对照清单。校验不符时重新取得文件，不要继续刷入。

## 1. 刷入配套 Recovery

关机后按住音量下和电源进入 Bootloader Fastboot，也可在已开启且授权 USB 调试的 Android 中运行：

```sh
adb reboot bootloader
```

确认只连接一台待刷手机，并检查：

```sh
fastboot devices
fastboot getvar product
fastboot getvar unlocked
fastboot getvar current-slot
fastboot getvar is-userspace
```

应为 `product: gold`、`unlocked: yes`、槽位 `a` 或 `b`、`is-userspace: no`。身份不符、未解锁或命令失败时停下。下列不带槽位后缀的 flash 命令使用 Fastboot 默认的**当前活动槽位**；不要额外切换槽位或加 `--slot=all`。

```sh
fastboot flash lk rec/lk.img
fastboot flash boot rec/boot.img
fastboot flash dtbo rec/dtbo.img
fastboot flash vendor_boot rec/vendor_boot.img
fastboot flash vbmeta rec/vbmeta.img
fastboot reboot recovery
```

逐条检查 OKAY；任意一步失败，不要接着启动 Android，保留错误信息反馈。本次实际是在 A 槽完成这五个镜像刷入，并逐个回读校验成功。

## 2. 清除数据并安装 ROM

在 Lineage Recovery 中：

1. 选择 **Factory reset → Format data/factory reset**，确认清除；等待 `Data wipe complete`。
2. 返回主菜单，选择 **Apply update → Apply from ADB**。
3. 电脑执行：

```sh
adb devices
adb sideload rom/lineage-23.2-20260913-UNOFFICIAL-gold-OS3.0.10.0-recovery-r1.zip
```

设备应显示 `sideload`。安装时保持 USB 连接，不重启手机或 ADB 服务。本次完整安装约 10 分 36 秒，实际时间会变化；电脑端百分比和传输结束不能单独证明成功，**以手机 Recovery 的最终成功提示为准**。若出现签名、分区或安装错误，保留完整信息，不要盲目忽略。

若 Recovery 连接显示 `unauthorized`，先退出到 Recovery 主菜单，检查 Advanced 中的 Enable ADB（若有），重新插拔 USB，再进入 Apply from ADB。本次曾出现这个问题，尚无专门修复。

## 3. 仅当遇到旧布局重名错误

本次第一次安装返回 status 7，日志明确包含 `Attempting to create duplication partition with name: system_b`。原因是旧手工刷机留下的动态分区分组和历史 COW 项；**status 7 也可能有其他原因，不要只凭错误码执行本节**。

确认属于上述旧布局问题且已备份、接受全新安装后，在 Recovery 的 Advanced 菜单选择 Reboot to bootloader，进入 Bootloader Fastboot，再执行：

```sh
fastboot wipe-super rec/super_empty.img
fastboot reboot recovery
```

这会清除 super 内 **A/B 两槽旧系统逻辑分区**；执行后没有旧系统可直接启动，必须完成后续 ROM 安装。它不是保留数据升级步骤，不替代第 2 节的 data 格式化。

回到 Recovery 的 Apply update → Apply from ADB，重新执行第 2 节的同一条 sideload 命令。若先前 data 格式化已成功，无需重复格式化。本次使用本文件夹中的 super_empty.img 后，第二次安装和首次启动成功。其他类型的安装失败请反馈，不要反复清除或混刷镜像。

## 4. 首次启动

手机 Recovery 明确报告安装完成后，选择 **Reboot system now**，等待初始设置出现。若返回 Recovery、进入 Fastboot 或长时间无法进入初始设置，请保留画面/错误信息反馈，不要锁 Bootloader。

完成初始设置。需要抓日志时重新开启开发者选项和 USB 调试并授权电脑；格式化后原调试授权已丢失。正常使用无需开启 root。

本次安装从 A 槽写入 B 槽，首次开机确认：23.2-20260913、OS3.0.10、6.6.89 内核、SELinux Enforcing，初始化完成。安装后 B 槽五个启动链镜像回读均与本包匹配；再次进入 Recovery 尚未实测，保留本文件夹的配套镜像作为恢复输入。

## 已验证与已知问题

| 项目 | 本轮结果 |
|---|---|
| 配套 Recovery 启动、ADB、格式化 data | 通过 |
| 完整 ROM 安装 | 重置旧 super 布局后通过；Recovery 日志 status 0，payload 写入、文件系统校验和 postinstall 均成功 |
| 首次 Android 启动与初始化 | 通过；B 槽、版本和官方底包匹配 |
| 崩溃 / ANR | 首次抓取中无 Java/native crash、无 tombstone、无 ANR；不代表长期稳定性结论 |
| 图形帧积压 | **仍存在**：抓取窗口内 398 条 SurfaceFlinger pending-frame 报错，伴随 HWC buffer-recorder 报错；根因和影响仍待定位 |
| 热点 | 已观察到热点开启，但驱动有认证发送完成超时和 MDDP 状态错误；硬件 offload 统计为 0，当时无已连接客户端，不能据此断言转发失败；多客户端和硬件加速未验收 |
| Power HAL | 观察到 LAUNCH 加速请求及释放，当前日志未见对应权限错误；不代表新底包性能、温控验收完成 |
| IMS / VoLTE、eSIM | 已有适配包含在工程中；新底包通话、短信、双卡和各 eUICC 场景未重新全面验收；历史本机号码为空问题没有已验收修复 |
| 其他日志 | 有音频时间戳读取失败、IMS 网络定位 provider 未就绪等；实际影响仍需复测，不等于已证明音频或通话不可用 |
| SELinux / 发布状态 | 系统 Enforcing；构建严格 neverallow 检查仍有既有 27 项失败，不是 CTS 或正式发行验收通过 |
| 安装后再次进入 Recovery、保留数据升级、长期使用 | 未完成验收 |

本版未验证额外 Google 服务包、Root 模块和第三方内核组合，先按原包测试。反馈时说明设备代号、原系统/固件、操作步骤、发生时间、能否复现；公开日志前去掉手机号、SIM 标识、账号、序列号及网络隐私信息。

源码、补丁与后续进度：[Redmi-Note-13-Gold/lineageos-gold](https://github.com/Redmi-Note-13-Gold/lineageos-gold)。本文件是此测试版的状态快照，后续修复不自动适用于已经下载的 ZIP。
