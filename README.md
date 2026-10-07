# LineageOS 23.2 for Redmi Note 13 5G (`gold`)

这个仓库只放构建入口：一份 local manifest 和构建机用的脚本。设备相关的代码在别处：

| 内容 | 仓库 |
| --- | --- |
| 设备树 | [Redmi-Note-13-Gold/android_device_xiaomi_gold](https://github.com/Redmi-Note-13-Gold/android_device_xiaomi_gold)，fork 自 [Dhterech](https://github.com/Dhterech/android_device_xiaomi_gold) |
| 内核（预编译） | [Redmi-Note-13-Gold/android_kernel_xiaomi_gold](https://github.com/Redmi-Note-13-Gold/android_kernel_xiaomi_gold)，fork 自 [Dhterech](https://github.com/Dhterech/android_kernel_xiaomi_gold) |
| IMS | [techyminati/android_vendor_mediatek_ims](https://github.com/techyminati/android_vendor_mediatek_ims) |
| 厂商 blob | 不入库，从官方 `OS3.0.5.0.VNQMIXM` 包里提取 |

测试版，userdebug、test-keys，和 Xiaomi、MediaTek、LineageOS 官方无关。

## 状态

2026-10-07 起改为跟踪上游 `lineage-23.2`，设备树改为以 Dhterech 的树为基础。基于新结构的版本还没在手机上验证过。

9 月 30 日及更早的版本（包括已发布的 [Global R1](https://github.com/Redmi-Note-13-Gold/lineageos-gold/releases/tag/lineage-23.2-20260929-r1)）来自旧结构：这个仓库的 tag `pre-restructure`，以及设备树仓库的 `gold-r7` 分支。

## 构建

需要 `repo`、`git-lfs`、`erofs-utils`，以及 LineageOS 的[常规构建依赖](https://wiki.lineageos.org/devices/)。

```sh
repo init -u https://github.com/LineageOS/android.git -b lineage-23.2 --git-lfs
mkdir -p .repo/local_manifests
curl -o .repo/local_manifests/gold.xml \
  https://raw.githubusercontent.com/Redmi-Note-13-Gold/lineageos-gold/main/local_manifests/gold.xml
repo sync -c
```

提取厂商 blob。输入是官方全量 OTA `gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip`（SHA-256 `35c9f1d98b28538ac10c319ad4cba993cd5a632960d9111162e3efa494dae5c9`）：

```sh
cd device/xiaomi/gold
./extract-files.py /path/to/gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip
cd -
```

构建：

```sh
source build/envsetup.sh
breakfast gold userdebug
m bacon
```

产物在 `out/target/product/gold/`。

### 内存小的构建机

`host/build.sh` 是我们那台 8 核 14 GB 机器用的入口，做的事和上面一样，另外启用 ccache，并打两个本地补丁，内存够的机器用不着：

- `soong-memory-env.patch`（`build/soong`）：把 `GOGC`、`GOMEMLIMIT` 传给 soong_build。
- `lineage-build-date.patch`（`vendor/lineage`）：允许固定版本号里的日期。日期一变 Soong 就要重新分析整棵树，在这台机器上要几个小时。脚本沿用当前 `out/` 第一次构建时的日期，想换日期就设 `LINEAGE_BUILD_DATE`。

`repo sync` 之前先还原这两个项目：`git -C build/soong checkout . && git -C vendor/lineage checkout .`

## 和 Dhterech 的差别

见两个 fork 的 `lineage-23.2`、`prebuilt` 分支上 Dhterech 之后的提交。

- 内核仓库补上了 `system_dlkm/` 目录。上游只提交了镜像，设备树要的是目录，缺了它 `system_dlkm` 分区是空的：没有 zram，Wi-Fi 驱动也加载不了。
- OTA 里只带 `scp` 固件，不刷 preloader、lk、tee 等。我们的测试机是刷了 Global 底包的国行 `gold_cn`。
- 关掉窗口模糊，这颗 GPU 带不动。
- 电池服务每秒最多刷新一次。充电时内核每秒发约 9 个电池事件。
- 给 LN8000 电荷泵补了 SELinux 标签。
