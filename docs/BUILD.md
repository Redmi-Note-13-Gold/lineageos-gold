# 构建与验证

主路径：固定源码 + Global 官方提取输入 → 标准 `bacon target-files-package` → Android 官方验证工具。执行环境为原生 Linux x86_64；Mac 只做源码审阅和原生主机测试。

## 日常增量

Android hiddenapi 编码与 OTA 打包需要 PATH 中真实可执行的 `unzip` 和 `zip`。统一入口在配置/构图前预检，直接 build-source.py 也在创建输出前预检，并把选中工具的路径和 SHA-256 存入同次 inputs.json。缺失时退出，不跳过编码或包校验。需要临时依赖时，可按 jobs 中执行记录，用 APT 下载当前 Ubuntu 的已认证包、核对包 SHA-256 后 dpkg-deb 解包，仅为本次服务加入 PATH；不持久安装，终态后由独立 guard 清理本次目录。

科研机复用 `/srv/build/gold/source` 和其中的 `out-gold-standard`，不 clean，不创建第二份完整输出。先确认 source 是正确 overlay 挂载且没有另一构建，再以 **root（实际 UID 0）** 执行。

科研机 `/srv/build/build-gold.sh [extra_targets...]` 统一指向本仓库 `tools/host/build-research.sh`：直接由 root 执行，不再切换专用编译账户。HOME 固定为 `/root`，ccache 实际目录为 `/root/ccache`，24 GiB swap 位于数据盘 `/srv/build/gold/host/build.swap`。额外参数用于同时编译模块或测试，不省略完整 OTA。底层入口也可直接调用：

```sh
export USER=builder LOGNAME=builder BUILD_USERNAME=builder
export HOME=/root
export USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
export CCACHE_DIR=/root/ccache
export GOGC=50 GOMEMLIMIT=10GiB GOMAXPROCS=4
python3 /srv/build/gold/project/tools/build-source.py \
  --tree /srv/build/gold/source \
  --lunch lineage_gold-bp4a-userdebug --out out-gold-standard \
  --jobs 2 --build-datetime UNIX_TIMESTAMP --execute
```

`UNIX_TIMESTAMP` 使用本次构建时间。USER、LOGNAME、BUILD_USERNAME 的 `builder` 仅保留已有产物标识，真实进程 UID 是 root，HOME 是 `/root`；这些环境字符串不代表运行账户。可附加 `--extra-target gold_vibrator_contract_test`，只编译振动契约测试程序，不代表该测试已经运行。

迁入的源码仍由原账户拥有。当前 root 的 Git 配置通过 `include.path` 加载 `/srv/build/gold/host/git-safe-directories.config`，只信任本源码树 `repo list -p` 枚举的 1158 个项目和 3 个 Repo 元数据仓库的确切路径。没有设置 `safe.directory=*`，也没有递归更改 overlay 所有权。新增项目或迁到新路径时，应核对后更新清单；对单个已核对仓库可执行 `git config --global --add safe.directory /exact/repository/path`。科研机 Git 2.43 的 `source/*` 未通过实际检查，不能用它替代确切路径。

原有 `out-gold-standard` 的目录和文件也必须归实际构建 UID 所有：nsjail 内的映射用户不能依靠宿主 root 的权限覆盖旧 UID 的写权限。科研机已确认该输出全部位于 overlay upper，再只调整这个受管输出的所有权；未复制输出、改写文件内容或关闭沙箱。

日常实际工作区是 `/srv/build/gold`；唯一输出随源码同盘迁移，文件和缓存继续复用。每次进入构建脚本都先运行 `tools/host/check-research-layout.py`，核对数据盘 UUID、准确的 overlay 挂载和三层路径；缺失或不匹配则在写输出前退出。宿主路径由 `tools/host/research-layout.json` 维护。

先执行 `/srv/build/build-gold.sh --check-environment`，检查实际 UID、HOME、源码路径、输出目录归属、完整固定清单导出和缓存读写。清单导出失败也会在正常构建的 `result.json` 中留下失败记录。长期构建先准备本次精确重启保护，再通过root systemd服务启动原入口及独立guard，保留资源上限：

```sh
unit="gold-build-$(date +%Y%m%d-%H%M%S).service"
guard="${unit%.service}-vm-guard.service"
record_dir="/srv/build/gold/jobs/${unit%.service}"
epoch=$(date +%s)
install -d -m 0700 "$record_dir"
# PATH须已包含本轮认证的zip/unzip；临时盘须按本次job记录准备并负责清理。
: "${GOLD_OTA_TMPDIR:?先准备本次0700私有打包临时目录}"
python3 -B /srv/build/gold/project/tools/host/vm-guard.py \
  --unit "$unit" --guard-unit "$guard" --record "$record_dir/vm.json" \
  --protection-record "$record_dir/needrestart.json" --prepare-restart-protection
systemd-run --unit="$unit" -p User=root -p Group=root \
  -p WorkingDirectory=/srv/build/gold/source -p Environment=HOME=/root \
  -p "Environment=PATH=$PATH" -p "Environment=BUILD_DATETIME=$epoch" \
  -p "Environment=GOLD_OTA_TMPDIR=$GOLD_OTA_TMPDIR" \
  -p MemoryHigh=12800M -p MemoryMax=13G -p MemorySwapMax=20G \
  -p OOMPolicy=stop -p Nice=5 \
  -p StandardOutput=append:/srv/build/gold/logs/"$unit".log -p StandardError=inherit \
  /srv/build/build-gold.sh
systemd-run --unit="$guard" -p User=root -p MemoryMax=128M \
  -p OOMScoreAdjust=-900 -p StandardOutput=append:"$record_dir/guard.log" \
  -p StandardError=inherit \
  python3 -B /srv/build/gold/project/tools/host/vm-guard.py \
    --unit "$unit" --record "$record_dir/vm.json" \
    --protection-record "$record_dir/needrestart.json"
```

