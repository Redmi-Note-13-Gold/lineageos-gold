# LineageOS 23.2 for Redmi Note 13 5G (`gold`)

主线使用标准 Android 源码构建，固定 **Global OS3.0.5.0.VNQMIXM / Android 15 vendor / kernel 6.6.118**。从官方 Recovery 提取厂商输入，再构建完整 target-files 和 A/B OTA。旧 Python 混合镜像流程已按用户后续清理授权退出工作树；源码历史由 Git 保存，当前维护、构建和验证统一使用主线。

2026-09-20 已重新审查主线、科研机实际源码和 Dhterech 参考树。当前修改包含 32 位图形依赖补齐、原厂功耗统计资源、实际屏幕模式选择、电量计数单位修复、振动 HAL 契约修复、相机目录权限收敛及维护者补丁入库。**本轮候选的 Android 构建和实机验收状态见 [STATUS](docs/STATUS.md)。**

- [当前状态](docs/STATUS.md)：构建、安装、启动和硬件证据分别列出。
- [构建](docs/BUILD.md) · [恢复源码](docs/RESTORE.md)
- [适配取舍](docs/ADAPTATION.md)：v1 与参考仓库的采用、替代和暂缓项。
- [目录与环境](docs/LAYOUT.md) · [更新策略](docs/UPDATES.md)
- [CN R1 最终安装说明](docs/releases/CN-R1.md)：仅适用于已发布旧版。
- [来源与许可](NOTICE.md)

科研机为唯一执行与核验依据，本地同步同一提交。日常入口 `/srv/build/gold/project`，统一构建命令 `/srv/build/build-gold.sh`；输入、候选、任务与历史均从 `/srv/build/gold` 导航。当前仅使用科研机 8 vCPU / 16 GiB 的迁移源码、`out-gold-standard` 和 ccache 做增量。旧编译机已释放。固定 IMS APK 是主线明确管理的闭源输入；仓库不包含官方完整镜像、签名私钥、原始设备日志或用户数据。

设备树继承 [mt6833-devs/android_device_xiaomi_gold](https://github.com/mt6833-devs/android_device_xiaomi_gold)，固定起点 `d3d941c29395ce770b95b735b27bd28e6a8c6946`。参考 [Dhterech/android_device_xiaomi_gold](https://github.com/Dhterech/android_device_xiaomi_gold) 的改动按实际输入和接口契约审查，保留原版权。与 Xiaomi、MediaTek、LineageOS 官方无隶属关系。
