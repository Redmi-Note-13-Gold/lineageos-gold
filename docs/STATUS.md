更新于 2026-09-30 06:21（UTC+8）：当前安装源码 `52e9435`，A 槽 / incremental `1790709272`。完整构建、保数据安装、启动与静默检查通过；全机硬件验收尚未完成。下文旧版本记录保留其历史范围，不自动继承到新版本。

## 本轮适配与设备交付

源码提交 `48306c6`、`52e9435` 接入现有 FMRadio，补齐统一 Power HAL 的持续音频请求与独立来源释放，修正 Health 无效读取的 AIDL 状态码；Aperture 复用一个后端增加默认关闭的后摄 108MP / 前摄 16MP 捕获入口，按原厂契约将 HDR 属性设为 false，并删除未使用的 libperfmgr 配置和标签。电量单位继续按已确认的 mAh→µAh 契约转换，Codec2 保留按当前平台编译的服务入口。

科研机唯一输出完成 bacon 与 target-files 两阶段构建；签名、VINTF、SELinux、14 个 payload 分区及设备包检查通过，实际 Android 工具链的 Power/Health 测试 33/27/8 项通过。最终包冻结于 `/srv/build/gold/releases/20260930-060158-52e9435`；首轮因本任务误用沙箱只读的 `/var/tmp` 打包目录失败，改用既定 `/tmp` 后成功，没有修改源码或放宽沙箱处理此错误。

已准备并核对基线 Recovery 启动镜像及自动 ADB 配置，随后完整 OTA 单次安装返回 `kSuccess(0)`，B→A 正常重启一次。安装器与独立活动槽回读各 14 项匹配；正常启动、Enforcing、data/persist 挂载、snapshot none、DE/CE 两份 canary 一致。设备没有 `bootctl`，未宣称单独核对 bootloader 的成功槽位标记。Power/Health AIDL 注册、FMRadio/Aperture 包、五项 FM 属性和 HDR=false 实读通过；Power 后端 ready 且无错误。未打开相机、FM 播放或进行屏幕、声音、振动及外部 WPA3 客户端测试。

手机安装暂存已核验清理，ADB 恢复 UID 2000，漫游数据保持关闭。科研机 VM/needrestart 恢复，临时 zip/unzip 和 OTA scratch 已清理，历史原厂输入保留。没有公开推送或发布本候选。脱敏证据见 [本轮记录](../validation/adaptation-20260930.json)；冻结时的 `candidate.json` 保持原字节，安装结果另记。

后置人像已加入待构建实现：Aperture 复用既有相机交接与保存流程，向原厂 MiAlgo 双摄图提交逻辑 3 / 物理 0、2 的帧和 metadata，再将效果输出保存为 JPEG，默认关闭。应用移至 system_ext 使用局部平台 API，签名及非特权身份保留；专用 SELinux 域只读指定校准和模型文件。三个新增原厂库保持原字节。JNI 中一个未被 relocation 使用的旧 libgui 符号无法通过标准 ELF 检查，故仅对这个模块允许 undefined symbols，仍检查 SONAME/NEEDED；这不代表运行时 ABI 已验证。尚未进行实际加载、捕获或画质验收。

第三批 `00efd66` 的额外 DisplayServiceTests 编译失败：45 个错误均为未修改上游测试对 AutomaticBrightnessController.configure 的旧参数调用。不修补整套上游测试；保留本次 20 行 HBM 回归用例及失败记录，后续只构建主线 ROM。第三批没有合格交付包，也未安装。WPA3 关联、设备 ID attestation `-66` 及其他物理验收继续待办，不将编译或启动成功扩大为功能通过。

## GitHub 测试版发布