swap 已在 `/etc/fstab` 持久化；对应 swap 单元依赖 `srv-build.mount`。原 `goldbuild` 账户仅保留历史用途，其 HOME 已更新为 `/srv/build/gold/history/retired-build-home`；日常构建仍由 root 执行，HOME 为 `/root`。迁移完成后的 IMS 修正版已以实际 UID 0 完成完整构建及验证，见 [最终记录](../validation/ims-build-20260920.json)。迁移前已安装的首次候选按其原构建身份和独立 OTA 路径保留。

路径迁移后的定向验证使用 `/srv/build/build-gold.sh --check-build-graph`：在原输出内以原 build_date 执行 `m nothing`，由 Soong 迁移输出绝对链接并重生成构建图。它与正式构建共用源码锁，仍须使用下述同等 systemd 内存保护与独立 VM guard；不 clean、不生成第二份完整输出，也不等于新 ROM 验收。2026-09-21 的迁移构图已成功结束（01:01:37、exit 0），guard 和实读 VM 恢复通过；详见 host-layout validation。

内存环境转发补丁位于 `tools/host/soong-memory-env.patch`；当前科研机已经有此变化。恢复其他机器时先检查 `git -C build/soong diff`，只对未应用的对应基线使用 `git apply`，不要重复套用。它不改变 ROM 运行参数。长时间任务应有独立日志与明确进程/退出状态，不能靠日志文件存在判断成功。

## 新环境准备

先按 [RESTORE](RESTORE.md) 恢复源码。使用 `firmware/gold-global.json` 锁定的官方 Recovery，通过 `tools/prepare-stock.py --help` 选择本机已有工具提取。准备目录需包含 `physical/`、`logical/` 和 `prepared.json`，再执行：

```sh
python3 device/xiaomi/gold/prepare-vendor.py \
  --tree /path/to/android --lock /path/to/lineageos-gold/firmware/gold-global.json \
  --stock /path/to/prepared-stock
```

此步骤核验原厂镜像并提取配套 kernel、DTB、DTBO、modules 与厂商组件。日常源码修改不重做完整提取；提取配方改变时只重提取受影响部分，并重新生成 vendor 构建定义。不要直接只改生成的 Android.bp 而漏掉提取清单。

IMS 固定输入现作为 `vendor/xiaomi/gold/ims/ImsService.apk` 普通 Git blob 纳入主线，SHA-256 为 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1`。恢复源码时随集成文件复制，准备 vendor 默认使用它；不再需要外部旧 APK。来源、版本、完整依赖载荷和原厂重建限制见 [IMS 说明](../vendor/xiaomi/gold/ims/README.md) 与 `input.json`。原厂依赖打包配方仍不完整，但构建输入本身可从主线 Git 独立取得。

## 产物与验收

当前配置为 14 个 OTA 分区；唯一随包底层固件是 `scp`，以 `proprietary-firmware.txt` 和最终 target-files 为准。其他基带、LK、TEE 等固件不由当前系统包替换。vendor_boot 由本次源码构建，包含 generic init 与 Recovery 片段。

构建入口不扫描或重验 vendor receipt；它在构建后校验最终 target-files/OTA 分区、时间戳、VINTF、OTA/payload 签名和包内 SELinux 策略。默认输出 `out-gold-standard/gold-build-records/<id>/result.json`，以终态和验证日志为准。没有单独安装的 repo 命令时使用源码自带官方 Repo 启动器。重写可变 OTA 前会保留已有日期硬链接的内容，避免覆盖历史候选。

冻结候选实际目录为 `/srv/build/gold/releases`，8 个既有候选已整体移出活动输出，14 个 ZIP 重读哈希均匹配原始记录。后续完整冻结目录直接写入此入口下新的 `<时间-提交>`，不改活动 OUT_DIR；包不能与会被覆盖的输出建立硬链接。用 `tools/index-candidates.py <候选根> --verify-hashes` 更新清单，索引不代替原有验证器与实机验收。路径与归档规则见 [LAYOUT](LAYOUT.md)。

Gold 清单检查按 aapt2 实际输出层级提取 activity 子树，不能假定固定缩进；权限不得从相邻 service 或 activity 借用。若 Android 构建和签名等检查已通过，但后续检查器有经回归测试确认的误判，应保留原入口失败 result／日志，只在 Android 输入及包哈希均未变时单独记录修正后的完整复验；冻结时同时保存原检查器与新版工具，并独立复验冻结包。不能修改旧 result 的退出码或跳过原门禁。2026-09-21 r2 的实例见 mainline-convergence validation 和 `jobs/gold-mainline-20260920/functional-r2-closure.json`。

Android 验证通过后，在科研机用同次构建的 `aapt2` 复查 Gold 组件和已编译资源：

```sh
python3 /srv/build/gold/project/tools/check-gold-package.py \
  --target-files out-gold-standard/target/product/gold/obj/PACKAGING/target_files_intermediates/lineage_gold-target_files.zip \
  --aapt2 out-gold-standard/host/linux-x86/bin/aapt2
