# gold / LineageOS 23.2 ROM 更新方案

2026-09-17 更新 · OTA 设计稿。Global 标准构建及后续启动、充电修复已进入源码；最新增量镜像已刷机并通过短时开机检查，见 [STATUS.md](STATUS.md)。本轮仅推送源码，暂不验证最新完整安装包，未启用更新源或发布新的 ROM Release。下文 r1 数据仅记录旧发布版本。

**建议路线：先固定 Global 底包和发行密钥，完成“完整 ZIP 手动保数据升级”；随后让系统内 Lineage Updater 下载并安装同一个完整 ZIP；增量包等确有带宽收益时再做。** 使用现有 GitHub 仓库与 Release 即可，无需数据库、更新服务器或新客户端。

CN Recovery R1 是“完整安装并首次启动通过的预发布测试包”。它尚未证明保数据升级、Virtual A/B 完整合并与回退，也未完成安装后 Recovery 和全部硬件验收。Global OS3.0.5.0.VNQMIXM 已用于当前实机开发版本，但完整包迁移、保数据升级和全部硬件仍未验收。

较早的标准 Global 构建已通过 Neverallow、Treble 策略和最终包检查，包含 22 个 A/B 分区及 7 个动态分区；这是历史记录，见 [standard-build-20260914.json](../validation/standard-build-20260914.json)。下表中的分区和历史策略失败属于旧混合镜像流程。

当前配置仅随包携带锁定国际版 `scp`，其余底层固件沿用设备现有版本；2026-09-14 的完整包已核实合计 14 个分区，见 [历史记录](../validation/repack-scp-only-20260914.json)。该完整包早于后续实机修复，不能视为包含全部当前改动的新安装包。SCP 与 Google 套件或语音助手的适配关系尚未证实。构建流程见 [BUILD.md](BUILD.md)。

## 1. 历史 CN R1 证据与更新边界

2026-09-14 读取发布仓库快照 `e14a7fa605391f61e8e4c0b09b679e31c042a34a` 的构建、安装、Recovery 文档和验证记录。以下表格仅描述当时 CN R1 的证据，不是当前 Global 状态。

| 已知事实 | 对更新设计的影响 |
|---|---|
| r1 完整 A/B OTA 包含 25 个分区，ZIP/payload 签名及解包回读通过 | 已有可复用的完整包形态；不必重新发明刷机协议 |
| 9 个逻辑分区为 system、system_ext、product、vendor、odm、system_dlkm、vendor_dlkm、odm_dlkm、mi_ext | 最终 hybrid 包与旧设备树的分区列表有差异，最终 target-files 才是发布依据 |
| 其余包括 boot、vendor_boot、dtbo、vbmeta 体系以及 LK、基带等固件 | OTA 不只是替换 Android 上层；跨地区固件切换需要独立验证 |
| Recovery 位于 vendor_boot v4 的 recovery 片段，r1 成对重建 vendor_boot 与 vbmeta | 新包必须带匹配的 Recovery，不能让 OTA 换回小米 Recovery，也不能只换 ZIP 内一个镜像 |
| 当前用公开开发测试密钥；脚本可传 AVB key，但正式发行签名流程尚未闭环 | 传一个 `--key` 并不等于完成 APK/APEX、OTA、payload 和 AVB 的发行签名 |
| 安装先清除了 data/metadata，旧 default 组和历史 COW 导致第一次 status 7；wipe-super 后第二次 status 0、B 槽首启成功 | 这是全新安装证据；不能称为保数据更新。wipe-super 会破坏两槽旧逻辑系统，必须排除在日常升级流程之外 |
| 未完成安装后再次进入 Recovery、完整硬件与长期验证；仍有图形帧积压、热点相关日志、27 项严格 neverallow 失败 | 不向普通使用者开放默认更新推送；不能把 Enforcing 或首启成功当作稳定版验收 |

