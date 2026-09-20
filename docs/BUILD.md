# 构建与验证

主路径：固定源码 + Global 官方提取输入 → 标准 `bacon target-files-package` → Android 官方验证工具。执行环境为原生 Linux x86_64；Mac 只做源码审阅和原生主机测试。

## 日常增量

科研机复用 `/srv/build/migration/gold-architecture-20260914/source` 和其中的 `out-gold-standard`，不 clean，不创建第二份完整输出。先确认 source 是正确 overlay 挂载且没有另一构建，再以 `goldbuild` 用户执行。

科研机 `/srv/build/build-gold.sh [extra_targets...]` 统一指向本仓库 `tools/host/build-research.sh`：以 goldbuild 账户复用现有输出、执行完整构建与产物校验。额外参数用于同时编译模块或测试，不省略完整 OTA。底层入口也可直接调用：

```sh
export USER=builder LOGNAME=builder BUILD_USERNAME=builder
export USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
export CCACHE_DIR=/srv/build/ccache-gold-betterr
export GOGC=50 GOMEMLIMIT=10GiB GOMAXPROCS=4
python3 /srv/build/migration/gold-architecture-20260914/project/tools/build-source.py \
  --tree /srv/build/migration/gold-architecture-20260914/source \
  --lunch lineage_gold-bp4a-userdebug --out out-gold-standard \
  --jobs 2 --build-datetime UNIX_TIMESTAMP --execute
```

`UNIX_TIMESTAMP` 使用本次构建时间。保留旧输出的 builder 标识用于避免无意义地重算构建图；执行账户仍为 goldbuild。可附加 `--extra-target gold_vibrator_contract_test`，只编译振动契约测试程序，不代表该测试已经运行。

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

userdebug 允许上游调试域；不能等同于全局 permissive。正式 user 包需要无 permissive 域；不允许跳过 neverallow、缺依赖/ELF 校验或关闭 AVB。测试证书不构成正式发行签名验收。

源码编译、包验证、Recovery 安装、分区回读、稳定开机、硬件和保数据 OTA 分别记录。当前结论见 [STATUS](STATUS.md)。