out-gold-standard/host/linux-x86/nativetest64/gold_health_units_test/gold_health_units_test
```

以上命令在 Android 源码根执行。Health 测试需构建时附加 `--extra-target gold_health_units_test`；它在 Linux 主机执行，不访问手机。振动契约测试生成在 `data/nativetest64/vendor/gold_vibrator_contract_test/`（以及对应 ARM 目录），仅生成测试程序不能记作运行通过。包内容检查也不能代替 overlay 生效和硬件验收。

运行振动契约测试时，普通 shell 可能无权读取 vendor 的 AIDL 库。将同次构建、对应 ABI 的测试 ELF 和 `vendor/lib64/android.hardware.vibrator-V1-ndk.so`（ARM 对应 `vendor/lib/`）临时放到独立的 `/data/local/tmp/` 子目录，以该目录作为 `LD_LIBRARY_PATH` 运行，随后删除。这四项契约测试不驱动马达，无需改变系统库、文件标签或 SELinux；仍需另验实际振动。包内容检查现在也要求标准 IMS feature XML，避免 APK 已打包但框架跳过 IMS 初始化。

Power 构建附加 `gold_power_requests_test gold_power_nodes_test`。无参数运行是主机／设备上的确定性测试，不驱动硬件。`gold_power_nodes_test --hardware` 是短时写入探针：只能在确认没有其他节点写入者、已受控停止 Power HAL 并核对基线后运行，结束后必须恢复服务并读取复位状态。不能把 root 探针当作 HAL 的 SELinux 权限验收。

框架策略对照通过 userdebug/eng、UID 0 专用的 `dumpsys android.hardware.power.IPower/default --set-strategy LAUNCH INTERACTION` 设置，两个参数均为 0..60，默认 0。调试入口依据只读 `ro.build.type`，因为当前 Lineage 上游在已鉴权的 userdebug 中也设置 `ro.debuggable=0`；不改变全局属性或正常系统 ADB 鉴权。由拥有属性的 vendor HAL 写入，不能给 shell/su 新增跨分区属性写权限或把属性加入 neverallow 豁免。受控重启 Power HAL 后核对框架能力重新发现、参数和真实动作；对照结束同样设回 `0 0`、重启并验证复位。HAL 重启后保守等待框架重新报告显示状态，必要时在授权范围内熄屏再唤醒，确认 enabled=1 后开始试验。此调试命令不放宽普通资源请求的温控／省电／屏幕状态限制。

`gold_power_nodes_test --client` 通过已安装的 `libmtkperf_client_vendor.so` 发起请求，不直接写节点；它检查两个 uclamp 请求的聚合、更新、独立释放、超时，以及共享显示 idle、未知资源和越界时长的明确拒绝。只在屏幕亮起、温控正常、关闭实验框架 boost、无媒体等竞争负载时运行；基线被占用则退出。此探针要在对应候选上执行，再核对 HAL 域、AVC、`dumpsys android.hardware.power.IPower/default` 的有界调用记录和节点复位。仍须单独覆盖真实媒体调用、进程退出、服务恢复及可比的启动／帧时间／能耗；生成探针或通过主机测试不表示这些项目已通过。

`--client-exit` 申请 2000 ms 的 uclamp=10 后主动退出且不调用 release；协调者应记录进程退出时间，并确认 HAL 在超时之前恢复 0，区分所有者回收和普通超时。`--client-restart` 输出 READY 后最多等 10 秒；协调者受控重启 `vendor.power-hal-gold`，确认新 PID、屏幕／温控许可及节点复位后向探针标准输入写 `G`。探针要求旧 Binder 返回传输错误，然后用独立新请求验证旧 C 句柄不能释放新 HAL 的票值。两种探针仍须没有竞争负载，完成后确认 0 票值和服务恢复。探针退出码不替代协调者对条件和动作的记录。

`tools/build-device-probe.py --probe performance --android-root <源码根> --android-out <唯一输出> --output <新的专属测试目录>` 在科研机用已有 JDK／SDK／aapt2／d8／apksigner 编译 `tests/android/GoldPerfProbe/`，只生成临时测试 APK，不修改产品源码或镜像。`--probe hardware` 同样生成 `GoldHardwareProbe`，验证自己创建的 EC／RSA／AES 密钥运算、安全级别及删除，逐项请求实际支持的显示模式，读取有效状态栏尺寸并展示横竖屏合成画面；默认硬件模式不请求认证绑定密钥、远程证明、相机或网络权限；独立security/Auth入口的范围见下文。两个包的 `testOnly=true`，安装前确认同名包不存在，核对源文件和 APK 哈希；保留安装后 APK 读回哈希，结束时卸载本次包。

性能对照入口是 `tools/measure-power-strategies.py`，参数明确指定 `--adb`、`--serial`（可为网络 transport）、`--hardware-serial`、`--incremental`、`--apk-sha256` 和新的 `--output`。先取得设备操作许可、完成网络 ADB 并确认 USB／其他充电均断开；入口再次核验身份、Enforcing、温控 0、省电关闭和默认策略。默认采集 12 组冷进程启动与 4 组各 60 秒滚动，0／20 策略按 AB／BA 交替；只 force-stop 自有合成应用，保留文件缓存、固定窗口亮度 0.35、记录真实滑动次数。首先实读框架启动造成的 uclamp 投票与释放，退出路径经 HAL 的 root Binder 入口恢复 0／0 并重启核验；异常时必须另核对恢复结果，不把进程退出当作恢复成功。

用 `tools/analyze-power-strategies.py <采样目录> --output <结果.json>` 验证样本哈希，排除起始温度差超过 0.5°C 或刷新率不一致的配对。帧统计去掉前后各 2 秒，以每次运行而非每帧作为比较单位；电流／电压积分是电池侧估算，设备电量计可能延迟跳变，不能用短时 charge_counter 差或单次跑分证明节能。帧与电池使用不同单调时钟，分析不能混减时间戳。原始样本和截图留私有目录，Git 记录脱敏统计及方法。一个合成应用和少量配对只能支持有边界的策略选择；未证明收益时保持默认 0，不据此宣称所有应用等效或整机续航通过。

`tests/android/GoldMediaDecodeProbe.java` 是有 20 秒期限的硬件解码调用者探针，仅读取明确提供的本地测试片段，不读用户媒体或联网。可在科研机以现有 JDK 的 `javac --release 8 -cp prebuilts/sdk/current/public/android.jar` 编译，用同树 `d8 --min-api 35 --lib prebuilts/sdk/current/public/android.jar --output <独立测试目录> <classes.jar>` 生成 dex（PATH 包含该 JDK 的 bin）；临时推送到专属 `/data/local/tmp/` 后，`CLASSPATH=<classes.dex> app_process /system/bin GoldMediaDecodeProbe <测试片段>` 执行。要求实际组件为 `c2.mtk.*`、至少一帧且收到 EOS，退出后删除自己的 dex／测试片段。保存同期 HAL 调用记录及 AVC，不能把无渲染解码耗时作为播放帧率或能耗成绩。

同一探针支持 `--roundtrip <专属测试目录> <1..20轮>`：每轮用 MTK AVC 编码器生成 24 帧 640×360 的合成 YUV，使用实际 plane stride 写入，封装到独占临时文件后再硬件解码，要求编码／解码帧数和 EOS 一致。每段排队循环限 20 秒；协调者还应使用外层进程超时，覆盖组件创建／释放可能阻塞的情况。它不读取用户媒体，每轮清理自己的片段；异常中止后由协调者清理专属目录。服务冷启动后的第一轮和同进程多轮分别验收，并监测 Codec2 服务 PID、原始故障日志和 AVC；客户端内部重试导致 PID 变化，即使探针返回成功也不能通过稳定性验收。

已授权的 Wi-Fi 重连可使用 `tests/android/GoldWifiReconnect.java`，沿用上述 javac／d8 准备方法。先用 `cmd wifi list-networks` 核实目标是用户指定的已保存网络，再以临时 adb root 执行 `CLASSPATH=<dex> app_process /system/bin GoldWifiReconnect <network-id>`。它按方法名调用当前框架的网络选择接口，不读取或替换凭据，不强制网络验证结果。`SELECTION_REQUEST_ACCEPTED` 仅表示请求已受理，必须另验关联、DHCP、联网、自动重连和网络 ADB。若框架因互联网探测失败禁止自动连接，要把显式重选与自动恢复分开记录，不能用前者冒充后者；结束后删除自己的 dex。

`tests/android/GoldConntrackProbe.java` 沿用相同 javac／d8 方法，参数必须是 `pm path com.android.networkstack.tethering` 返回的已安装 APEX APK 路径。它加载该包的实际 conntrack parser 和 event 类，用合成 netlink 数据覆盖 TCP 状态传递、缺字段和畸形属性；不打开网络 socket、不改配置或 BPF map。记录 APK／DEX 哈希与退出码。解析测试不能替代 BPF 双向规则删除、真实连接回收或热点验收。

`tests/native/RecoveryCacheProbe.cpp` 是 Linux 主机专项测试，链接**实际合并**的 `bootable/recovery/fuse_sideload/fuse_sideload.cpp`、`system/libbase/stringprintf.cpp` 和宿主 SHA-256 库。科研机现有 `g++ -std=c++17 -O2 -pthread -Wno-attributes`，include 为 Recovery 的 `fuse_sideload/include`、`otautil/include`、`system/libbase/include` 和 BoringSSL 头目录，链接 `/usr/lib/x86_64-linux-gnu/libcrypto.so.3` 及 `-Wl,--wrap=malloc,--wrap=free`。显式传入专属测试目录，以 root 运行；每轮只在该目录新建随机 FUSE 挂载点，退出时清理。测试完整 OTA 大小的合成文件、32 MiB 缓存上限、O_DIRECT 强制的淘汰后重读、篡改拒绝及一次可控 malloc 失败。记录编译命令、源码哈希、实际缓存分配峰值、宿主 RSS 和剩余挂载；宿主 glibc 结果不能冒充 Android Scudo 或手机实际侧载峰值。

Codec2 的 AIDL 服务入口由 `device/xiaomi/gold/codec2/` 编译，继续调用匹配 Global 的 MTK codec store／编解码库，保留原有服务路径、身份和唯一 AIDL 声明。固定原厂入口在 0x3c2c 只分配 336 字节，当前 `libcodec2_aidl` 的 `ComponentStore` 实际需要 352 字节；实机首次编码已在组件表插入处崩溃。因此不能再把原厂可执行文件直接当作当前平台 ABI 兼容输入，也不能手工改一个分配常数替代源码编译。原 seccomp 规则继续生效，仅按实际崩溃报告被二次 SIGSYS 中断的证据追加只读 `uname`。验收需覆盖服务冷启动后的首次编码、多次创建／销毁及解码，核对 PID、信号与日志；客户端自动重试后成功不算无崩溃通过。

在已有明确设备授权内，正常系统的标准 `update_engine_client` 可以安装已签名的完整 A/B OTA，避免为升级临时进入旧 Recovery。首先核对显式 ADB 序号、gold 身份、当前槽位／incremental、剩余空间和电量、签名证书与已装 `otacerts.zip`、snapshot state none，以及 `timeout 2 update_engine_client --follow` 回调的 `UPDATE_STATUS_IDLE (0)`。该只读跟随因超时退出 124 属于预期；此版本没有 `--status` 参数。加密用户未首次解锁时，共享存储保留文件只能记作待核验，不能误报为丢失。

从已核验 OTA 中读取未压缩的 `payload.bin`、`payload_properties.txt` 和 OTA metadata。payload 偏移必须根据 ZIP 本地文件头中的文件名／extra 长度计算，并核对 metadata 的 property-files；不是固定偏移。metadata 文件包括 CrAU v2 的 24 字节头、manifest 和 metadata signature；属性里的 METADATA_SIZE 不包括签名，单独核对 METADATA_HASH。将完整 OTA 和 metadata 放入专属 `/data/ota_package/` 子目录，采用 system:cache、目录 0750／文件 0640、标准 ota_package_file 标签，并在设备端复核完整 OTA SHA-256。只读适用性命令是 `update_engine_client --verify --metadata=<metadata文件绝对路径>`；`--payload` 不用于 verify。

适用性、身份和空闲状态确认后，使用 `update_engine_client --update --follow --payload=file://<OTA绝对路径> --offset=<已验证偏移> --size=<已验证大小> --headers=<原始四行payload属性>`；协调程序须用参数数组或安全引用保留真实换行，不重写签名／镜像。保存客户端 `kSuccess(0)`、UPDATED_NEED_REBOOT(6)、daemon 最终分区哈希和 postinstall 结果，再重启预期非活动槽。中断时先核对服务状态与已有任务，不盲用 reset_status、cancel 或重复 update。启动后单独核对 build incremental、稳定 boot_completed、Enforcing、data/persist、快照合并、保留文件及最终镜像字节范围的分区回读；安装成功与原镜像启动、Recovery 往返、硬件验收分别记录。

