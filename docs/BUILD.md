# 构建与验证

主路径：固定源码 + Global 官方提取输入 → 标准 `bacon target-files-package` → Android 官方验证工具。执行环境为原生 Linux x86_64；Mac 只做源码审阅和原生主机测试。

## 日常增量

科研机复用 `/srv/build/migration/gold-architecture-20260914/source` 和其中的 `out-gold-standard`，不 clean，不创建第二份完整输出。先确认 source 是正确 overlay 挂载且没有另一构建，再以 **root（实际 UID 0）** 执行。

科研机 `/srv/build/build-gold.sh [extra_targets...]` 统一指向本仓库 `tools/host/build-research.sh`：直接由 root 执行，不再切换专用编译账户。HOME 固定为 `/root`，ccache 实际目录为 `/root/ccache`，24 GiB swap 位于数据盘 `/srv/build/gold-build-swapfile`。额外参数用于同时编译模块或测试，不省略完整 OTA。底层入口也可直接调用：

```sh
export USER=builder LOGNAME=builder BUILD_USERNAME=builder
export HOME=/root
export USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
export CCACHE_DIR=/root/ccache
export GOGC=50 GOMEMLIMIT=10GiB GOMAXPROCS=4
python3 /srv/build/migration/gold-architecture-20260914/project/tools/build-source.py \
  --tree /srv/build/migration/gold-architecture-20260914/source \
  --lunch lineage_gold-bp4a-userdebug --out out-gold-standard \
  --jobs 2 --build-datetime UNIX_TIMESTAMP --execute
```

`UNIX_TIMESTAMP` 使用本次构建时间。USER、LOGNAME、BUILD_USERNAME 的 `builder` 仅保留已有产物标识，真实进程 UID 是 root，HOME 是 `/root`；这些环境字符串不代表运行账户。可附加 `--extra-target gold_vibrator_contract_test`，只编译振动契约测试程序，不代表该测试已经运行。

迁入的源码仍由原账户拥有。当前 root 的 Git 配置通过 `include.path` 加载 `/srv/build/gold-git-safe-directories.config`，只信任本源码树 `repo list -p` 枚举的 1158 个项目和 3 个 Repo 元数据仓库的确切路径。没有设置 `safe.directory=*`，也没有递归更改 overlay 所有权。新增项目或迁到新路径时，应核对后更新清单；对单个已核对仓库可执行 `git config --global --add safe.directory /exact/repository/path`。科研机 Git 2.43 的 `source/*` 未通过实际检查，不能用它替代确切路径。

原有 `out-gold-standard` 的目录和文件也必须归实际构建 UID 所有：nsjail 内的映射用户不能依靠宿主 root 的权限覆盖旧 UID 的写权限。科研机已确认该输出全部位于 overlay upper，再只调整这个受管输出的所有权；未复制输出、改写文件内容或关闭沙箱。

先执行 `/srv/build/build-gold.sh --check-environment`，检查实际 UID、HOME、源码路径、输出目录归属、完整固定清单导出和缓存读写。清单导出失败也会在正常构建的 `result.json` 中留下失败记录。长期构建通过 root systemd 服务启动，保留资源上限：

```sh
unit=gold-build-$(date +%Y%m%d-%H%M%S)
systemd-run --unit="$unit" -p User=root -p Group=root \
  -p WorkingDirectory=/srv/build/migration/gold-architecture-20260914/source \
  -p Environment=HOME=/root \
  -p MemoryHigh=12800M -p MemoryMax=13G -p MemorySwapMax=20G \
  -p StandardOutput=append:/srv/build/logs/"$unit".log -p StandardError=inherit \
  /srv/build/build-gold.sh gold_health_units_test gold_vibrator_contract_test
```

swap 已在 `/etc/fstab` 持久化；对应 swap 单元依赖 `srv-build.mount`。原 `goldbuild` 账户和 `/srv/build/home` 仅保留历史内容，不再作为有效构建入口或 HOME。迁移完成后的 IMS 修正版已以实际 UID 0 完成完整构建及验证，见 [最终记录](../validation/ims-build-20260920.json)。迁移前已安装的首次候选按其原构建身份和独立 OTA 路径保留。

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

