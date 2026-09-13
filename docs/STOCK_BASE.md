# 官方底包整合

`main` 固定使用 Redmi Note 13 5G `gold` 国行官方 **OS3.0.10.0.VNQCNXM**（Android 15）作为下层固件基线，LineageOS 上层仍为 **23.2 / Android 16**。版本与完整归档校验值见 [gold-cn.json](../firmware/gold-cn.json)。本轮只构建和检查，未刷手机。

旧 OS3.0.9 组合、调试输入与自编译 MDDP 研究保留在 [experimental 分支](https://github.com/Redmi-Note-13-Gold/lineageos-gold/tree/experimental)。`main` 不使用该候选模块。

## 下载与提取

在 Linux 编译服务器直接下载归档。主地址是 `bigota.d.miui.com`，可以尝试同路径的 `hugeota.d.miui.com`、`bn.d.miui.com`；不同节点的可达性和限速会变化。下载时保留官方页面 Referer，分段下载必须检查每段的 `Content-Range`，合并后重新验证整个文件。

SHA-256 是本项目对完整文件计算的值，**并非小米签名校验声明**。无论选哪个端点，都必须与固定文件的大小、MD5 和 SHA-256 同时匹配。不要仅凭 HTTP 200、文件名或预分配文件大小认定下载完成。

使用已有的 Linux / Python 3.11+ 和 Android 主机工具：

```sh
python3 /path/to/lineageos-gold/tools/prepare-stock.py \
  --archive /path/to/official.tgz \
  --output /path/to/fresh-stock-inputs \
  --host-bin /path/to/android/out/host/linux-x86/bin
```

工具只提取所需镜像，不执行原厂刷机脚本。保留原归档、16 个物理分区输入及 vendor、mi_ext、三个 dlkm 逻辑分区；super 解包临时副本在成功后删除。LK、基带等物理固件单独保留在 `physical/`，不自动写入设备。

## 增量组装

这一步需要**已完成 hybrid 适配的 LineageOS 上层镜像**：system、system_ext、product、对应 vbmeta_system，以及 23.2 构建的 ODM。它们须包含既有 property contexts、zygote、模块路径、IMS 和 framework VINTF 适配。普通 `bacon` 输出尚不能直接替代这组输入；本仓库没有宣称已经解决从空目录恢复整包。

使用新输出目录，保留旧镜像供回退。以 root 运行是为了只读挂载镜像、读取原始 UID/GID/SELinux/capabilities；不会访问手机。

```sh
sudo python3 /path/to/lineageos-gold/tools/build-stock-base.py \
  --source /path/to/android \
  --stock /path/to/fresh-stock-inputs \
  --lineage-images /path/to/matching-lineage-images \
  --output /path/to/fresh-assembly \
  --lock /path/to/shared-build.lock
```

官方包没有独立 ODM 分区，这一分区由 Lineage 构建提供；若不在同一输入目录，可用 `--lineage-odm /path/to/odm.img` 指定。

组装原则：

- boot、vendor_boot、dtbo、内核模块及对应固件来自同一份官方包。
- vendor 从新官方镜像提取，仅应用 `integration/stock/vendor-compat.patch` 并移除过期预编译策略缓存；回读重建镜像核对全部文件、权限及扩展属性。
- mi_ext 保留新底包内容及版本，只移除会遮挡 Lineage Messaging 的零字节 `product/app/messaging/messaging.apk` 占位文件。
- 重新生成 AVB 描述符与父镜像，保留真正的官方版本字段；顶层 flags 为 0，独立重算修改分区的 FEC。
- 默认使用 AOSP 公开开发测试密钥签署重建的 vbmeta；可通过 `--key` 指定自有构建密钥。这不意味着获得小米签名，也不是锁定 bootloader 或正式发布密钥流程。

输出 `assembly.json`、`SHA256SUMS` 和审计结果；固件输入与重建产物分开保留。不执行 adb、fastboot 或 A/B 切换。

## 编译与兼容性检查

```sh
sudo python3 /path/to/lineageos-gold/tools/verify-stock-base.py \
  --source /path/to/android \
  --assembly /path/to/fresh-assembly \
  --apex-root /path/to/matching-extracted-apex
```

检查直接读取组装后的镜像，并从官方 kernel 提取内嵌配置：编译合并 SELinux 策略、检查 property contexts、VINTF 和 Messaging 文件。`--apex-root` 必须来自对应 Lineage 上层的 APEX 提取结果，不能指向任意空目录。

init 使用的运行时策略编译与启用全部 neverallow 的严格检查分别记录。旧 hybrid 已有严格策略冲突；不得把 `-N` 的编译成功写成严格 SELinux/CTS 通过。离线检查也不能验证 modem 握手、VoLTE 通话、热点加速或新底包启动。

## 本轮结果

日期：2026-09-13。服务器直接下载了完整官方归档，大小 **7,818,573,046 字节**，MD5 与 SHA-256 均匹配；提取 21 个官方分区输入。没有传输 Mini 上的底包，也没有刷手机。

| 检查 | 结果 |
|---|---|
| 官方输入 | boot / vendor_boot / dtbo / LK / 基带及三个 dlkm 来自同一份 OS3.0.10 归档；内核载荷为 6.6.89 |
| vendor 回读审计 | 6482 个路径的元数据与扩展属性保持一致；仅修改列出的 4 个配置文件、移除预编译策略缓存 |
| mi_ext 回读审计 | 47 个路径的元数据与扩展属性保持一致；仅移除零字节 Messaging 占位文件，保持原分区大小 |
| Lineage 上层 | 保留既有 23.2 system / system_ext / product / vbmeta_system，并使用 23.2 构建的 ODM |
| AVB | 完整链验证通过；重建顶层 flags=0；新 vendor 的版本属性保持原始字节值 |
| FEC | vendor、mi_ext 均独立重新编码并与镜像中的纠错数据匹配 |
| 策略与属性 | init 使用路径的 SELinux 策略编译通过，property contexts 检查通过 |
| 严格 neverallow | **未通过：27 项冲突**，与旧 hybrid 已知数量相同；本轮没有修复这项既有缺口 |
| VINTF | 使用新官方 kernel 的内嵌配置，与组装镜像和匹配的 Lineage APEX 输入检查，结果 COMPATIBLE |
| 启动设备树 | 新 LK、vendor_boot 中的 DTB 及新 DTBO 载荷，与此前成功做过 overlay 合并检查的输入逐字节一致 |
| Messaging | Lineage 23.2 的实际 APK 保留在 product，mi_ext 遮挡占位文件已移除 |
| 实机 / OTA | **未刷入、未验收、未做 OTA 验证**；不能从离线结果推断 VoLTE、热点、相机或稳定性 |

机器可读摘要与最终镜像哈希见 [stock-base-20260913.json](../validation/stock-base-20260913.json)。这些是增量镜像组装及兼容性编译结果，不是全新源码完整 ROM 编译记录。