userdebug 允许上游调试域；不能等同于全局 permissive。正式 user 包需要无 permissive 域；不允许跳过 neverallow、缺依赖/ELF 校验或关闭 AVB。测试证书不构成正式发行签名验收。

源码编译、包验证、Recovery 安装、分区回读、稳定开机、硬件和保数据 OTA 分别记录。当前结论见 [STATUS](STATUS.md)。


当前非 IMS 修复的包检查同时核验双击唤醒资源／Power 路径／设备标签、NetworkStack 的真实 HTTPS 地址、原厂 attestation 专用属性；实际镜像读取覆盖新增 RRO 和 SystemUI。OpenEUICC/eSIM 已退出支持，检查 target-files 中不存在 APK、odex、权限、feature 或 lpac-jni 残留，并直接检查 system_ext 镜像的旧安装路径不存在。包内存在不等于运行通过。双击协议的 Linux 主机定向测试为 `g++ -std=c++17 -Wall -Wextra -Werror -I device/xiaomi/gold/power tests/native/TouchWakeTest.cpp -o <专属目录>/touch-test`，执行该程序只调用系统调用替身，不访问手机。安装后仍需通过正式 Settings→Power Binder→Enforcing 域测试开关、物理双击、服务与设备重启恢复，不能用 root 直接 ioctl 代替。

