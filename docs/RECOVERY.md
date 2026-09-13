# 官方 6.6 基线的 Lineage Recovery

日期：2026-09-13。**以下是经过离线检查的候选构建方法，尚未验证 Recovery 启动、格式化 data、sideload 或安装后的再次进入。当前不提供已验收的终端用户刷机命令。**

## 为什么需要单独整合

普通源码生成的 vendor_boot 使用设备树原有的另一套内核模块输入。官方 OS3.0.10 vendor_boot 则包含小米 Recovery，直接将它放入 OTA 会覆盖先前安装的 Lineage Recovery。终端用户需要一套与官方 6.6 内核配套、安装后仍保留的 Lineage Recovery。

工具以已校验的官方基线组装结果为输入，保留 vendor_boot 的平台 ramdisk、init_boot ramdisk、DTB、bootconfig 及片段顺序，只替换名为 `recovery`、类型为 2 的片段，使用本轮源码构建的 Lineage Recovery。并不混入旧内核模块，也不修改官方 kernel。

这遵循 [AOSP vendor boot v4 的 ramdisk 分片结构](https://source.android.com/docs/core/architecture/partitions/vendor-boot-partitions)。结构正确仍需真实设备启动验证。

## 构建候选

在已具备 Android 主机工具的 Linux 编译环境运行，使用新输出目录和与其他组装任务共用的锁：

```sh
python3 tools/build-recovery.py \
  --source /path/to/android \
  --assembly /path/to/verified-stock-assembly \
  --lineage-vendor-boot /path/to/android/out/target/product/gold/vendor_boot.img \
  --output /path/to/new-recovery-candidate \
  --lock /path/to/shared-build.lock
```

输入必须是本仓库 `build-stock-base.py` 的 OS3.0.10 组装结果，以及匹配本轮 Lineage 构建的 vendor_boot。工具保留未修改镜像的引用，不能在归档前删除这些输入。输出中的 `vendor_boot.img` 和 `vbmeta.img` 必须成对进入后续完整 OTA；不应只替换 ZIP 内某个镜像或沿用旧 payload。

工具会重建 vendor_boot 的 AVB footer 与父级 vbmeta，并重新解包检查：

- 官方平台和 init_boot 片段、DTB 与 bootconfig 均逐字节保持不变。
- Recovery 片段与 Lineage 输入逐字节一致。
- 完整 AVB 链通过，顶层验证标志仍为 0。

默认使用 AOSP 公开开发测试密钥；可用 `--key` 显式指定自有密钥。此候选不支持重新锁定 bootloader。

## 当前结果与下一步

候选构建及上述离线检查已通过，结果见 [recovery-candidate-20260913.json](../validation/recovery-candidate-20260913.json)。带该 Recovery 的完整 OTA 正在重新打包和验证；旧完整包的哈希不代表这个新候选。

实机将单独记录 Recovery 启动、USB/sideload、data 格式化、安装完成、首次开机、再次进入 Recovery 和基础功能。格式化会清除应用、账号和内部存储文件，需先备份。现有 27 项严格 SELinux neverallow 缺口不会因替换 Recovery 自动消失。
