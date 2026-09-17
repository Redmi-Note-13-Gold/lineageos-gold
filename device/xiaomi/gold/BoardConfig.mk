#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/gold

# Virtual A/B
AB_OTA_UPDATER := true
AB_OTA_PARTITIONS := \
    dtbo \
    odm_dlkm \
    product \
    system \
    system_dlkm \
    system_ext \
    vendor \
    vendor_dlkm

# Architecture
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-2a-dotprod
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_VARIANT := cortex-a76

# Stock Global contains 32-bit native vendor components. Applications use the
# 64-bit-only zygote selected by lineage_gold.mk; retain the native vendor ABI.
TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv8-2a
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_2ND_CPU_VARIANT := cortex-a55

# boot/vendor_boot image
AB_OTA_PARTITIONS += \
    boot \
    vendor_boot

BOARD_RAMDISK_USE_LZ4 := true
BOARD_USES_GENERIC_KERNEL_IMAGE := true
BOARD_MOVE_RECOVERY_RESOURCES_TO_VENDOR_BOOT := true
BOARD_INCLUDE_RECOVERY_RAMDISK_IN_VENDOR_BOOT := true

BOARD_BOOTIMAGE_PARTITION_SIZE := 67108864
BOARD_DTBOIMG_PARTITION_SIZE := 8388608
BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE := 67108864

BOARD_KERNEL_CMDLINE := bootopt=64S3,32N2,64N2

BOARD_KERNEL_BASE := 0x40078000
BOARD_KERNEL_OFFSET := 0x00008000
BOARD_KERNEL_PAGESIZE := 4096
BOARD_RAMDISK_OFFSET := 0x11088000
BOARD_KERNEL_TAGS_OFFSET := 0x07c08000
BOARD_DTB_OFFSET := 0x07c08000
BOARD_BOOT_HEADER_VERSION := 4

BOARD_MKBOOTIMG_ARGS := --base $(BOARD_KERNEL_BASE)
BOARD_MKBOOTIMG_ARGS += --kernel_offset $(BOARD_KERNEL_OFFSET)
BOARD_MKBOOTIMG_ARGS += --pagesize $(BOARD_KERNEL_PAGESIZE)
BOARD_MKBOOTIMG_ARGS += --ramdisk_offset $(BOARD_RAMDISK_OFFSET)
BOARD_MKBOOTIMG_ARGS += --tags_offset $(BOARD_KERNEL_TAGS_OFFSET)
BOARD_MKBOOTIMG_ARGS += --dtb_offset $(BOARD_DTB_OFFSET)
BOARD_MKBOOTIMG_ARGS += --header_version $(BOARD_BOOT_HEADER_VERSION)

# Bootloader
TARGET_BOOTLOADER_BOARD_NAME := gold
TARGET_NO_BOOTLOADER := true

# Display
TARGET_SCREEN_DENSITY := 440

# Kernel and modules are extracted together from the locked Global Recovery OTA.
# The stock boot contains only the kernel. Android re-signs it and rebuilds
# vendor_boot and all DLKM images; no R1 image is an input.
GOLD_KERNEL_PATH := vendor/xiaomi/gold/proprietary/kernel
TARGET_KERNEL_VERSION := 6.6
TARGET_FORCE_PREBUILT_KERNEL := true
TARGET_PREBUILT_KERNEL := $(GOLD_KERNEL_PATH)/kernel
BOARD_PREBUILT_BOOTIMAGE := $(GOLD_KERNEL_PATH)/boot.img

# Global puts generic init in a named vendor_boot fragment, not in boot.
# Use the generic ramdisk built from this checkout, plus the standard recovery
# fragment created by BOARD_INCLUDE_RECOVERY_RAMDISK_IN_VENDOR_BOOT.
BOARD_VENDOR_RAMDISK_FRAGMENTS := init_boot
BOARD_VENDOR_RAMDISK_FRAGMENT.init_boot.PREBUILT := $(PRODUCT_OUT)/ramdisk.img
BOARD_VENDOR_RAMDISK_FRAGMENT.init_boot.MKBOOTIMG_ARGS := --ramdisk_type PLATFORM
BOARD_KERNEL_IMAGE_NAME := Image
BOARD_INCLUDE_DTB_IN_BOOTIMG := true
BOARD_PREBUILT_DTBIMAGE_DIR := $(GOLD_KERNEL_PATH)/dtb
BOARD_PREBUILT_DTBOIMAGE := $(GOLD_KERNEL_PATH)/dtbo.img