设备 Recovery 缓存测试可用 test-key 签名、OTA 大小的无 payload／updater fixture，令 pre-device 为专用不匹配标识；要求完整签名验证通过，再在元数据检查被拒绝且从未启动 updater。ADB transfer exit 0 只证明传输。RSS 观察者须在 sideload 切换停止 adbd 后仍存活且有边界；只分离自己的观察进程，不改 Recovery／minadbd 控制组或 SELinux。结束核对原槽位／版本、挂载、快照与 canary。这是缓存／验签的定向证据，不能记作完整 Recovery OTA 安装通过。


WPA3 SoftAP 的当前Gold门禁要求实际编译的 `VENDOR/overlay/WifiOverlay/WifiOverlay.apk` 中 `config_wifi_softap_sae_supported=true`，并从最终vendor镜像读取同一APK比较字节；新增后预期关键文件39项。其能力值有同基线原厂RRO依据；包通过不等于热点真实启动或客户端SAE认证通过。

空间受限时，只能在源码锁空闲、构建停止且独立冻结包重读哈希一致后移除同次可变输出包副本，保留精确路径映射；不得清理唯一输入、缓存、swap或历史候选。2026-09-21的两种包/三个可变路径见jobs/wpa3-active-package-duplicates.json（实际位于gold-mainline-20260920下）。OverlayFS合并视图到releases直接rename已实测EXDEV。后续逐包复制到同一冻结staging，重读SHA-256并fsync后才移除该包在可变输出下的全部硬链接，记录来源/去向并独立重验；不能保留会被重写的硬链接或链接回旧外层路径。冻结JSON保持当时事实，后来的安装/实机证据另存聚合validation。

2026-09-22 eSIM移除首轮在 target-files ZIP 压缩时因 ENOSPC 失败，Android耗时01:34:45，入口exit1；同时运行的OTA任务随后结束并清理临时ZIP。主线入口现将打包分为先 `m -j2 bacon`、再 `m -j2 target-files-package`，避免两个压缩/签名高峰重叠；每阶段仍jobs2，第二阶段失败或任一产物门禁失败均不得记完成。两阶段共用同一源码锁、OUT、lunch和BUILD_DATETIME，最终仍校验全量OTA/target-files的签名、分区、VINTF、SELinux和Gold内容，不修改Android源码或关闭检查。