Android 验证通过后，在科研机用同次构建的 `aapt2` 复查 Gold 组件和已编译资源：

```sh
python3 /srv/build/migration/gold-architecture-20260914/project/tools/check-gold-package.py \
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

`tests/android/GoldMediaDecodeProbe.java` 是有 20 秒期限的硬件解码调用者探针，仅读取明确提供的本地测试片段，不读用户媒体或联网。可在科研机以现有 JDK 的 `javac --release 8 -cp prebuilts/sdk/current/public/android.jar` 编译，用同树 `d8 --min-api 35 --lib prebuilts/sdk/current/public/android.jar --output <独立测试目录> <classes.jar>` 生成 dex（PATH 包含该 JDK 的 bin）；临时推送到专属 `/data/local/tmp/` 后，`CLASSPATH=<classes.dex> app_process /system/bin GoldMediaDecodeProbe <测试片段>` 执行。要求实际组件为 `c2.mtk.*`、至少一帧且收到 EOS，退出后删除自己的 dex／测试片段。保存同期 HAL 调用记录及 AVC，不能把无渲染解码耗时作为播放帧率或能耗成绩。

在已有明确设备授权内，正常系统的标准 `update_engine_client` 可以安装已签名的完整 A/B OTA，避免为升级临时进入旧 Recovery。首先核对显式 ADB 序号、gold 身份、当前槽位／incremental、剩余空间和电量、签名证书与已装 `otacerts.zip`、snapshot state none，以及 `timeout 2 update_engine_client --follow` 回调的 `UPDATE_STATUS_IDLE (0)`。该只读跟随因超时退出 124 属于预期；此版本没有 `--status` 参数。加密用户未首次解锁时，共享存储保留文件只能记作待核验，不能误报为丢失。

从已核验 OTA 中读取未压缩的 `payload.bin`、`payload_properties.txt` 和 OTA metadata。payload 偏移必须根据 ZIP 本地文件头中的文件名／extra 长度计算，并核对 metadata 的 property-files；不是固定偏移。metadata 文件包括 CrAU v2 的 24 字节头、manifest 和 metadata signature；属性里的 METADATA_SIZE 不包括签名，单独核对 METADATA_HASH。将完整 OTA 和 metadata 放入专属 `/data/ota_package/` 子目录，采用 system:cache、目录 0750／文件 0640、标准 ota_package_file 标签，并在设备端复核完整 OTA SHA-256。只读适用性命令是 `update_engine_client --verify --metadata=<metadata文件绝对路径>`；`--payload` 不用于 verify。

适用性、身份和空闲状态确认后，使用 `update_engine_client --update --follow --payload=file://<OTA绝对路径> --offset=<已验证偏移> --size=<已验证大小> --headers=<原始四行payload属性>`；协调程序须用参数数组或安全引用保留真实换行，不重写签名／镜像。保存客户端 `kSuccess(0)`、UPDATED_NEED_REBOOT(6)、daemon 最终分区哈希和 postinstall 结果，再重启预期非活动槽。中断时先核对服务状态与已有任务，不盲用 reset_status、cancel 或重复 update。启动后单独核对 build incremental、稳定 boot_completed、Enforcing、data/persist、快照合并、保留文件及最终镜像字节范围的分区回读；安装成功与原镜像启动、Recovery 往返、硬件验收分别记录。

userdebug 允许上游调试域；不能等同于全局 permissive。正式 user 包需要无 permissive 域；不允许跳过 neverallow、缺依赖/ELF 校验或关闭 AVB。测试证书不构成正式发行签名验收。

源码编译、包验证、Recovery 安装、分区回读、稳定开机、硬件和保数据 OTA 分别记录。当前结论见 [STATUS](STATUS.md)。
