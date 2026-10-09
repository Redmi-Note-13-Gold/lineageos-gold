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

- 正常：启动、通话、短信、4G/5G 数据（联通和移动的卡，通话时数据不断，听筒、扬声器、蓝牙耳机都有声音，贴脸熄屏）、Wi-Fi（含 WPA3）、热点（WPA2、WPA3，Apple 设备也能连）、蓝牙（含耳机、传文件）、相机（含 ZSL、Ultra HDR、RAW、录像）、硬件编解码（H.264、HEVC、VP9 解码，H.264、HEVC 编码）、全部传感器（加速度、陀螺仪、磁力计、光线、距离、计步、拿起等；指南针校准后和 iPhone 的读数能对到 1°）、自动亮度、自动旋转、双击亮屏和双击熄屏、拿起和轻触触发主动显示、指纹、麦克风、扬声器、USB 和快充头充电、关机充电、关机闹钟（闹钟要定在 2 分半以后，手机会提前这么久开机）、USB 传文件（MTP）、USB 网络共享、GPS（室外实测能定位，热启动 1 到 3 秒，精度约 5 米）、zram、系统“更新”应用的自动更新（10-09 那版起，实测从上一个测试包升上来）。
- 没有：NFC（这台没有硬件）、相机的 108MP、人像、前摄 1600 万像素（相机 HAL 只把它们给官方相机用；后摄出 1200 万、前摄出 400 万）、屏幕常亮（已移除，见下）。
- 硬件限制：只有一路 Wi-Fi 射频，手机连着 5 GHz Wi-Fi 时热点也只能在同一信道，选 2.4 GHz 无效。屏是 video 模式，AOD 显示期间系统不休眠，实测约 290 mA，所以去掉了。热点没有基带的硬件转发加速：基带固件不提供这项能力（官方的服务程序和我们的是同一个文件），转发走内核。
- 待机：息屏、连着 Wi-Fi、没插卡时约 15 mA（3 小时掉 1%，94% 的时间在休眠）。网络 ADB 连着时会升到约 60 mA。
- 温控：八个核心满载约 7 分钟，CPU 升到 63°C 左右后被降频，稳定在 58°C 上下，主板 38°C、电池 34°C。

9 月 30 日及更早的版本（包括已发布的 [Global R1](https://github.com/Redmi-Note-13-Gold/lineageos-gold/releases/tag/lineage-23.2-20260929-r1)）来自旧结构：这个仓库的 tag `pre-restructure`，以及设备树仓库的 tag [`gold-r7`](https://github.com/Redmi-Note-13-Gold/android_device_xiaomi_gold/tree/gold-r7)。

从旧结构的版本换过来必须清数据。

待办见 [TODO.md](TODO.md)。

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

分区：OTA 包写 14 个分区。

- 启动：`boot`、`vendor_boot`、`dtbo`
- 校验：`vbmeta`、`vbmeta_system`、`vbmeta_vendor`
- 系统（都在 `super` 里）：`system`、`system_ext`、`product`、`vendor`、`system_dlkm`、`vendor_dlkm`、`odm_dlkm`
- 固件：`scp`

Dhterech 的包还会多写 10 个固件分区：`preloader`、`lk`、`tee`、`gz`、`md1img`、`dpm`、`mcupm`、`pi_img`、`spmfw`、`sspm`。

这 10 个分区我们靠底包提供：刷之前需要用户先手动刷入最新的国际版官方系统作为底包（目前是 `OS3.0.5.0.VNQMIXM`，厂商 blob 也取自它）。

设备树：

- 关掉窗口模糊。开着时界面明显掉帧，关掉后流畅；这颗入门级 GPU 按默认参数带不动，没试过别的参数。
- Wi-Fi 协商 PMF，否则连不上 iPhone 的热点；热点声明支持 WPA3，并改一项驱动配置让 Apple 设备能连上 WPA3 热点。
- 2.4 GHz 热点只用 1 到 11 信道（参照同芯片的 camellia）；不再谎称支持 Wi-Fi 6（这颗芯片是 Wi-Fi 5）。
- 强光下的高亮模式不再空转：原来的时间配置全是 0，系统进入高亮后每毫秒重算一次，电源管理线程占一个核的 14% 左右。
- 自动亮度能降回来：原来亮屏期间只升不降（从官方搬来的 3 秒平均窗口，配不上 4 秒的变暗确认时间），光线变暗后屏幕不变暗，高亮模式也退不出，要熄屏再亮屏才恢复。
- 关机闹钟：补上 LineageOS 给联发科写的那个小应用，并给预编译内核配了它编译时要的内核头文件包。
- 32 位图形驱动：原来只带了 64 位的，32 位进程一画界面就崩溃。
- 编解码服务用回官方那一版 Codec2 配套库。官方的服务是 Android 15 的二进制，配 Android 16 源码编的库时，有个类的大小对不上，服务启动后第一次创建编解码器容易崩溃（开机时媒体库扫描就会碰到）。同时放开两个系统调用，让它崩溃时能留下记录。
- “更新”应用改成读本仓库的 `updates.json`。
- 联网检测换成国内也能通的地址，否则网络会被标成无互联网、重启后不自动回连。
- 对时服务器换成国内也能通的，否则没插 SIM 时时间从不同步。
- 去掉状态栏多加的边距，收起时和下拉后的时间、图标对齐。
- 双击亮屏，电源服务换成 LineageOS 的 libperfmgr 实现。
- 另一批次器件的 SELinux 标签：LN8000 电荷泵、挂在 `dsi.1`/`dsi.2` 下的屏。
- 开回 dm-verity。
- 关机充电：Dhterech 的树上不工作。充电界面等显示驱动加载完再启动；面板每次重新上电后要重设亮度（背光驱动会丢掉和上次相同的值，所以先写一个相邻值）；充电模式下把背光节点交给充电程序。
- 拿起亮屏；USB 网络共享的接口改名为 `ncm0`（原来叫 `usb0`，共享服务不认）；关蓝牙不再崩溃；去掉屏幕常亮。
- 轻触屏幕触发主动显示（触摸屏手势里的 Single Tap）；主动显示的亮度跟着小米的 AOD 传感器走。
- FM 收音机（加载驱动、带上芯片固件、补上音频 HAL 要的属性、装上应用）；开机加载 GPS 驱动。Dhterech 的树上这两个驱动都没加载。
