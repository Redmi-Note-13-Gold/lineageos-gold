# SPDX-License-Identifier: Apache-2.0
# Retire the former bundled LPA from existing incremental Gold outputs.
# Soong's old installed-file removal follows symlinks with os.Stat, which can
# leave the app JNI link after its /system_ext library target is gone.
# Keep the platform clean version unchanged; these steps run once per output.
ifeq ($(TARGET_DEVICE),gold)
ifeq ($(strip $(PRODUCT_OUT)),)
$(error Gold retired-eSIM cleanup requires PRODUCT_OUT)
endif
$(call add-clean-step, rm -rf "$(PRODUCT_OUT)/system_ext/priv-app/OpenEUICC")
$(call add-clean-step, rm -f "$(PRODUCT_OUT)/system_ext/etc/permissions/android.hardware.telephony.euicc.xml" "$(PRODUCT_OUT)/system_ext/etc/permissions/android.hardware.telephony.euicc.mep.xml" "$(PRODUCT_OUT)/system_ext/etc/permissions/privapp_whitelist_im.angry.openeuicc.xml" "$(PRODUCT_OUT)/system_ext/lib/liblpac-jni.so" "$(PRODUCT_OUT)/system_ext/lib64/liblpac-jni.so")
# Rebuild the affected image and its listing, then let the normal target-files
# recipe recreate its staging tree. Keep the compiled intermediates and caches.
$(call add-clean-step, rm -f "$(PRODUCT_OUT)/system_ext.img" "$(PRODUCT_OUT)/installed-files-system_ext.txt" "$(PRODUCT_OUT)/installed-files-system_ext.json" "$(PRODUCT_OUT)/obj/PACKAGING/target_files_intermediates/lineage_gold-target_files.zip.list")
# Aperture uses local platform APIs from system_ext; retire its old product APK.
$(call add-clean-step, rm -rf "$(PRODUCT_OUT)/product/app/Aperture")
$(call add-clean-step, rm -f "$(PRODUCT_OUT)/product.img" "$(PRODUCT_OUT)/installed-files-product.txt" "$(PRODUCT_OUT)/installed-files-product.json" "$(PRODUCT_OUT)/obj/PACKAGING/target_files_intermediates/lineage_gold-target_files.zip.list")
endif
