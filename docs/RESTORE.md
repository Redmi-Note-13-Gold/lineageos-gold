# 源码恢复与应用顺序

本仓库提供精确源码基线和可检查的补丁恢复入口。**不是空目录到可刷 ROM 的完成声明。** 先阅读 [集成说明](INTEGRATION.md) 中的 IMS、vendor/kernel 和 hybrid 输入缺口。

## 1. 初始化固定基线

使用已有的 Git、Repo、Python 3.9+ 和适合 LineageOS 23.2 的 Linux 构建环境。不要在已有修改的源码树上强制重置。

在新 Android 源码目录执行（`/path/to/lineageos-gold` 是本仓库克隆目录）：

```sh
repo init -u https://github.com/Redmi-Note-13-Gold/lineageos-gold \
  -b experimental -m manifests/lineage-23.2-gold.xml
repo sync -c -j8

git -C external/openeuicc submodule update --init --recursive
```

manifest 固定 1160 个项目的提交：当前构建树导出的 1158 个项目，加上经过逐文件核对的 OpenEUICC 与依赖。保留现用 TUNA/USTC 镜像来源；网络不可达时可在副本中改为对应官方源，但不要改变锁定提交。某个提交若在公开源被清理，固定 SHA 本身不能恢复已丢失对象。

固定提交不包含该项目的工作区改动；下一步才应用补丁。manifest 也不包含厂商提取生成的 `vendor/xiaomi/gold`，或目前独立保存的 `device/xiaomi/gold-kernel` 输入。

## 2. 检查并应用

```sh
python3 /path/to/lineageos-gold/tools/apply-patches.py /path/to/android
python3 /path/to/lineageos-gold/tools/apply-patches.py /path/to/android --apply
```

默认只检查，要求各目标项目位于正确基线且工作区干净，子模块版本匹配；在临时目录按顺序试应用补丁；不覆盖已存在的独立源码。`--apply` 在全部检查通过后应用 `patches/series.json` 并复制 `sources/` 到相同 Android 路径。

设备补丁后接 R3 boost restorecon 标签修复。MDDP 实验、hybrid vendor 的镜像级差异不在自动应用序列中。外部中断可能留下部分项目已修改的状态；先查看 Git 状态，保留自己的改动，不要盲目 reset 或重复套补丁。

## 3. 补齐独立输入

- 使用设备提取规则和合法持有的匹配固件恢复厂商文件；本仓库没有重新分发原厂 APK/固件。主设备树仍有 5.10 预编译内核基线依赖，当前运行 hybrid 则使用 6.6；这一步不能省略或混用。
- IMS 构建注册引用 `vendor/xiaomi/gold/ims/ImsService.apk`，需要按 [IMS 说明](INTEGRATION.md#ims--volte) 准备已校验的 payload；本仓库不包含该文件。从原厂输入恢复完整 v1/v5 依赖闭包仍未完成公开自动化。
- 检查厂商提取是否覆盖了刚恢复的集成文件。不要用提取器的输出覆盖 IMS 构建注册而不审查差异。
- OpenEUICC 的二进制依赖由固定的公开依赖仓库取得；本次已经逐文件匹配，不需要再次手动下载另一套版本。
- 按 [混合启动说明](INTEGRATION.md#混合启动与打包) 准备相互匹配的 staging 和工具输入；普通 `bacon` 尚未完成这一集成。

## 4. 构建与验收

先运行可在主机完成的工具测试：

```sh
python3 -m unittest discover -s device/xiaomi/gold/tools -p 'test_*.py'
```

还需要对应 Android 模块的编译和测试。Android View/设备侧测试不能被主机单元测试替代。构建镜像后需继续做 AVB/FEC、分区内容、刷后回读、启动和实际硬件验收。本仓库不提供通用刷机命令，以免把某次固定 A/B 布局当成所有设备的安装流程。

当前没有完成全新机器从此 manifest 到等效整包/OTA 的端到端验收。已完成与未完成的部分见 [STATUS.md](STATUS.md)。
