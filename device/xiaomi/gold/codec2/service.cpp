// SPDX-License-Identifier: Apache-2.0
#define LOG_TAG "gold-codec2"

#include <C2Component.h>
#include <android-base/logging.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <codec2/aidl/ComponentStore.h>
#include <minijail.h>

#include <csignal>
#include <cstdlib>
#include <memory>
#include <string>

namespace android {
// Exported by the matched Global vendor's libcodec2_mtk_c2store.so.
std::shared_ptr<C2ComponentStore> GetCodec2MtkComponentStore();
}

int main(int, char** argv) {
    android::base::InitLogging(argv, android::base::LogdLogger(android::base::SYSTEM));
    signal(SIGPIPE, SIG_IGN);
    android::SetUpMinijailList(
            "/vendor/etc/seccomp_policy/android.hardware.media.c2@1.2-mediatek-seccomp-policy",
            {"/vendor/etc/seccomp_policy/android.hardware.media.c2@1.2-extended-seccomp-policy",
             "/vendor/etc/seccomp_policy/gold-codec2-crash.policy"});

    namespace c2 = aidl::android::hardware::media::c2;
    ABinderProcess_setThreadPoolMaxThreadCount(8);
    auto vendorStore = android::GetCodec2MtkComponentStore();
    if (!vendorStore) {
        LOG(ERROR) << "Matched MTK component store is unavailable";
        return EXIT_FAILURE;
    }

    // The factory owns the closed codec implementation. Allocate the platform
    // AIDL wrapper here, using the same headers as libcodec2_aidl. The stock
    // Android 15 executable allocates 336 bytes; the current class needs 352.
    // Never patch a hard-coded allocation size into that old executable.
    LOG(INFO) << "Gold Codec2 bridge: platform ComponentStore size="
              << sizeof(c2::utils::ComponentStore);
    auto service = ndk::SharedRefBase::make<c2::utils::ComponentStore>(vendorStore);
    if (service->status() != C2_OK) {
        LOG(ERROR) << "Platform Codec2 wrapper initialization failed: " << service->status();
        return EXIT_FAILURE;
    }
    const std::string instance = std::string(c2::IComponentStore::descriptor) + "/default";
    if (AServiceManager_addService(service->asBinder().get(), instance.c_str()) != EX_NONE) {
        LOG(ERROR) << "Cannot register " << instance;
        return EXIT_FAILURE;
    }
    ABinderProcess_joinThreadPool();
    return EXIT_FAILURE;
}
