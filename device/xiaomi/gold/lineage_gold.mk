#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

# Inherit from those products. Most specific first.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)

# Inherit from device makefile.
$(call inherit-product, device/xiaomi/gold/device.mk)

# Inherit some common LineageOS stuff.
$(call inherit-product, vendor/lineage/config/common_full_phone.mk)

PRODUCT_NAME := lineage_gold
PRODUCT_DEVICE := gold
PRODUCT_MANUFACTURER := Xiaomi
PRODUCT_BRAND := Redmi
PRODUCT_MODEL := 2312DRAABG

# Original OS3.0.5.0.VNQMIXM vendor/build.prop, verified against its pinned image.
# Keep user-visible identity above; KeyMint must receive the original TEE identity.
PRODUCT_NAME_FOR_ATTESTATION := vnd_gold
PRODUCT_MODEL_FOR_ATTESTATION := gold

PRODUCT_GMS_CLIENTID_BASE := android-xiaomi