[Global R1 / lineage-23.2-20260929-r1](https://github.com/Redmi-Note-13-Gold/lineageos-gold/releases/tag/lineage-23.2-20260929-r1) 已公开发布为 Pre-release。发布标签固定到实际 ROM 源码 `8f01656dc34564b5157aadfc466bf0180397a461`，日期来自该 ROM 构建。8 个附件包括完整 OTA、同次 boot/dtbo/vendor_boot/vbmeta 镜像、说明、脱敏清单和 SHA256SUMS；逐项 GitHub SHA-256 与科研机文件一致，公开校验文件及 OTA 下载范围请求通过。target-files 保留在科研机，不是手机安装包。

该发布为 userdebug/test-keys 测试版，已验收和待办边界如下；公开发布不等于正式发行密钥、CTS 或全部硬件验收。未改变旧 CN R1 发布，未操作手机或 Mac 网络。

## 8f01656 历史 AOD 候选：正式低功耗路径已通过

2026-09-29 22:42:50启动，23:05:21入口exit0。bacon11:46、target-files-package07:31均成功；同次169项输入/10受管项目/1158项Repo、签名/VINTF/SELinux/UTC日期、14个payload分区与40个实际镜像文件通过。实际system_ext的GoldStatusBarOverlay含DOZE和DOZE_SUSPEND两个true；MPEG4兼容库、SAE资源、eSIM缺席门禁保留。单一OUT inode9437191未变，内核无OOM。

候选 `/srv/build/gold/releases/20260929-231337-8f01656` 已冻结同次源码/工具/输入，独立副本复验exit0；全量OTA SHA-256 `a7de60dd4e8281e7b37db3d2b28896d56609443520f71ca655c085b6fae2a4f8`，全量target-files `ee441c332f84379db0c774c908db949d58b351479097b32d003f9b78e3e11f39`。包各nlink1，转存临时目录已清理。guard23:05:25恢复，VM实读0/zbud/N/Y，临时ZIP工具、OTA scratch、needrestart精确保护全部清理，宿主ZIP工具未持久安装。历史4项OTA缺席注记保留。

用户确认手机空闲后，已通过本地与手机SHA、证书、适用性、槽位/供电/快照检查，update_engine返回kSuccess(0)，B→A正常重启一次。安装器与独立活动槽各14分区匹配；data/persist挂载、snapshot none、Enforcing通过。64.0秒观察含ADB重连，不作为纯启动时长。开机后的首次网络ADB探测未立即成功，随后重新核对身份并实际连通；未再次刷机或重启。

首次解锁后两canary均一致。直接使用新ROM永久资源，关闭AOD时实际compositor为Off、面板节点0；开启后为DozeSuspend、dozeScreenState=4、framework Dozing、面板节点16；两种状态均可程序唤醒回Awake/On。截图中时钟正常绘制，没有临时overlay或属性覆盖。物理时钟亮度及双击体验尚待用户反馈，节点16不能换算成已测功耗。

Diagnostics活动APK与既有28项验收版本一致，MPEG4库与冻结包SHA相同，未重复无影响媒体测试；用户KeyAttestation保留。原AOD设置已恢复，本次手机OTA/元数据两文件及目录经SHA核对后清理，ADB UID2000/Enforcing及鉴权网络控制已恢复。漫游数据维持关闭，本轮未操作Mac网络或钥匙串。

## 60e90a7 已验收记录

| 子项 | 60e90a7实际证据与边界 |
|---|---|
| 安装、回读与数据 | 本地/手机OTA SHA-256、信任证书和适用性通过；update_engine成功，A→B正常重启一次；安装器及独立活动槽各14分区哈希匹配。data/persist、snapshot none、解锁后两份canary一致。87.02秒观察包含ADB重连，不作为纯启动时长 |
| MPEG4真实修复 | 普通ADB UID2000、Enforcing下，c2.mtk.mpeg4编码/解码60帧及EOS通过，v3avpud/Codec2相关PID稳定；交付库SHA与冻结镜像相同。HEVC 720p/120帧往返及EOS回归通过；不扩展为全部格式或长期稳定性 |
| 应用与清理 | OTA后实际活动Diagnostics APK仍为此前28/28通过的6e64afef…；用户KeyAttestation1.8.4/code198保留。自有DEX/视频、手机OTA暂存和临时Doze覆盖/属性已清理；ADB恢复UID2000 |

冻结安装入口仍为 `/srv/build/gold/releases/20260923-090824-60e90a7`，ROM源码60e90a7；全量OTA SHA-256 `09cf910fcb992e01dd412554e19dd9d4a2b3324561145d119922d44a66da372a`，target-files SHA-256 `56e7c1114b95d8d324f69b0859e91e85ee45d3f8727d63ee2f91a61b4b8bab63`。本机只下载了OTA及元数据，未下载整份target-files。冻结candidate.json保持9月23日当时的事实，后续设备证据见 `candidate_60e90a7_device`，不改写冻结历史。

## 当前修复与边界

AOD服务绑定和时钟绘制在60e90a7生效，但SystemUI默认 `doze_display_state_supported=false`、`doze_suspend_display_state_supported=false`，把低功耗请求改成普通ON。现场普通ON时面板亮度节点为513；受控临时验证分别进入真实compositor DOZE和DOZE_SUSPEND、亮度节点16，唤醒回Awake/ON成功，随后完整撤销临时设置。屏幕物理可见性仍待用户确认，长期耗电未测，不把节点读数等同功耗。

0737d5f在现有GoldStatusBarOverlay资源中补两个开关，169项合并输入仅这一XML变化，10个受管项目提交不变。唯一OUT的定向Ninja共4项、84.59秒exit0，APK签名及两个编译布尔值通过，旧包确实缺少这两个值；21项相关主机测试通过。独立guard与对应InvocationID成功退出，VM实读0/zbud/N/Y。静态系统RRO仍需完整ROM交付，未尝试绕过PackageManager/EROFS/AVB；新包门禁同时要求两个编译值及实际system_ext中的覆盖APK，实际镜像检查增至40项。

当前限制：仅剩漫游卡，手机全局及活动订阅数据均关闭，不拨号、不收发短信、不操作SIM。用户已允许本次正常安装重启，但明确禁止后续操作Mac网络和钥匙串；WPA3 Mac联测停止。此前Mac重连预检造成网络中断，读取密码尝试失败、未保存密码，相关临时工具已删除；未开始手机本地热点测试，不归因ROM认证失败。优先已核对身份的鉴权网络ADB，原始日志只留本机0600私有目录。

为下一轮正常增量构建，按用户既有“旧的没用的OTA可直接删”授权删除4份已被新版本取代的OTA，释放4,698,773,097字节；对应target-files、原始记录、官方输入、当前60e90a7及70c2ec4/bd50b19回退包均保留。releases/index标注缺席，清单和删除前SHA在任务记录中。

## 未完成与当前限制

| 项目 | 当前事实及下一步 |
|---|---|
| WPA3 热点 | 用户历史确认可以开启、Mac可扫描但无法连接；当前没有新修复或认证阶段证据。用户禁止操作Mac网络/钥匙串，因此停止Mac联测；后续需要独立且获准的测试客户端，不启用漫游数据 |
| 设备属性证明 | 70c2ec4普通应用无设备属性的TEE证明通过；设置安全锁屏后，包含属性仍为-66。五项当前属性分别请求、五项一起请求、正常平台五项一起请求均被拒绝；CN原厂分区检查与本地RKP诊断见keymint_followup记录。RKP签名和当前系统信息不等于工厂ID已获验证；信任根/吊销未审计。认证绑定EC/AES已移到已验收；不猜身份、不导入keybox或重置安全存储 |
| TCP/BPF | FIN回收与活动连接隔离通过，部分RST仍长驻。逐四元组CT_GET复查两条旧流仍为内核ESTABLISHED、超时约五天；撤回先前“/proc未匹配=内核已消失”的推断。新配对测试中RST先保留ESTABLISHED但超时缩至9秒，12秒查询时内核及双向规则缺席；查询可能促进过期项回收，不算无观察自然到期通过。继续查周期超时刷新与RST短超时的交互，未改生产BPF/APEX，未手动删除规则 |
| Recovery | 60e90a7及8f01656均未做Recovery往返；bd50b19缓存/RSS为独立历史证据。Scudo失败注入与完整Recovery OTA仍未测，按实际需要及稳定控制链安排，不为重复验收刷机 |
| AOD | 已发现并修复两个缺失的面板低功耗开关，临时DOZE/DOZE_SUSPEND与唤醒通过，定向APK已编译。8f01656正式OFF/DOZE_SUSPEND/程序唤醒及两canary已过；剩余物理时钟亮度与双击体验确认，长期功耗未测。截图渲染与硬件状态不代替用户物理观察；MPEG4既有短往返验收按60e90a7保留 |
| Health / 热控 / 其他硬件 | 持续负载降频与恢复、完整充电/关机充电循环、长期续航未测；蓝牙音频等依外设和已有记录选择测试 |
| 正式发行 | 已公开 Global R1 Pre-release 测试版；正式发行密钥、CTS及完整硬件验收仍未完成 |
| IMS | 按用户安排放最后，另有安排；本轮不推进，不操作 SIM、不拨号或发短信 |

2026-09-22用户明确要求“开刷”，本轮已执行保数据安装及必要正常重启；这不扩大为额外Recovery或网络切换测试。未操作SIM、拨号或短信，当时只记录旧的全局mobile_data=0，不能据此判定双卡实际数据开关；本轮按订阅与真实上行核实中国联通已开启、漫游eSIM数据关闭，原设置不变。正式双击设置仍1。手机端两份专属OTA暂存文件及其目录已清理，临时root已恢复UID2000、Enforcing。用户Key Attestation 1.8.4/code198保留，没有授予额外权限。

## 9月22日晚免重启定向结果

源码修复提交 `f6b67d4`。统一入口新增受限 `--module-apks`，复用同一OUT的已核验Ninja图、源码/输出锁及原资源限制；只允许已存在源文件或资源变化，产品/配方/文件列表变化拒绝复用。DeviceDiagnostics与FrameworkResOverlayGold共13项Ninja任务、125.73秒、exit0；签名及独立APK哈希通过，构建/guard的实际InvocationID退出均确认，VM实读0/zbud/N/Y。124项主机回归通过。不是新ROM或新冻结候选，APK工具/选定源码/169项输入记录在 `jobs/gold-mainline-20260920/focused-apks-20260922`。

**本轮已完成子项**

| 子项 | 已完成证据 |
|---|---|
| DeviceDiagnostics负循环次数 | 旧APK的28项实际Activity边界用例有3项失败；主线同时修生产者与界面过滤，新APK在线更新后28/28通过。健康值、日期、循环次数含缺失/负值/极值与Android版本差异；未注入全局BatteryService。活动APK SHA-256为6e64afef792093c6d1de5b78f67af9922a1261e82b53e20e45b2751d35a315e2，位于data应用更新；后续OTA须核对实际活动APK |
| KeyMint普通证明 | 本候选TEE级别/挑战/链内签名及真实orange引导状态如上；自建密钥已删。设备属性证明仍在未完成项中，认证绑定追加结果见下一行 |
| 认证绑定EC/AES | 用户自己设置安全锁屏并在系统窗口认证；普通应用的EC P-256与AES-256-GCM在认证前及15秒授权到期后均拒绝使用，认证后签名/加解密和篡改拒绝通过。两把KeyInfo均为TEE且认证约束由安全硬件执行；EC证明的硬件列表含认证类型/15秒期限。密钥和测试APK已清理；安全锁屏不改变bootloader的unlocked/orange事实 |
| HEVC短往返 | c2.mtk.hevc.encoder/decoder，1280×720，120帧编码、120帧解码和EOS；不扩展为长时/全格式验收 |
| 交还状态 | 未重启手机或改变热点；联通数据开启、漫游eSIM关闭且未操作。鉴权网络ADB优先，已恢复UID2000/Enforcing；两canary一致，双击1。自有探针APK、DEX、片段和临时Doze覆盖均清理，用户KeyAttestation保留 |

当时手机是70c2ec4/A/1790008554加上述DeviceDiagnostics数据分区更新。AOD静态覆盖、MPEG4插件尚未安装，TCP/BPF未修改运行中的APEX；不能把这些源码修复并入当前ROM已验收结论。原始截图/无线/设备日志仅在本机0600私有目录；Git只含脱敏结论，详见聚合validation的 `focused_followup_20260922`。

## 认证绑定与设备属性证明的后续核对

主线增加普通应用 `GoldAuthActivity` 与只生成自有密钥的 `GoldAttestationParameters`，沿用已有JDK/SDK/唯一OUT工具，单独编译测试APK/DEX；没有编译或安装新ROM，也没有更改生产KeyMint、手机属性或TEE配置。认证窗口由系统处理，探针不获取锁屏凭据。认证绑定的实际先拒绝→本人认证→成功→过期拒绝，以及EC/AES篡改拒绝均通过；不是从“已设锁”或界面成功提示推断通过。

设备属性仍失败：普通应用冷启动确认无属性成功/含属性-66；直接按五个属性拆分及组合后，所有含属性的当前值请求仍-66。当前平台属性组合也失败。固定CN输入的vendor/odm通用身份与Global一致；product仍为Xiaomi/missi/miproduct模板，仅name=gold。以上都不能当作这台设备的TEE预置身份。MiTEE二进制中的“get deviceinfo success”来自普通ro.product属性读取，不能解释为读出了工厂ID。补充的本地RKP v3空key CSR有匹配随机挑战、DICE链内签名及请求签名，修改签名被拒；只证明这条诊断路径工作，没有远程证书申请、网络上传、信任根/吊销验收或证明ID修复。

原始证书、DICE身份、设备和无线输出只保存在本机0600私有目录。服务器与Git记录脱敏结论，详见 `validation/mainline-convergence-20260920.json` 的 `keymint_followup_20260922`。本轮全程普通鉴权网络ADB UID2000，未重启手机/adbd、未改热点或数据/SIM；两canary一致，用户KeyAttestation与已修复DeviceDiagnostics保留，自己的探针APK/DEX/密钥已清理。

## 70c2ec4 本次已验收子项

| 子项 | 本候选证据与边界 |
|---|---|
| 全量OTA安装与回读 | 手机端包SHA-256、信任证书和适用性通过，标准update_engine返回kSuccess(0)及UPDATED_NEED_REBOOT；B→A保数据安装，安装器最终14分区与独立活动槽14分区SHA-256均匹配签名镜像 |
| 正常启动与数据 | A / 1790008554，正常重启一次、首次稳定观察25.40秒；Enforcing、data/persist挂载、snapshot none、两份canary一致。没有做Recovery往返或第二次重启 |
| eSIM退出支持 | 设备实际system_ext六条旧路径（包含悬空链接）均缺席，PackageManager中无OpenEUICC应用或eUICC feature；没有操作SIM |
| WPA3资源与能力 | SAE资源true、SoftAP能力127含bit4；用户在70c2ec4确认热点能启动、Mac可扫描，Mac连接仍失败，连接故障留在待办 |
| 交还状态 | OTA暂存已清理；本轮临时root检查后恢复ADB UID2000、Enforcing。因用户提示USB线缆破损，已启用并实际连接鉴权网络ADB，核对硬件身份后优先使用；端点只存私有证据。联通数据开启、漫游eSIM数据关闭，未改设置。用户KeyAttestation1.8.4/code198保留 |
| Wi-Fi自动恢复（用户验收） | 用户明确确认70c2ec4自动恢复可用；移出未完成清单。未提供本轮独立TLS/204、恢复耗时或框架VALIDATED日志，不将用户体验结论扩大为这些自动化指标 |
| TCP正常关闭及隔离 | 现有WPA2热点客户端经联通ccmni0上行，真实连接ESTABLISHED时双向各1条规则；FIN后客户端进入TIME_WAIT、双向规则清除，另一条活动连接的两条规则保持。RST细节与边界见上表和聚合证据 |

用户澄清既往低电关机是操作意外，取消其ROM故障记录，不再据此安排故障排查；必要充电/热控场景仍按独立需求决定。没有重启手机、改变热点或操作漫游eSIM。

## 6e7c418 历史已验收子项

| 子项 | 本候选证据与边界 |
|---|---|
| 包与安装 | 完整 A/B OTA 已下载本机并核验；适用性与签名匹配后标准 update_engine 于约 23:00:50 +08 返回 kSuccess(0)、UPDATED_NEED_REBOOT。安装器最终 14 分区哈希及独立 B 槽 14 项回读均与签名镜像一致 |
| 正常启动与数据 | B / 1789977174，首次稳定观察 25.8 秒，另一次正常重启稳定 20.34 秒；Enforcing、data/persist、snapshot none、两份 canary 通过。后续不再重启的限制已生效 |
| 正式双击唤醒 | Settings→Power HAL→窄 SELinux 权限生效；用户确认两轮黑屏物理双击均亮，FTS 两组 KEY_POWER 对应。实际设置开关 Off/On 与 framework、睡眠寄存器 0xD0=0/1 一致；正常重启保留，Power HAL 受控重启后 PID 改变且状态恢复。没有用直接 ioctl 冒充本轮正式路径 |
| SystemUI 横屏边距 | zh-CN / ar-SA、rotation 1 / 3 共四组真机截图和实际 InsetsProvider 缓存核对；左右均 55 px，原 111/55 px 缺陷消失。10 合成状态图标可见溢出点，未见重叠；不是全部可能组合的穷尽测试，语言/旋转/demo 已恢复 |
| OpenEUICC 管理 | 系统 SIM 列表可见；标准 MANAGE_EMBEDDED_SUBSCRIPTIONS 路由打开 PrivilegedMainActivity 只读管理列表，4 个配置、1 个已启用，未进入下载页，观察窗口没有原快捷方式崩溃。已只读核对第二实体槽 physical1→port0→logical phone1 为 eUICC，第一槽不是。2026-09-22 用户决定退出该支持，此行仅为 6e7c418 历史记录 |

## bd50b19 既有验收（不继承给新候选）

ROM `bd50b19ef82575790eb455c6cb1d712a482d62b7`、A 槽 / 1789938387 的冻结候选仍为 `/srv/build/gold/releases/20260921-090452-bd50b19`。其完整 Android 构建 01:27:20、入口 exit 0，161 项输入、14 payload / 35 实际镜像文件、保数据 OTA、安装器及独立各 14 项回读、稳定启动与 Recovery 往返、Enforcing、挂载、snapshot none、两份 canary 为既有通过。

| 已验收子项 | 证据边界 |
|---|---|
| Recovery 缓存 | 主机实际源码 32 MiB、淘汰重读、篡改拒绝和 malloc 降级；设备 1,174,408,317 字节无安装器 fixture 验签后产品检查拒绝，未刷 ROM。minadbd RSS/HWM 43,084/43,436 KiB，Recovery HWM 99,284 KiB |
| Codec2 / 相机 | 3 次冷服务启动、11 轮各 24 帧 MTK AVC 编解码及 EOS、PID 稳定；Aperture 预览和 7.218 秒 1080p 自有录像、216 帧 MTK 解码/EOS。自有片段已删；用户确认相机、麦克风、扬声器和震动体验正常 |
| Power 生命周期 | ARM64/ARM 各 27 项请求和 32 项节点测试；真实 C ABI→Enforcing HAL 的申请、更新、并发、释放、超时、退出回收、服务重启隔离、诊断权限和复位通过 |
| Power 性能策略 | 无外部电源、可比设置温度 AB/BA：11 组冷启动 258.3→252.5 ms，探索性差值区间 [-11.64,+1.55] ms；4 组滚动 p95 7.45→7.95 ms；电池估算 2.718→2.691 W，差值区间 [-0.0965,+0.0433] W。未证明可重复收益，默认 LAUNCH/INTERACTION 保持 0/0 |
| Wi-Fi 客户端 / 网络 ADB | WPA3 SAE 5GHz 关联、DHCP、真实 TLS HTTPS 与鉴权网络 ADB 通过；临时 gstatic 真 HTTPS 配置使自动重连 21.574/1.448 秒验证成功。客户端 WPA3 通过不等于本机 WPA3 热点通过 |
| 显示 / TEE / Diagnostics | 60/90/120Hz 窗口模式；普通应用 TEE EC/RSA 签名、AES-GCM 加解密及篡改拒绝，自建密钥删除；DeviceDiagnostics 正常界面与实际未知值隐藏 |
| TCP 状态 | 已装 parser/event 13 项，USB NCM 真连接 ESTABLISHED→TIME_WAIT；未证明 BPF 规则回收 |

## 构建与工程证据

2026-09-22 r7 于12:57:15 +08入口 exit 0；bacon 01:15:23、target-files-package 01:36:32 均 exit 0。168项合并输入、14个payload分区与target-files镜像全部一致；签名、VINTF、SELinux、Gold内容与版本日期门禁通过。真实镜像核对38项文件，system_ext六个退役路径缺席，eSIM支持为false，WPA3 SAE编译资源为true。product与Recovery均为UTC epoch对应的20260921版本日期。独立guard12:57:20退出，VM实读0/zbud/N/Y，无OOM，本轮ZIP工具、OTA scratch与精确needrestart配置均已清理；宿主zip/unzip仍未安装。

完整全量OTA与target-files已独立冻结至 `/srv/build/gold/releases/20260922-130256-70c2ec4`，保留同次源码、工具与输入，独立冻结检查器exit0；两包均nlink1，转存和复验临时目录已清理，index现为11个候选。OTA SHA-256 `df868491641dd16021951af2d87b2f3d7a4c8e579d0f20964e7a3cf4203c273b`；target-files `1540f7966f681f900b223627aa9dd676adb4ed005aba1c1f1ba6a7549f2c57ed`。OTA与r5的OTA字节相同：r5的OTA日期原本正确，发生漂移的是第二阶段target-files；r7原生重建后已通过全部分区和日期检查，没有沿用r5失败结论或手工改签名包。r5两份拒绝包继续单独保留。70c2ec4现已完成上文安装与回读；用户已确认WPA3能启动并被Mac扫描，Mac连接失败；当前仍未通过客户端连接验收。

构建后主机收尾已纳入主线 `tools/host/vm-guard.py`、`build-invocation.py` 与统一入口：启动前准备仅匹配本轮build/guard完整名称的临时needrestart配置；守护单例锁、服务与递归cgroup状态、源码锁共同约束恢复，重启接管保留原始VM值，外部值变化保留并明确报恢复未完成；运行期终止信号不能提前恢复。每个systemd InvocationID在jobs/build-invocations下独立建档，禁止覆盖，记录真实退出/外部信号；Android输入/result关联同一ID。117项主机测试通过。短服务实测覆盖SIGTERM延后、并发守护拒绝、SIGKILL后接管且测试服务不重启、最终VM和精确配置恢复、PID1退出与invocation对应；实际构建入口的缺unzip预检失败也独立留档且未创建Android构建。这次主机改动后168项Android输入及10个受管项目逐字节/提交不变，不另编ROM，冻结工具仍为构建时70c2ec4版本。

以下保留各轮失败原因与当时边界，当前终态以上面的r7记录为准。

r6 于 09:50:52 启动、09:51:21 入口 exit 1，未进入 Android 编译：Kati 在 version.mk 报 `BUILD_DATETIME is obsolete. Use BUILD_DATETIME_FROM_FILE.`。Soong 在配置前已生成 `out-gold-standard/build_date.txt` 并提供 `BUILD_DATETIME_FILE`，而 `BUILD_DATETIME_FROM_FILE` 在此 version.mk 包含点尚未定义。最小补丁改为从前者读取固定 epoch；不用被禁变量，也不放宽 Kati。真实 `lunch lineage_gold-bp4a-userdebug` 和 `soong_ui --dumpvars-mode` exit 0，实际版本为 `23.2-20260921-UNOFFICIAL-gold`；105 项主机测试及 8 项日期/UTC/路径空格/过时变量定向检查通过。168 项输入中仅 version.mk 相比 ecdbab1 改变，另 167 项未变。该配置检查阶段尚无新包；r7随后已通过，见本节首段。

r6 独立 guard 于 09:51:25 有匹配 invocation 的 PID1 成功退出；实读 VM 0/zbud/N/Y，临时 ZIP 工具、OTA scratch 和两服务精确 needrestart 配置均删除，宿主 zip/unzip 安装状态未改变，无 OOM。失败保存在 `jobs/gold-mainline-20260920/no-euicc-r6-terminal.json`；该轮预先准备的保护、独立 VM 原值记录及按 invocation 分开的 job 结果已实际工作，现已完成主线主机流程固化和定向验证，见本节首段。没有操作手机。

r5 当前有效 invocation 于 06:55:31 启动，bacon 01:21:45、target-files-package 55:30 均 exit 0；入口 09:14:35 exit 1。14 个分区中 product、vendor_boot 和关联 vbmeta/vbmeta_system 哈希不一致。真实 payload 提取哈希通过，product 的 606 项文件仅 etc/build.prop 不同，vendor_boot 的 Recovery ramdisk 仅 prop.default 不同，两处均为 ro.lineage.version / display.version 的 20260921→20260922；固定 Android timestamp 没有约束上游实时 UTC 版本日期。ecdbab1 首次补丁将普通日期及可选时分秒绑定 BUILD_DATETIME，但其 GNU Make 测试未覆盖 Kati 的过时变量限制，后续 r6 启动检查真实拒绝；现已按上文修正。包门禁同时核对 product/Recovery 版本日期与 epoch。105 项主机测试、7 项实际 Make 跨午夜/时区检查通过；原 167 项合并输入逐字节未变，仅新增 version.mk，当前 168 项/10 个受管项目，1158 项 Repo 提交不变。当时最终ROM包未通过，未生成候选；后续r7已完成。

本轮 06:55 的宿主 unattended-upgrades/needrestart 外部重启与 Android 终态分开记录；原 guard 因既有记录退出 1，rescue 安全接管后于 09:14:52 有 PID1 成功退出证据。实读 VM 0/zbud/N/Y、无 OOM；ZIP 工具、OTA scratch 与精确临时 needrestart 配置均清理，宿主未安装 zip/unzip。失败原结果保持，详见 jobs/gold-mainline-20260920/no-euicc-r5-terminal.json、mismatch-diagnostic.json、guard-recovery.json。两份拒绝包逐字节校验/fsync 后暂存 /tmp/gold-no-euicc-r5-unvalidated-packages，任务记录 package-preservation.json 关联旧路径；保留失败包原字节，未删历史候选或输入，不可刷写。

eSIM 移除时，实际合并输入 165 项与主线一致；保留的输入只改 device.mk，删除 3 项 OpenEUICC 补丁输入及两个独立检出。原 1158 个 Repo 项目清单未变；受管完整 manifest 从 1160 项变为 1158 项，8 个保留受管项目提交未变。包检查在旧 target-files 和旧 system_ext 实际镜像上均正确拒绝残留。该源码移除阶段尚未验证最终镜像；后续r7已通过实际镜像缺席检查。首轮02:11:40入口exit1，直接错误为target-files soong_zip的ENOSPC；guard02:11:54退出，VM实读0/zbud/N/Y、无OOM、临时ZIP工具清理。保留失败结果，不将随后完成的OTA单包冒充候选。

历史6e7c418候选的 Android r2 构建成功，02:36:40；原入口于 22:14:26 +08 exit 1，因检查器固定四空格缩进误拒绝正确 OpenEUICC 路由。`00be34a` 修正层级解析，91 项测试、原 ZIP 和冻结工具独立复验均通过，未改 Android 输入或 ZIP，也未改写原失败结果。168 项输入一致，签名/VINTF/SELinux、14 payload / 38 实际镜像文件通过。OTA SHA-256 `22f5937ef97ed7073e57c357c0302bf77bbdd6cddb2b474aab7073a38e79f6cb`；target-files `7e8cc241b97b73beef1dacdd0948af6271c4c1d5bc1b64d786e142317256f98c`。

r2 guard 于 22:14:31 恢复，终态实读 VM=0/zbud/N/Y，无 OOM，临时 ZIP 工具清理；r1 缺 unzip 失败及 6e7c418 前置检查修复记录保留。WPA3 补丁只改一个实际 Android XML；89ae983 于 2026-09-22 00:20:25 +08 入口 exit 0，Android 编译打包 12:33，签名/VINTF/SELinux、14 payload / 39 实际镜像文件通过。guard 00:20:29 恢复 VM=0/zbud/N/Y，临时 ZIP 工具清理、无 OOM。冻结候选 `/srv/build/gold/releases/20260922-002433-89ae983` 已独立复验，包含撤回之前的 OpenEUICC，未安装；已由70c2ec4移除版取代，旧包仍保留且未安装。

活动输出两种同次包的三个路径在与独立冻结候选逐个重读 SHA-256 一致后清理，释放约 3.80 GiB，输出 inode 9437191 不变；记录 `jobs/gold-mainline-20260920/wpa3-active-package-duplicates.json` 给出已保存冻结路径。历史候选、官方输入、OverlayFS、缓存与 swap 均保留。OverlayFS 合并视图到 releases 直接 rename 实测返回 EXDEV；冻结改为逐包复制、重读 SHA-256 并 fsync 后才移除该包的全部可变硬链接，保存路径映射和独立工具复验；不改 OUT_DIR，不复制第二套输出。

目录迁移构图于 14:56:55 exit 0、01:01:37，guard 14:57:03 退出、VM 0/zbud/N/Y，无 OOM；.top、新路径、inode9437191、161 项原输入和1158个Repo提交未变。整机重启恢复未实测，仅为主机维护边界，不列ROM待办。`27ea764` 已退役15个 archive/hybrid 文件；旧源码从 Git 历史查阅，当前主线 Python 提取/构建/检查工具继续保留，后续适配只走主线。

固定 IMS APK SHA-256 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1` 为普通 Git blob，原厂完整依赖配方不足仍是 prebuilt 限制。匹配 Global vendor/kernel/modules、所需 ARM 媒体图形库、官方 Global/CN 输入和历史候选均有恢复及硬件用途，不能删除。原始设备/无线日志与截图只在本机私有目录0600，Git只存脱敏结论；维护、构建、冻结入口见 [LAYOUT](LAYOUT.md)、[BUILD](BUILD.md)、[RESTORE](RESTORE.md)。

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

WPA3 下一轮任务记录使用 `jobs/gold-mainline-20260920/wpa3-r1-build-request.json` / `wpa3-r1-build-result.json`；是否实际启动、终态与 VM 恢复以实时服务和这些记录为准。该构建不授予重启当前手机的权限。

2026-09-22续编r2于02:34:26入口exit1，bacon阶段12:05；OTA zip2zip自身临时副本仍触发ENOSPC，target-files阶段未启动。guard02:34:37恢复VM并清理工具；旧峰值估算不足。新增可选OTA系统盘临时目录补丁并准备r3：98项主机测试、实际Make宏默认/覆盖/含空格路径检查通过；合并输入166项/9个受管项目，原165项字节不变，只增加build/make主机打包规则。最终包尚未验收；手机和网络未动。

2026-09-22移除版r3：bacon12:40、target-files48:59均exit0；签名/VINTF/SELinux与14payload哈希通过，但03:55:41最终Gold门禁exit1。target-files和实际system_ext仍含OpenEUICC目录及32字节JNI链接，目标库已不存在，不能标完成。guard03:55:43退出，VM实读0/zbud/N/Y，临时ZIP工具与OTA目录均清理、无OOM。标准Gold CleanSpec迁移仅移除退役eSIM安装路径并使system_ext及target-files列表失效，由原生规则重建，保留缓存和其他中间结果；不放宽门禁。100项主机测试通过，新增真实文件系统回归覆盖悬空/外部链接、其他应用保护、重复执行和非Gold不动。当前167项合并输入/9受管项目，原166项字节不变；r4终态和实机均待完成。

2026-09-22移除版r4于05:19:32入口exit1，bacon耗时01:07:20；三条Gold CleanSpec迁移已真实执行，产品与target-files树中的OpenEUICC路径缺席。失败位于add_img_to_target_files生成system.img，其合并root/system的临时副本仍在数据盘。相同输入、1146617856字节镜像和3473请求inode在系统盘定向生成exit0，仍余28766块/313 inode，排除了镜像容量不足；原空间预检遗漏这一临时副本。guard05:19:37成功退出，VM实读0/zbud/N/Y、工具和OTA目录已清理，无OOM。原打包补丁扩展到add_img_to_target_files，默认路径不变，六项实际Make调用验证通过；未改设备分区大小或放宽产物门禁。当前167项输入中仅主机Makefile改变，其余166项一致。新候选仍待构建与冻结，手机未操作。