# Include GKI modules in depmod so vendor dependencies point at /system_dlkm.
# Signed stock modules must be copied without stripping.
BOARD_SYSTEM_KERNEL_MODULES := $(wildcard $(GOLD_KERNEL_PATH)/system_dlkm/lib/modules/*.ko)
BOARD_SYSTEM_KERNEL_MODULES_LOAD := $(strip $(shell cat $(GOLD_KERNEL_PATH)/system_dlkm/lib/modules/modules.load))
BOARD_VENDOR_KERNEL_MODULES := $(wildcard $(GOLD_KERNEL_PATH)/vendor_dlkm/lib/modules/*.ko)
BOARD_VENDOR_KERNEL_MODULES_LOAD := $(strip $(shell cat $(GOLD_KERNEL_PATH)/vendor_dlkm/lib/modules/modules.load))
BOARD_VENDOR_RAMDISK_KERNEL_MODULES := $(wildcard $(GOLD_KERNEL_PATH)/vendor_ramdisk/lib/modules/*.ko)
BOARD_VENDOR_RAMDISK_KERNEL_MODULES_LOAD := $(strip $(shell cat $(GOLD_KERNEL_PATH)/vendor_ramdisk/lib/modules/modules.load))
BOARD_VENDOR_RAMDISK_RECOVERY_KERNEL_MODULES_LOAD := $(strip $(shell cat $(GOLD_KERNEL_PATH)/vendor_ramdisk/lib/modules/modules.load.recovery))
BOARD_DO_NOT_STRIP_VENDOR_MODULES := true
BOARD_DO_NOT_STRIP_VENDOR_RAMDISK_MODULES := true

# Partitions
BOARD_FLASH_BLOCK_SIZE := 262144
BOARD_SUPER_PARTITION_SIZE := 9126805504

BOARD_USES_METADATA_PARTITION := true

BOARD_SUPER_PARTITION_GROUPS := mediatek_dynamic_partitions
BOARD_MEDIATEK_DYNAMIC_PARTITIONS_SIZE := 9122611200
BOARD_MEDIATEK_DYNAMIC_PARTITIONS_PARTITION_LIST := \
    system \
    system_dlkm \
    system_ext \
    product \
    vendor \
    vendor_dlkm \
    odm_dlkm

BOARD_SYSTEM_DLKMIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_ODM_DLKMIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_VENDOR_DLKMIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := erofs

BOARD_PRODUCTIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_SYSTEM_EXTIMAGE_FILE_SYSTEM_TYPE := ext4

TARGET_COPY_OUT_ODM := vendor/odm
TARGET_COPY_OUT_SYSTEM_DLKM := system_dlkm
TARGET_COPY_OUT_ODM_DLKM := odm_dlkm
TARGET_COPY_OUT_VENDOR := vendor
TARGET_COPY_OUT_VENDOR_DLKM := vendor_dlkm

TARGET_COPY_OUT_PRODUCT := product
TARGET_COPY_OUT_SYSTEM := system
TARGET_COPY_OUT_SYSTEM_EXT := system_ext

# Platform
TARGET_BOARD_PLATFORM := mt6833
BOARD_SHIPPING_API_LEVEL := 30

# Props
TARGET_VENDOR_PROP += $(DEVICE_PATH)/vendor.prop

# Recovery
TARGET_RECOVERY_PIXEL_FORMAT := BGRA_8888
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/init/fstab.mt6833

# RIL
ENABLE_VENDOR_RIL_SERVICE := true

# SEPolicy
include device/mediatek/sepolicy_vndr/SEPolicy.mk
BOARD_VENDOR_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/vendor

# SPL
# The vendor reports February; the OTA framework SPL is August. The rebuilt
# boot image uses the vendor baseline (stock boot header has no encoded SPL).
BOOT_SECURITY_PATCH := 2026-02-01
VENDOR_SECURITY_PATCH := 2026-02-01

# vintf
DEVICE_MANIFEST_FILE := $(DEVICE_PATH)/manifest.xml
DEVICE_MATRIX_FILE := $(DEVICE_PATH)/compatibility_matrix.xml
DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE += \
    hardware/xiaomi/vintf/xiaomi_framework_compatibility_matrix.xml \
    hardware/mediatek/vintf/mediatek_framework_compatibility_matrix.xml

# WiFi
# Match the function table exported by the Android 15 Global vendor HAL.
$(call soong_config_set_bool,mediatek_wifi_hal,use_pre_baklava_qpr0_struct,true)
WPA_SUPPLICANT_VERSION := VER_0_8_X
BOARD_WPA_SUPPLICANT_DRIVER := NL80211
BOARD_HOSTAPD_DRIVER := NL80211
WIFI_DRIVER_FW_PATH_PARAM := "/dev/wmtWifi"
WIFI_DRIVER_FW_PATH_STA := "STA"
WIFI_DRIVER_FW_PATH_AP := "AP"
WIFI_DRIVER_FW_PATH_P2P := "P2P"
WIFI_DRIVER_STATE_CTRL_PARAM := "/dev/wmtWifi"
WIFI_DRIVER_STATE_ON := "1"
WIFI_DRIVER_STATE_OFF := "0"
WIFI_HIDL_FEATURE_DUAL_INTERFACE := true
WIFI_HIDL_UNIFIED_SUPPLICANT_SERVICE_RC_ENTRY := true

# Verified Boot
AB_OTA_PARTITIONS += \
    vbmeta \
    vbmeta_system \
    vbmeta_vendor

BOARD_AVB_ENABLE := true
BOARD_AVB_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_ALGORITHM := SHA256_RSA4096

BOARD_AVB_BOOT_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_BOOT_ALGORITHM := SHA256_RSA4096
BOARD_AVB_BOOT_ROLLBACK_INDEX := $(PLATFORM_SECURITY_PATCH_TIMESTAMP)
BOARD_AVB_BOOT_ROLLBACK_INDEX_LOCATION := 1

BOARD_AVB_VBMETA_SYSTEM := system system_ext product system_dlkm
BOARD_AVB_VBMETA_SYSTEM_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_VBMETA_SYSTEM_ALGORITHM := SHA256_RSA4096
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX := $(PLATFORM_SECURITY_PATCH_TIMESTAMP)
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX_LOCATION := 2

BOARD_AVB_VBMETA_VENDOR := vendor vendor_dlkm odm_dlkm
BOARD_AVB_VBMETA_VENDOR_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_VBMETA_VENDOR_ALGORITHM := SHA256_RSA4096
BOARD_AVB_VBMETA_VENDOR_ROLLBACK_INDEX := $(PLATFORM_SECURITY_PATCH_TIMESTAMP)
BOARD_AVB_VBMETA_VENDOR_ROLLBACK_INDEX_LOCATION := 3

# Inherit the proprietary files
include vendor/xiaomi/gold/BoardConfigVendor.mk
