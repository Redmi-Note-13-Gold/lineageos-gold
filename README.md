# LineageOS 23.2 for Redmi Note 13 5G (`gold`)

这个仓库只放构建入口：一份 local manifest、提取内核的脚本和构建机用的脚本。设备相关的代码在别处：

| 内容 | 仓库 |
| --- | --- |
| 设备树 | [Redmi-Note-13-Gold/android_device_xiaomi_gold](https://github.com/Redmi-Note-13-Gold/android_device_xiaomi_gold)，fork 自 [Dhterech](https://github.com/Dhterech/android_device_xiaomi_gold) |
| 内核、DTB、内核模块 | 不入库，用 `extract-kernel.sh` 从同一个官方包里提取 |
| IMS | [techyminati/android_vendor_mediatek_ims](https://github.com/techyminati/android_vendor_mediatek_ims) |
| 厂商 blob | 不入库，从官方 `OS3.0.5.0.VNQMIXM` 包里提取 |

测试版，userdebug、test-keys，和 Xiaomi、MediaTek、LineageOS 官方无关。

## 状态

2026-10-07 起跟踪上游 `lineage-23.2`，设备树以 Dhterech 的树为基础。在一台国行 `gold_cn` 上用过：

- 正常：启动、Wi-Fi（含 WPA3）、热点（WPA2、WPA3，Apple 设备也能连）、蓝牙（含耳机）、相机（含 ZSL、Ultra HDR、RAW）、全部传感器（加速度、陀螺仪、磁力计、光线、距离、计步、拿起等）、自动亮度、自动旋转、双击亮屏和双击熄屏、AOD、指纹、麦克风、扬声器、USB 和快充头充电、关机充电、zram。
- 没有：NFC（这台没有硬件）、108MP 和人像等相机私有模式、屏幕常亮（已移除，见下）。FM 在做。
- 硬件限制：只有一路 Wi-Fi 射频，手机连着 5 GHz Wi-Fi 时热点也只能在同一信道，选 2.4 GHz 无效。屏是 video 模式，AOD 显示期间系统不休眠，实测约 290 mA，不建议常开。

9 月 30 日及更早的版本（包括已发布的 [Global R1](https://github.com/Redmi-Note-13-Gold/lineageos-gold/releases/tag/lineage-23.2-20260929-r1)）来自旧结构：这个仓库的 tag `pre-restructure`，以及设备树仓库的 `gold-r7` 分支。

从旧结构的版本换过来必须清数据。

## 待办

2026-10-08 的清单。

正在构建（新增模块，要整树分析）：

1. 轻触屏幕触发主动显示：触摸驱动打开 AOD 模式后，息屏单击会发 `KEY_GOTO`（已实测）。在设备树里加一个 `vendor.lineage.touch` 的手势服务，让设置里的“触摸屏手势”能把单击绑到“主动显示”
2. 主动显示的亮度跟着小米的 AOD 传感器走（亮环境约 9%，暗环境约 2%），做法同 LineageOS 的 rosemary
3. FM 收音机：加载驱动模块、加 LineageOS 的 FMRadio 和频段属性。要插有线耳机实际收台确认
4. GPS：驱动模块 `gps_drv_stp.ko` 一直没被加载，`/dev/stpgps`、`/dev/gps_emi` 都不存在。手动加载后节点出现。已在开机脚本里补上，要到室外定位确认

要做：

1. 相机 108MP、人像、前摄全分辨率
2. 连着 5 GHz Wi-Fi 开 2.4 GHz 热点：试驱动的分时双信道
3. 指南针和另一台手机差 16° 到 19°（两边都是磁北）：同点同向比四个方向，看是不是缺软铁校准。另外重启后磁力计不会自动用上已存的校准值，要晃动手机才准
4. 剩余的 SELinux 拒绝：相机、编解码、电话服务、音频、充电界面读属性被拒。目前只抓到一个属性名（`ro.vendor.aware_available`），其余要在开机后立刻抓
5. 高负载下的温控
6. 息屏待机耗电
7. 用 MTP 往手机里传文件：识别、列目录、从手机下载都正常，上传没试成（命令行工具自己找不到目标目录），要用图形界面的工具再确认
8. 进入高亮模式后系统是否空转（旧结构为此打过框架补丁；现在的配置里时间窗全是 0）
9. USB 网络共享：接口名已补，要用设置里的开关再试一次

还没验，要人动手：

- 无线投屏
- 关机闹钟
- 插 SIM：通话、短信、数据、VoLTE、双卡，以及听筒、免提、蓝牙通话、贴脸熄屏
- 有线耳机
- OTG、存储卡
- 红外
- 室外：GPS、指南针对比

观察，出问题再动：

- 图标多时状态栏折叠成圆点、间距不匀
- TCP 连接被重置后长驻
- 热点硬件加速（联发科 MDDP，转发走基带不走 CPU）：没验过实际有没有生效。9 月在旧结构上查到基带上报的能力是 `0x3`，缺 Wi-Fi 热点那一位（`0x4`），只放开 `/dev/mddp` 的权限不够。当时写过一个让内核模块走旧握手方式的候选补丁，只做了离线编译和主机测试，没装过机。材料在提交 `0e570c7` 的 `experiments/mddp/`
- LDAC
- 蓝牙传文件到 Mac 只有约 37 KB/s。蓝牙音频正常；如果耳机卡顿或手机对手机也慢再查

## 构建

需要 `repo`、`git-lfs`、`erofs-utils`、`lz4`、`cpio`、`unzip`，以及 LineageOS 的[常规构建依赖](https://wiki.lineageos.org/devices/)。

```sh
repo init -u https://github.com/LineageOS/android.git -b lineage-23.2 --git-lfs
mkdir -p .repo/local_manifests
curl -o .repo/local_manifests/gold.xml \
  https://raw.githubusercontent.com/Redmi-Note-13-Gold/lineageos-gold/main/local_manifests/gold.xml
repo sync -c
```

提取内核和厂商 blob。输入都是官方全量 OTA `gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip`（SHA-256 `35c9f1d98b28538ac10c319ad4cba993cd5a632960d9111162e3efa494dae5c9`）：

```sh
curl -O https://raw.githubusercontent.com/Redmi-Note-13-Gold/lineageos-gold/main/extract-kernel.sh
bash extract-kernel.sh /path/to/gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip
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

设备树的差别见 fork 的 `lineage-23.2` 分支上 Dhterech 之后的提交。

内核：Dhterech 用一个放预编译文件的仓库。我们不用它，改成用 `extract-kernel.sh` 直接从官方包生成同样的目录，这样每个文件的来源都能重跑验证。生成结果和他的仓库相比：

- 多出 `system_dlkm/` 目录。他的仓库只提交了镜像，设备树要的是目录，缺了它 `system_dlkm` 分区是空的：没有 zram，Wi-Fi 驱动也加载不了。
- `hq_charger_sysfs.ko` 改了一条指令，停掉给 MIUI 充电动画用的 uevent 线程。接电脑充电时它每秒发 10 个电池事件，拔线后还可能一直不停。
- 其余构建用到的文件和他的逐字节相同，包括他在模块加载清单里加的 `wmt_drv.ko`。

设备树：

- OTA 里只带 `scp` 固件，不刷 preloader、lk、tee 等。
- 关掉窗口模糊。开着时界面明显掉帧，关掉后流畅；这颗入门级 GPU 按默认参数带不动，没试过别的参数。
- Wi-Fi 协商 PMF，否则连不上 iPhone 的热点；热点声明支持 WPA3，并改一项驱动配置让 Apple 设备能连上 WPA3 热点。
- 联网检测换成国内也能通的地址，否则网络会被标成无互联网、重启后不自动回连。
- 对时服务器换成国内也能通的，否则没插 SIM 时时间从不同步。
- 去掉状态栏多加的边距，收起时和下拉后的时间、图标对齐。
- 双击亮屏，电源服务换成 LineageOS 的 libperfmgr 实现。
- 另一批次器件的 SELinux 标签：LN8000 电荷泵、挂在 `dsi.1`/`dsi.2` 下的屏。
- 开回 dm-verity。
- 关机充电：Dhterech 的树上不工作。充电界面等显示驱动加载完再启动；面板每次重新上电后要重设亮度（背光驱动会丢掉和上次相同的值，所以先写一个相邻值）；充电模式下把背光节点交给充电程序。
- 拿起亮屏；USB 网络共享认 `usb0`；关蓝牙不再崩溃；去掉屏幕常亮。