详细证据见 [FULL_BUILD](https://github.com/Redmi-Note-13-Gold/lineageos-gold/blob/e14a7fa605391f61e8e4c0b09b679e31c042a34a/docs/FULL_BUILD.md)、[INSTALL_TEST](https://github.com/Redmi-Note-13-Gold/lineageos-gold/blob/e14a7fa605391f61e8e4c0b09b679e31c042a34a/docs/INSTALL_TEST.md)、[RECOVERY](https://github.com/Redmi-Note-13-Gold/lineageos-gold/blob/e14a7fa605391f61e8e4c0b09b679e31c042a34a/docs/RECOVERY.md)。

旧设备树 snapshot 启用了 `AB_OTA_UPDATER`、virtual_ab_ota 产品继承、update_engine/update_engine_sideload/update_verifier、Boot HAL 与动态分区，并配置 system/vendor postinstall。但它仍有旧内核/AVB flags 输入；不能从该 snapshot 直接推断最终 r1 的运行配置。本轮随后已只读取得最终 r1 target-files 的关键 META 与 ZIP metadata，结果如下；运行态快照压缩、snapuserd、Boot HAL 和回滚保护仍需实机证据。

### 最终 r1 元数据补充核查

读取对象是最终 `ota-with-recovery/target-files`，不是普通 bacon 的中间 target-files：

| 项目 | 实际结果 |
|---|---|
| A/B 与 Virtual A/B | `ab_update=true`、`virtual_ab=true`、`virtual_ab_cow_version=2` |
| 快照压缩与 userspace 字段 | 本次返回的最终 META 未见这些字段；不能据此断定开启或关闭 |
| 分区 | AB 清单25项；动态清单9项，与上文最终镜像清单一致 |
| super | 9,126,805,504 字节；mediatek_dynamic_partitions 组配置9,122,611,200字节 |
| Recovery | `no_recovery=true`，对应无独立recovery分区；不表示没有vendor_boot中的Recovery |
| 最终 postinstall | 仅 system 的 `otapreopt_script`，ext4、optional=true；旧设备树的vendor checkpoint_gc并未出现在最终postinstall配置 |
| update_engine 配置 | payload major=2、minor配置=9；ZIP payload头实际major=2，不能将配置minor值当作已解析payload manifest的值 |
| ZIP安装约束 | `ota-type=AB`、`pre-device=gold`，本次metadata未出现wipe/downgrade标志 |
| ZIP目标版本 | SDK36、SPL2026-08-01、post-timestamp及incremental均为1789310122、fingerprint仍为userdebug/test-keys |
| OTA下载缓存字段 | `ota-required-cache=0`；不代表/data无需下载空间、COW空间或合并空间 |

APK/APEX META映射也已取得，包含测试证书和预签名条目。它们是构建证书映射，不能把行数当成实际安装的应用数量；最终system/Recovery/payload信任集仍未重新解包确认。这个差异说明，更新门槛应依最终产物建立，不能只读设备树开关就宣布后台OTA可用。

## 2. 把首次迁移与日常升级分开

| 路径 | 初始支持策略 | 数据与回退边界 |
|---|---|---|
| CN r1 → 首个 Global 基线 | 独立迁移，人工选择并执行；不放进 CN 自动更新入口 | 默认设计为备份后全新安装，具体清除操作仍须刷机执行阶段授权；暂不承诺保数据 |
| 已知历史混刷布局 → Global | 先审计 super 分组、快照和固件状态；按已验证迁移文档处理 | 仅特定布局确有需要时才重建 super；不能因任意 status 7 自动 wipe-super |
| Global G0 → G1，同地区/同签名/同布局/同主版本 | 优先验证完整 ZIP 手动升级，之后开放 Updater | 正常目标是保留 data；安装、首启、加密解锁及合并完成均须通过 |
| Global → 新地区/新分区布局/新签名体系/Android 主版本 | 重新作为迁移项目验证 | 不按“版本号更大”自动放行；可能需要新入口和新验收 |

CN `3.0.10` 与 Global `3.0.5` 不能按末尾数字比较新旧。地区分支、Android/vendor 安全补丁、AVB rollback index/location、LK/TEE/modem 协议兼容性和实际硬件 SKU 才决定可迁移性。不要为通过检查伪造时间戳/SPL 或全局启用允许降级。

第一版 Global 应尽量同时收敛底包、布局、Recovery 与正式签名，建立一个可长期维护的起点 G0。以后保持地区和信任体系稳定，避免每次发布都要求先手刷五张镜像。G0 尚未验收前，CN 用户仍停留在现有独立发布说明；Global 测试输入不覆盖现有 r1 资产。

## 3. 阶段一：完整 ZIP 手动保数据升级

AOSP 的完整 OTA 不依赖某个旧版本的块内容；增量 OTA 则要求匹配的前一版 target-files。这里先使用完整 ZIP，仍必须满足设备、分区、签名、固件和时间戳检查，不能把“完整包”理解成适用于任意起始状态。[AOSP OTA 构建说明](https://source.android.com/docs/core/ota/tools)

最低实现要求：

1. 由标准源码构建生成完整 target-files，再通过同版本 releasetools 完成发行签名与完整 A/B ZIP。设备树必须描述最终启动链和分区；退出旧 hybrid 镜像改写流程。当前入口为 `m -j8 bacon target-files-package`，实际完成状态见构建验证记录。
2. 在最终 target-files 里统一固化全部分区与签名信息，并保存映像哈希、固定 manifest、底包锁定记录、构建参数及工具版本。所有后续校验读取最终包。
3. 包内不含 userdata、不带 wipe/downgrade 意图；但这只是允许保数据的必要条件，实际解密与应用数据兼容性仍需测试。
4. 同基线升级只使用配套 Recovery 的完整 ZIP sideload；正常升级不格式化 data/metadata、不 wipe-super、不刷两槽启动链、不强制改活动槽。
5. Recovery 最终 status 0、update_engine 各阶段成功后再启动系统。主机传输完成、百分比或返回 0 都不能独立证明安装成功。
6. 完成首次解锁、应用与数据抽查，再进入 Recovery，并恢复系统。若实际使用 Virtual A/B，等待和证明合并结束，然后才能开始下一次更新测试。

现有九个独立附件可继续保留：ROM ZIP、五张启动链镜像、super_empty、README、SHA256SUMS。日常升级用户只需 ROM ZIP 与校验/说明；其他镜像属于初装或恢复材料。附件全部来自同一最终构建，不允许复用名字相同但内容已变化的旧版本文件。

## 4. 阶段二：现有 Lineage Updater + 静态 JSON

### 实现必须跟随本项目锁定的源码

本仓库 manifest 将 Updater 固定在 `cda5769201d3dd0c89eb8a88e5d097a6d40ffa61`。已读取该提交的实际实现。它使用**顶层 JSON 数组、`files[]`、`type`、`sha256`**；网上常见的旧 `response/id/romtype` 格式不适用于这里。[固定提交 README](https://github.com/LineageOS/android_packages_apps_Updater/blob/cda5769201d3dd0c89eb8a88e5d097a6d40ffa61/README.md)

建议在首个支持更新的 Global 构建内，用现有 `lineage.updater.uri` 配置一个同仓库的 HTTPS raw JSON 地址，路径显式区分设备、Lineage 主版本和 Global 基线，例如计划中的 `updates/gold/23.2/global-g0.json`。不需要修改 Updater 源码，不依赖手机连接 MacBook，也不新增服务。该路径目前是设计示例，尚未创建。

该提交的元数据请求强制 HTTPS、不跟随重定向、10 秒超时。入口必须直接返回 JSON 与 HTTP 200，不能使用 GitHub 网页、`latest/download` 重定向入口或登录后页面。Release 文件下载链与元数据入口是不同路径，重定向和断点续传必须分别实测。[网络请求实现](https://github.com/LineageOS/android_packages_apps_Updater/blob/cda5769201d3dd0c89eb8a88e5d097a6d40ffa61/app/src/main/java/org/lineageos/updater/data/source/network/UpdatesNetworkDataSource.kt)

### 最小非流式元数据示例

下面只是**JSON 语法有效的占位示例，不能部署**：日期、大小、哈希、文件名均是假值；`.invalid` 地址刻意不可使用。实际值必须自动从最终已签名 ZIP 和最终系统属性取得。

```json
[
  {
    "datetime": 2000000000,
    "files": [
      {
        "filename": "REPLACE_WITH_FINAL_SIGNED_GOLD_FULL_OTA.zip",
        "os_patch_level": "2030-01-01",
        "os_sdk_level": 36,
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "size": 1,
        "url": "https://example.invalid/REPLACE_WITH_IMMUTABLE_RELEASE_ASSET.zip"
      }
    ],
    "type": "UNOFFICIAL",
    "version": "23.2"
  }
]
```

实际字段规则：

- `datetime` 对齐 OTA post timestamp 和最终 `ro.build.date.utc`，不是上传时刻。每个公开修订必须有真实、单调递增的构建身份；同 timestamp 的 r2 可能被当作当前构建过滤，不靠改文件名解决。
- `type` 对齐 `ro.lineage.releasetype`；源码比较忽略大小写。`version` 写真实 Lineage 版本。当前客户端并没有根据自定义 firmware 字段保证地区兼容，额外属性会被忽略。
- `os_sdk_level` 虽在反序列化定义里可选，遗漏会变成 0，被当前设备 SDK 检查过滤；因此生成器必须填写。Android 16/本次 23.2 预期为 36，仍以最终 metadata 为准。SPL 用 Android 上层真实值，不用 vendor 的日期冒充。
- 一个发布项只放一份完整 ROM 在 `files[0]`；源码只取第一项，不会从中智能选择镜像、增量或恢复包。
- `sha256` 和 `size` 来自最终签名之后的文件。源码将 sha256 用作更新身份；下载完成后的真实性检查还会调用 `RecoverySystem.verifyPackage`，并由 update_engine 验证 payload。不要把 JSON 内哈希本身当成独立信任根。
- 初期省略 `ota_property_files`，让更新完整下载后安装；此时缺少流式范围，客户端不满足流式安装条件。待 HTTP Range、重定向、payload offset、断网恢复与快照全过程专项验收后，才原样提取最终 ZIP 中的 `ota-property-files`，不要人工计算或沿用签名前偏移。

依据：[数据映射](https://github.com/LineageOS/android_packages_apps_Updater/blob/cda5769201d3dd0c89eb8a88e5d097a6d40ffa61/app/src/main/java/org/lineageos/updater/data/source/network/NetworkUpdate.kt)、[过滤逻辑](https://github.com/LineageOS/android_packages_apps_Updater/blob/cda5769201d3dd0c89eb8a88e5d097a6d40ffa61/app/src/main/java/org/lineageos/updater/data/UpdatesRepository.kt)、[安装条件](https://github.com/LineageOS/android_packages_apps_Updater/blob/cda5769201d3dd0c89eb8a88e5d097a6d40ffa61/app/src/main/java/org/lineageos/updater/util/InstallUtils.kt)、[签名验证](https://github.com/LineageOS/android_packages_apps_Updater/blob/cda5769201d3dd0c89eb8a88e5d097a6d40ffa61/app/src/main/java/org/lineageos/updater/controller/UpdaterController.java)。

Updater 的 A/B 安装路径把本地 ZIP 的 payload 偏移与 properties 交给 `UpdateEngine.applyPayload()`；系统内后台安装与 Recovery sideload 是不同执行环境。前者须另测 SELinux/Binder 权限、存储空间和重启后恢复，不能由一次 sideload 成功替代。[A/B 安装实现](https://github.com/LineageOS/android_packages_apps_Updater/blob/cda5769201d3dd0c89eb8a88e5d097a6d40ffa61/app/src/main/java/org/lineageos/updater/controller/ABUpdateInstaller.java)

### 不让静态入口误推跨基线升级

CN 和 Global G0 使用不同入口；只有手工迁移且验收通过的 G0 构建才内置 G0 入口。入口只列经确认兼容的同基线完整包；未来更换底包大代、签名或分区布局时，先保留旧入口，另行设计迁移。JSON 中添加 `firmware: global` 不会变成安装防护。

静态入口仅解决“把包推荐给谁”，最终 OTA 自身仍需保留设备/时间戳/签名等安装前置校验，并核查该 release-tools 版本支持哪些固件/源版本约束。不要为实现一个自定义字段另写安装服务。

## 5. 签名：在 Global 起点前做一次明确决策

需要分别管理以下信任关系，公开证书和指纹可归档，私钥不进仓库、Release、日志或普通构建快照。

| 层次 | 需要核对 |
|---|---|
| APK/platform/shared 等 | 最终应用证书映射、shared UID 与系统权限关系；改签不能默认保留旧应用数据 |
| APEX | 容器证书和内部 payload key 都正确，预签名组件按实际用途保留 |
| OTA ZIP | 最终系统 otacerts.zip 与 Recovery `/res/keys` 信任目标发行证书 |
| A/B payload | update_engine 实际读取的 payload 公钥信任新包；不能只验证 ZIP 外层 |
| AVB / 启动链 | 顶层及子链密钥、descriptor、rollback index/location 一致；小米保留签名部分不宣称改成项目签名 |

AOSP 签名流程会涉及应用、OTA 证书和 APEX 双重签名；单独重签镜像或给打包命令换 key 无法覆盖这些关系。建议把最终 target-files 签名作为统一发布步骤，之后重新生成镜像/payload/ZIP并验证，禁止最终签名后再修改系统内容。[AOSP 发行签名](https://source.android.com/docs/core/ota/sign_builds)

最小维护路线是：首个 Global G0 全新安装即使用项目独有发行密钥，后续保持稳定。现有 CN 测试密钥到 G0 的过渡归入首次迁移，不在现阶段承诺无损改签。即使使用自有密钥，本适配仍要求 bootloader 保持解锁；这不是小米官方签名或可重新锁定的认证。

如果以后确需保数据换钥，必须独立设计旧信任链可验证的桥接发行版，逐层解决 ZIP、payload、Recovery、APK/shared UID、APEX 和 AVB 的过渡，再测试桥接后移除旧公钥的下一版。不能仅在新 Recovery 加一个公钥便宣称所有旧数据可用。公开测试私钥已知，不应永久保留其信任，也不能把桥接设计当作安全性已恢复的证明。

## 6. A/B 回退不能等同于备份

Virtual A/B 对启动分区保留槽位，对动态分区使用快照并在成功启动后合并；合并开始后，不能承诺旧逻辑系统仍是一套可随意切回的完整副本。[AOSP Virtual A/B](https://source.android.com/docs/core/ota/virtual_ab)

失败处置需要按阶段记录：

| 阶段 | 设计中的处理原则 |
|---|---|
| 下载/签名检查失败 | 不安装；保留旧系统，重新取得正确包 |
| payload 写入或 postinstall 失败、尚未切换 | 记录 update_engine 错误与快照状态；确认旧槽可启动，由标准更新引擎处理取消/清理，不手删 COW |
| 新槽首次启动失败、尚未进入不可逆合并阶段 | 以 Boot HAL/bootloader 实测回退为依据；待验证前只称“预期机制”，不承诺 gold 自动恢复 |
| 已成功启动并进入/完成合并 | 不指导用户直接 fastboot set_active 回旧槽；先确认合并状态。后续修复优先使用更新的同基线完整包 |
| bootloader/TEE/基带等不兼容，或 data 解密失败 | 采用事先演练过的配套恢复输入；可能需要全新安装及外部备份恢复，不能保证切槽解决 |

A/B 不自动撤销应用和共享 `/data` 的变化；userdata checkpoint 也必须独立确认实现和状态。跨地区更改 TEE/KeyMint 相关固件时，应专门验证锁屏密码、FBE 解锁、Keystore、指纹与应用密钥，而非只看桌面出现。[AOSP userdata checkpoint](https://source.android.com/docs/core/ota/user-data-checkpoint)

备份应包含可恢复的用户文件/账号恢复材料和设备专属分区的私有记录。设备校准、modem 持久状态和身份材料不进入通用 OTA，也不发布；新包分区清单必须明确排除这些内容。当前“安装前 B 槽未改动”的回读发生在 wipe-super/OTA 之前，不能用它证明安装后仍有完整旧系统。

## 7. 发布顺序与最小保留材料

1. 冻结源码提交、官方底包校验和、签名配置与最终 target-files；生成最终完整 ZIP及配套镜像。
2. 完成离线检查与候选实机测试，记下测试的精确起始版→目标版、槽位、布局及签名指纹。
3. 用唯一 tag/文件名上传同一批 Release 资产；验证公开 URL 可下载、长度与 SHA-256 一致，再完成 Release 说明。发布权限在实际执行阶段处理。
4. 从已上传且验证一致的最终 ZIP 生成 JSON。先离线解析与设备兼容性测试，最后在一个 Git 提交中更新静态入口。
5. 再从手机实际请求入口、下载并走一次升级；记录元数据 HTTP 状态、所选包身份、安装结果、重启和合并结果。

这是“先不可变资产、最后切换索引”的顺序，不是跨 GitHub Release 和 Git 的数据库事务。缓存可能暂时返回旧 JSON，因此新旧索引引用的资产都必须保持可用；不要覆盖同 tag 同名 ZIP，不复用 hash，不删除正在分发的旧包。发现问题先把入口回退到上一份 JSON，或发 `[]` 停止推荐；这不能召回已经下载或开始安装的包。

每版保留最终签名 target-files、完整 ZIP、配套恢复镜像、证书指纹、固定输入清单与验证摘要。公开内容和私有恢复材料分开归档；无需新增另一套发布数据库。SHA256SUMS 与 JSON 均由最终产物生成，避免人工维护两套数值。

## 8. 开放更新前的验收门槛

| 门槛 | 必须取得的证据 |
|---|---|
| 构建可追溯 | 固定源码与 Global 提取输入→标准 target-files（含配套 Recovery）→发行签名→最终 ZIP；不依赖不明历史成品。当前 IMS 仍需固定的兼容 APK 输入，其完整重建链尚未闭环 |
| 包结构 | 25 个分区或新基线明确变更后的完整清单；全部解包回读、AVB/FEC、VINTF、metadata和postinstall一致 |
| 签名 | 正式证书映射及指纹；系统/Recovery/payload相互信任；修改或错误签名的包被拒绝 |
| Global 初装 | 被支持的实际 gold SKU、配套 Recovery、安装、首启、再次 Recovery、基础硬件；其他地区型号不得自动外推 |
| 保数据手动升级 | G0→G1，再做 G1→G2 覆盖相反槽方向；保留照片/文件哈希样本、应用数据、锁屏解密、账号和密钥功能 |
| Virtual A/B | 最终配置、运行快照状态、启动成功标记、合并完成与空间回收；升级及合并中受控重启恢复；不可只看重启提示 |
| 系统内 Updater | 检查、完整下载、签名验证、applyPayload、重启、合并、再次检查无重复推荐；断网续传、空间不足、损坏包负例 |
| 恢复 | 在测试设备/测试数据上演练可恢复故障；记录哪些阶段可自动回退、哪些只能配套 Recovery 恢复，避免在唯一日用数据上试验 |
| 功能与发布级别 | 电话/短信/双卡/IMS、Wi-Fi及真实客户端热点、相机音频、蓝牙、GPS、传感器、充电/温控/休眠、FBE/指纹与关键回归；图形和热点问题有结论，27项neverallow清楚关闭或继续限制为明确预发布 |

不为了验收主动破坏唯一设备的启动链或触发不可恢复断电；故障测试先选下载中断、错误签名、低空间等受控场景，低层故障在有可靠恢复路径的测试环境再做。

## 9. 增量包放在最后

旧 CN R1 完整包约 1.74 GB；本次标准 Global 完整包为 1.207 GB，是否做增量应由实际发布频率、下载耗时与维护成本决定。每一对增量都需要精确的旧/新最终签名 target-files、源构建匹配检查、单独验证和失败后的完整包入口；旧包还可能含用户修改后的 boot 或逻辑分区。首次 CN→Global、改签和布局迁移不做增量。

当前 Updater 只取 `files[0]`，静态 JSON 也不会自动根据当前构建挑选增量与完整回退。即使 URL 支持 `{incr}` 占位，也要维护每个源版的索引和完整包去向，成本明显高于一个完整包入口。达到真实带宽瓶颈之前，保持每版完整包即可。

## 10. 本轮还需要补齐的证据接口

| 提供方 | 最小输出 |
|---|---|
| Android 结构整合 | r1最终META已取得并见第1节；下一版Global须再次导出同样字段。仍需最终system/Recovery的OTA与payload公钥指纹、实际APK/APEX证书核对、快照压缩/userspace配置及Boot HAL运行证据 |
| Global 底包整合 | OS3.0.5.0.VNQMIXM完整Recovery ZIP真实性/校验、payload完整或增量属性、分区清单；与CN物理固件和AVB rollback字段差异；正式确认候选是否适合当前SKU |
| 下一轮实机验证 | 当前起始版/槽位/加密与snapshot状态；可用Boot HAL和snapuserd；配套Recovery重进；同基线保数据升级与merge/回退记录 |

以上未齐前，可以整理构建与元数据生成方案，但保持更新入口未启用，不把 Global 候选或现有 CN r1 标为“已经支持 OTA”。