顺序打包的r2仍在OTA zip2zip临时副本阶段ENOSPC，证明先前峰值估算不足。新增最小build/make补丁：设置 `GOLD_OTA_TMPDIR` 时仅OTA命令的TMPDIR改用该私有目录，未设置则保留Soong默认值。主机入口核对目录归属/0700/非链接并记录输入；Gold实际镜像检查也使用同一临时盘。当前科研机通过本次job在既有系统盘/tmp下创建专属目录，独立guard在所有构建进程退出后校验marker并清理；不改OUT、不改Soong源码、不挂载第二输出。nsjail源码本来就以读写方式绑定/tmp，无需放宽沙箱。实际合并Make宏的默认、显式路径和含空格引用已定向验证。

移除版r3的Android两阶段及标准产物校验成功，但最终Gold门禁正确拒绝实际system_ext中的旧JNI悬空链接。固定Soong的普通旧文件清理使用os.Stat，可能跳过宿主不存在的Android绝对链接目标。`device/xiaomi/gold/CleanSpec.mk` 以标准一次性步骤仅迁移Gold旧eSIM安装产物，并失效system_ext镜像/清单和target-files构建清单，让原生规则重建；不修改平台clean版本，不执行全局clean或installclean，不删除完整输出。新增文件已纳入167项输入审计，包内六个退役路径必须继续全部缺席。

移除版r4补充覆盖了target-files图片生成阶段：`add_img_to_target_files`也使用可选`GOLD_OTA_TMPDIR`。前版只覆盖OTA与最后镜像检查，漏算build_image合并root/system时约1GB临时副本；本轮以原输入、原容量和inode参数在既有系统盘实测成功后修复。该变量现用于target-files镜像构造、OTA打包及最终镜像检查，保持唯一OUT；未设置时保留原生Soong临时目录。真实Make命令的默认、空值和带空格私有目录共六项通过，所有临时内容仍由独立guard在构建终态后清理。

2026-09-22 r5历史诊断：BUILD_DATETIME固定仍不足以约束上游Lineage的实时UTC日期；两次make跨零点导致product与Recovery版本属性不同，最终分区门禁已真实拒绝。固定vendor/lineage提交d747e9abec858434d4967eb5fa9cd3e87c5cc7b0上的最小补丁使两种LINEAGE_BUILD_DATE格式均取BUILD_DATETIME；未设置或空值保留原行为。包检查增加PRODUCT/etc/build.prop与VENDOR_BOOT/RAMDISK_FRAGMENTS/recovery/RAMDISK/prop.default日期及相互一致性检查，不能只比较顶层OTA时间戳。105项主机测试与7项真实Make时钟/时区检查通过。继续原OUT、jobs2顺序打包及全部原门禁。宿主自动更新的精确临时服务重启保护应在后续job启动前准备，任务结束核对并清理；不得全局停用安全更新。

2026-09-22 r6配置检查补充：直接读取BUILD_DATETIME被实际Kati判为obsolete；此前GNU Make检查覆盖不足，失败记录保留。现从Soong已提供的BUILD_DATETIME_FILE读取epoch；同文件内更晚才定义的BUILD_DATETIME_FROM_FILE不能用于version.mk包含点。105项主机测试、8项实际Make定向检查及真实Android lunch/dumpvars通过（日期20260921），168项输入仅version.mk变化；r7随后完整构建、日期与原有全部包门禁均通过，设备验收仍独立。


2026-09-22 r7 于12:57:15 +08入口 exit 0；bacon 01:15:23、target-files-package 01:36:32 均 exit 0。168项合并输入、14个payload分区与target-files镜像全部一致；签名、VINTF、SELinux、Gold内容与版本日期门禁通过。真实镜像核对38项文件，system_ext六个退役路径缺席，eSIM支持为false，WPA3 SAE编译资源为true。product与Recovery均为UTC epoch对应的20260921版本日期。独立guard12:57:20退出，VM实读0/zbud/N/Y，无OOM，本轮ZIP工具、OTA scratch与精确needrestart配置均已清理；宿主zip/unzip仍未安装。

构建后主机收尾已纳入主线 `tools/host/vm-guard.py`、`build-invocation.py` 与统一入口：启动前准备仅匹配本轮build/guard完整名称的临时needrestart配置；守护单例锁、服务与递归cgroup状态、源码锁共同约束恢复，重启接管保留原始VM值，外部值变化保留并明确报恢复未完成；运行期终止信号不能提前恢复。每个systemd InvocationID在jobs/build-invocations下独立建档，禁止覆盖，记录真实退出/外部信号；Android输入/result关联同一ID。117项主机测试通过。短服务实测覆盖SIGTERM延后、并发守护拒绝、SIGKILL后接管且测试服务不重启、最终VM和精确配置恢复、PID1退出与invocation对应；实际构建入口的缺unzip预检失败也独立留档且未创建Android构建。这次主机改动后168项Android输入及10个受管项目逐字节/提交不变，不另编ROM，冻结工具仍为构建时70c2ec4版本。

`vm-guard.py`默认从同一物理布局定位source，其他已核验位置需显式`--source-tree`。准备步骤必须先于两个服务；不启用全局needrestart排除，也不关闭安全更新。启动失败或守护异常时先核对实际服务/cgroup和原记录；仅守护需要接管时使用同一unit与record重新启动，不能重启Android构建。`--restore-only`同样拒绝活动服务或被占用的源码锁；确认构建全部停止后才用它恢复原值和精确配置。若其他管理者改变了VM值或配置内容，工具保留变化并报告未恢复，不伪称成功。

