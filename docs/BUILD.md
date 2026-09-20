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
  --stock /path/to/prepared-stock --ims-apk /path/to/ImsService.apk
```

此步骤核验原厂镜像并提取配套 kernel、DTB、DTBO、modules 与厂商组件。日常源码修改不重做完整提取；提取配方改变时只重提取受影响部分，并重新生成 vendor 构建定义。不要直接只改生成的 Android.bp 而漏掉提取清单。

IMS 必须提供 SHA-256 为 `98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1` 的兼容输入。部分重建配方在 [IMS 说明](../vendor/xiaomi/gold/ims/README.md)，从任意原厂 APK 独立还原其完整依赖仍未闭合。

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

userdebug 允许上游调试域；不能等同于全局 permissive。正式 user 包需要无 permissive 域；不允许跳过 neverallow、缺依赖/ELF 校验或关闭 AVB。测试证书不构成正式发行签名验收。

源码编译、包验证、Recovery 安装、分区回读、稳定开机、硬件和保数据 OTA 分别记录。当前结论见 [STATUS](STATUS.md)。