每次统一入口的systemd执行在`/srv/build/gold/jobs/build-invocations/<InvocationID>.json`单独记录。外部信号记interrupted，即使PID1记录外部stop成功也不能算构建成功；SIGKILL来不及写终态的running记录保持未完成，后续启动使用新的ID。终态需同时核对对应Android result、入口退出及PID1的UNIT/InvocationID/开始后时间。guard只有服务/cgroup稳定空闲且取得源码锁才恢复，退出后实读0/zbud/N/Y。临时zip/unzip和OTA目录仍按本次job的精确路径、归属、marker与哈希记录清理，不能把其他轮保留的失败包包含进去；主线guard只自动移除自己记录且字节一致的needrestart配置。

2026-09-22设备安装记录：冻结70c2ec4的全量OTA按上述标准update_engine流程完成B→A保数据更新，手机端包哈希、证书/适用性、安装器及独立各14项最终分区哈希一致。A / 1790008554正常启动、Enforcing/data/persist/snapshot none/两canary通过。手机端OTA暂存已清理，ADB已恢复UID2000。本次没有重编ROM、修改冻结包或做Recovery OTA；详细边界见STATUS及candidate_70c2ec4_device。

设备网络验证前必须同时核对实际默认/活动数据订阅、逐订阅mobile_data值及实际上行；旧全局mobile_data=0不能替代双卡判断。本次授权仅中国联通，漫游eSIM不可操作。USB线缆不稳定时，正常系统内应及时连接鉴权网络ADB并核对同一硬件身份，后续优先网络控制；端点与硬件标识只存私有记录。网络ADB依赖当前热点，不能因此随意切热点或重启设备。TCP验收须区分FIN、RST、内核状态/过期和两方向规则，记录采样间隔及观察动作，不能只凭解析器测试或瞬时规则存在判为全部通过。

`tests/android/GoldConntrackObserver.java`沿用上述javac/d8方法，是有1..180秒期限的只接收netlink多播事件探针。参数为已安装Tethering APEX APK、明确的测试客户端/服务端IPv4、自己的测试源端口列表和期限；需要已授权的临时ADB root，不发送conntrack查询/更新/删除，不写BPF map。使用已安装APK的真实parser与事件过滤器，记录原始消息是否被识别为建立/删除事件，可区分内核未发通知与框架丢弃。输出含受控连接原始字节，只落0600私有文件，不进Git。协调者必须另观察真实双向规则与终态；读取/proc连接表后的清理时序不冒充自然到期。实际70c2ec4运行exit0，观察到TCP状态仍ESTABLISHED的合法DELETE被接受并删除两条规则；另有自然RST残留复现，探针成功不等于BPF全面通过。执行后删除本次DEX/专属目录、恢复普通鉴权网络ADB；不改SELinux或网络设置。

## 已有构图上的定向APK增量

仅在此前完整构建成功、当前修改限于现存源文件/资源时使用：

```sh
/srv/build/build-gold.sh --module-apks \
  --baseline /srv/build/gold/jobs/gold-mainline-20260920/no-euicc-r7-source-build-inputs.json \
  --record /srv/build/gold/jobs/<本次唯一记录目录> \
  DeviceDiagnostics FrameworkResOverlayGold
```

入口仍由原资源限制的systemd服务及独立VM guard包裹，持同一源码/OUT锁；核验两次源审计、固定项目提交、允许的改动集合、OUT/.top与Ninja环境，保存既有图及环境哈希。产品/Android.bp/新增模块/其他配方变化必须回到标准Soong流程，不能用旧图绕过。此模式不需要本轮未使用的宿主zip/unzip，不产生OTA或ROM验收；APK经签名验证后独立复制/哈希/fsync到record。当前MPEG4新prebuilt已改变提取配方，不能对这个后续增量误用仅三个源文件变化的旧baseline。

本轮13项Ninja任务125.73秒exit0，DeviceDiagnostics通过PackageManager普通更新并按实际活动APK回读hash；FrameworkResOverlayGold是static，普通ADB及root均拒绝升级。root不会解除静态RRO、只读EROFS vendor或非rebootless Tethering APEX的生命周期限制。不要因此重启framework/APEX、关SELinux、remount或改AVB。新的vendor插件后续随正常增量产品构建和受控OTA验证。

`build-device-probe.py --probe diagnostics`用公开AOSP platform测试证书构建target com.android.devicediagnostics的instrumentation，以自有protobuf验证真实Activity，不改全局电池值；执行`am instrument -w org.lineageos.gold.diagnosticsprobe/.GoldDiagnosticsInstrumentation`后核对结果JSON的failed/count并卸载探针。`--probe hardware`生成的自有应用以`--es mode security`选择普通应用证明测试；输出错误链可能含请求参数，原始输出只入0600私有证据。未设锁或未获本人认证时不替用户配置认证。`GoldMediaDecodeProbe --extended <专属目录>`依次测HEVC与MPEG4，崩溃也必须收集服务日志并清理自己生成的文件，不循环触发已知崩溃。

`GoldConntrackQuery.java`仅对最多8条明确的自有IPv4/TCP四元组发CT_GET（无dump、timeout更新或删除），检查响应序号与实际四元组，使用已安装Tethering的真实解析器；需要已获准的root。query可能触发内核对已过期项的回收，记录观察边界，不能把它说成无观察自然到期。所有地址和端口留在私有日志。`GoldDozeOverlay.java`只用系统OverlayManager注销固定命名的自有临时覆盖，用于有恢复方案的短时验证；注销和设置复位后才交还。

## KeyMint认证和属性定向探针

`--probe hardware`现在还构建 `GoldAuthActivity`，使用普通公开AOSP testkey，非platform权限；testOnly=true、allowBackup=false不变，debuggable仅供run-as读取自己的结果。先确认同名包属于本次测试、手机空闲且用户已经自己配置安全锁屏；不替用户设锁或索取PIN。通过已核验身份的优先网络ADB安装该APK并启动：

```sh
adb -s <已核验的transport> shell am force-stop org.lineageos.gold.hardwareprobe
adb -s <已核验的transport> shell am start -n org.lineageos.gold.hardwareprobe/.GoldAuthActivity
adb -s <已核验的transport> shell run-as org.lineageos.gold.hardwareprobe cat files/auth-result.json
```

等待初始17秒认证过期，再请本人操作系统BiometricPrompt。探针创建的EC/AES均为15秒凭据授权：认证前拒绝、认证后真实运算/篡改拒绝、过期再次拒绝分别记录。核对KeyInfo安全级别、hardwareEnforced认证标签、挑战和链内签名；`completed`不能代替这些字段，链内签名不等于信任根/吊销验收。核对`owned_keys_deleted`，结束后卸载自己的包。切换MainActivity的`--es mode security`前同样force-stop本测试包，避免已有Activity只在onCreate读取extra而误把一般模式结果记为证明测试；不停止用户应用。

`tests/android/GoldAttestationParameters.java`使用同次OUT的framework-minus-apex combined/framework.jar及公开SDK编译，再由既有d8生成DEX，通过普通shell/app_process调用KeyStore2。只访问Domain.APP下UUID命名的自有别名，不接受用户提供的身份值，不请求IMEI/serial/MEID、唯一ID或更改provisioning。无属性为控制组，五个当前非唯一属性逐项及组合，再对正常平台属性组合；输出原生错误码，finally删除自己的密钥。将DEX放本次专属目录，执行后按哈希核对并删除它及空目录，原始错误/证书留在0600私有目录。

如需诊断RKP，先核对实际ShellCommand实现：本轮的`cmd remote_provisioning csr --challenge <随机挑战的base64> default`只用空keys数组在本地生成CSR，不调用`certify`或联网申请证书。CBOR包含可识别设备的DICE材料，必须仅在私有本机校验；核对挑战和COSE链内/请求签名并做坏签名拒绝，公开记录只放非唯一属性及布尔结论。签名后的当前DeviceInfo不是工厂证明ID查询接口，不能据此重置TEE或猜写属性。

### 9月22日晚完整ROM构建准备

AOD覆盖和新增MPEG4 vendor模块使用正常产品入口，保留顺序bacon/target-files-package与同一epoch。`followup-r1`任务在启动前要求数据盘至少7GiB、系统盘至少12GiB；两份最终包、模块/镜像变化与构图峰值留有余量。所有打包临时副本使用本次0700系统盘scratch；ZIP工具只临时认证解包。独立job wrapper直接调用主线vm-guard的单例/原值接管/精确needrestart保护和invocation流程，终态后核实VM恢复，才按本轮owner/marker清理工具与scratch；历史保留区不属于其清理范围。没有自动刷机或手机重启步骤。

### 9月23日 MPEG4 ABI续编

followup-r1的bacon在01:13:50退出1，第二阶段未运行；原实际invocation和独立guard成功恢复在followup-r1-terminal.json。源码按四项真实符号版本冲突修复后，followup-r2继续原OUT及epoch1790091429，不清理或跳过检查。主机回归环境指定GOLD_ANDROID_TREE为合并源码、GOLD_MPEG4_STOCK_LIBRARY为已锁定Global原厂ARM插件、GOLD_MPEG4_ELF_COMMAND为真实失败命令的JSON数组；tests/test_mpeg4_runtime.py要求三者全部提供，否则明确跳过这三项实文件测试。本次全部127项运行且通过，没有跳过。包门禁同时记录原输入和修复后哈希；构建完成仍需全部签名/VINTF/SELinux、14分区一致性和39项实际镜像文件检查。

followup-r2终态为9月23日03:16:41入口exit0，bacon01:10:26、target-files-package56:41，真实InvocationID ab447bf1dced4329b97c84373ba23f86。独立guard03:16:47成功，0/zbud/N/Y与临时内容缺席现场核对。169输入/127主机测试、14分区/39实际文件及全Android门禁通过；全量包已独立复验并冻结到 `/srv/build/gold/releases/20260923-090824-60e90a7`。冻结保存全部228项主线受管文件、169项合并输入、Repo清单、同次检查工具/库及job/invocation记录。后续重新构建继续使用唯一OUT，安装从releases候选读取，不依赖已移除的可变ZIP别名。此userdebug/test-keys候选未作正式发行密钥或设备验收。

2026-09-29补充：受限--module-apks现允许GoldStatusBarOverlay既有dimens.xml资源变化，所有源/图/锁/签名约束不变。4项Ninja84.59秒、两个Doze布尔值和21项相关回归已过，静态RRO未在线升级。新的完整ROM必须校验SystemUI DOZE与DOZE_SUSPEND两个编译值，并在实际system_ext核对覆盖APK，实际文件检查40项。手机已装60e90a7；当前禁止蜂窝数据、电话、短信和Mac网络/钥匙串操作，旧联通数据授权不适用于本次。

2026-09-29完整ROM增量已完成：8f01656、BUILD_DATETIME1790692970，两阶段和全部门禁通过；169输入、14payload、40实际文件，冻结/srv/build/gold/releases/20260929-231337-8f01656并独立复验。VM与三类临时内容已恢复/清理；没有第二OUT、clean或产物手工重签。冻结工具保持构建时版本。
