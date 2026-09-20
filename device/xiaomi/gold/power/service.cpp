// SPDX-License-Identifier: Apache-2.0
#define LOG_TAG "gold-power"

#include "PowerEngine.h"

#include <aidl/android/hardware/power/BnPower.h>
#include <aidl/android/hardware/thermal/IThermal.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android/binder_ibinder.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <hidl/HidlTransportSupport.h>
#include <hwbinder/IPCThreadState.h>
#include <vendor/mediatek/hardware/mtkpower/1.2/IMtkPerf.h>
#include <vendor/mediatek/hardware/mtkpower/1.2/IMtkPower.h>

#include <atomic>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdio>
#include <thread>
#include <unistd.h>

namespace {
namespace p = aidl::android::hardware::power;
namespace t = aidl::android::hardware::thermal;
namespace mt = vendor::mediatek::hardware::mtkpower;
using android::hardware::Return;
using android::hardware::Void;
using android::hardware::hidl_string;
using android::hardware::hidl_vec;
using gold::power::Millis;
using gold::power::PowerEngine;

std::atomic<bool> stopping{false};
static_assert(std::atomic<bool>::is_always_lock_free);
Millis now() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
}
void stopSignal(int) { stopping.store(true); }
ndk::ScopedAStatus unsupported() { return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION); }
bool frameworkCaller() {
    auto uid = AIBinder_getCallingUid();
    return uid == 0 || uid == 1000 || uid == 1003;
}
int clamp(const char* property) {
    // Experimental framework strategies start disabled. Defaults may only be
    // changed after matched-device latency/frame/energy measurements. These
    // transient vendor properties let the same binary run the A/B comparison.
    return android::base::GetIntProperty<int>(property, 0, 0, 60);
}
int launchClamp() { return clamp("vendor.gold.power.launch_uclamp"); }
int interactionClamp() { return clamp("vendor.gold.power.interaction_uclamp"); }

class Power final : public p::BnPower {
  public:
    explicit Power(PowerEngine& engine) : engine_(engine) {}
    ndk::ScopedAStatus setMode(p::Mode mode, bool enabled) override {
        if (!frameworkCaller()) return ndk::ScopedAStatus::fromExceptionCode(EX_SECURITY);
        switch (mode) {
            case p::Mode::LOW_POWER: engine_.lowPower(enabled, now()); break;
            case p::Mode::INTERACTIVE: engine_.interactive(enabled, now()); break;
            case p::Mode::DEVICE_IDLE: engine_.deviceIdle(enabled, now()); break;
            case p::Mode::DISPLAY_INACTIVE: engine_.displayInactive(enabled, now()); break;
            case p::Mode::LAUNCH:
                if (launchClamp() == 0) return unsupported();
                engine_.launch(enabled, launchClamp(), now());
                break;
            default: return unsupported();
        }
        return ndk::ScopedAStatus::ok();
    }
    ndk::ScopedAStatus isModeSupported(p::Mode mode, bool* result) override {
        *result = mode == p::Mode::LOW_POWER || mode == p::Mode::INTERACTIVE ||
                mode == p::Mode::DEVICE_IDLE || mode == p::Mode::DISPLAY_INACTIVE ||
                (mode == p::Mode::LAUNCH && launchClamp() > 0 && engine_.status().ready);
        return ndk::ScopedAStatus::ok();
    }
    ndk::ScopedAStatus setBoost(p::Boost boost, int32_t duration) override {
        if (!frameworkCaller()) return ndk::ScopedAStatus::fromExceptionCode(EX_SECURITY);
        if (boost != p::Boost::INTERACTION || interactionClamp() == 0) return unsupported();
        engine_.interaction(duration, interactionClamp(), now());
        return ndk::ScopedAStatus::ok();
    }
    ndk::ScopedAStatus isBoostSupported(p::Boost boost, bool* result) override {
        *result = boost == p::Boost::INTERACTION && interactionClamp() > 0 && engine_.status().ready;
        return ndk::ScopedAStatus::ok();
    }
    ndk::ScopedAStatus getSupportInfo(p::SupportInfo* result) override {
        *result = {};
        for (p::Mode mode : {p::Mode::LOW_POWER, p::Mode::INTERACTIVE, p::Mode::DEVICE_IDLE,
                             p::Mode::DISPLAY_INACTIVE, p::Mode::LAUNCH}) {
            bool supported;
            isModeSupported(mode, &supported);
            if (supported) result->modes |= int64_t{1} << static_cast<int>(mode);
        }
        bool supported;
        isBoostSupported(p::Boost::INTERACTION, &supported);
        if (supported) result->boosts = int64_t{1} << static_cast<int>(p::Boost::INTERACTION);
        return ndk::ScopedAStatus::ok();
    }
    ndk::ScopedAStatus createHintSession(int32_t, int32_t, const std::vector<int32_t>&, int64_t,
            std::shared_ptr<p::IPowerHintSession>*) override { return unsupported(); }
    ndk::ScopedAStatus getHintSessionPreferredRate(int64_t*) override { return unsupported(); }
    ndk::ScopedAStatus createHintSessionWithConfig(int32_t, int32_t, const std::vector<int32_t>&,
            int64_t, p::SessionTag, p::SessionConfig*, std::shared_ptr<p::IPowerHintSession>*) override { return unsupported(); }
    ndk::ScopedAStatus getSessionChannel(int32_t, int32_t, p::ChannelConfig*) override { return unsupported(); }
    ndk::ScopedAStatus closeSessionChannel(int32_t, int32_t) override { return unsupported(); }
    ndk::ScopedAStatus getCpuHeadroom(const p::CpuHeadroomParams&, p::CpuHeadroomResult*) override { return unsupported(); }
    ndk::ScopedAStatus getGpuHeadroom(const p::GpuHeadroomParams&, p::GpuHeadroomResult*) override { return unsupported(); }
    ndk::ScopedAStatus sendCompositionData(const std::vector<p::CompositionData>&) override { return unsupported(); }
    ndk::ScopedAStatus sendCompositionUpdate(const p::CompositionUpdate&) override { return unsupported(); }
    binder_status_t dump(int fd, const char**, uint32_t) override {
        auto uid = AIBinder_getCallingUid();
        if (uid != 0 && uid != 1000 && uid != 2000) return STATUS_PERMISSION_DENIED;
        const auto status = engine_.status();
        dprintf(fd, "ready=%d enabled=%d dirty=%d requests=%zu accepted=%llu rejected=%llu next_expiry_ms=%lld\n",
                status.ready, status.requests.enabled, status.requests.dirty, status.requests.requests,
                static_cast<unsigned long long>(status.accepted), static_cast<unsigned long long>(status.rejected),
                static_cast<long long>(status.requests.nextExpiry));
        dprintf(fd, "launch_uclamp=%d interaction_uclamp=%d backend_error=%s\n", launchClamp(), interactionClamp(), status.backendError.c_str());
        for (const auto& [id, value] : status.effective) dprintf(fd, "effective[0x%08x]=%d\n", id, value);
        return STATUS_OK;
    }
  private:
    PowerEngine& engine_;
};

class Perf final : public mt::V1_2::IMtkPerf {
  public:
    explicit Perf(PowerEngine& engine) : engine_(engine) {}
    Return<int32_t> perfLockAcquire(int32_t handle, uint32_t duration,
            const hidl_vec<int32_t>& pairs, int32_t) override {
        auto ipc = android::hardware::IPCThreadState::self();
        int result = engine_.acquire(ipc->getCallingUid(), ipc->getCallingPid(), handle, duration,
                                    std::vector<int32_t>(pairs.begin(), pairs.end()), now());
        if (result < 0) rejected(result, pairs);
        return result;
    }
    Return<void> perfLockRelease(int32_t handle, int32_t) override {
        auto ipc = android::hardware::IPCThreadState::self();
        int result = ipc->getCallingPid() > 0 ? engine_.release(ipc->getCallingUid(), ipc->getCallingPid(), handle, now()) :
                engine_.releaseAsync(ipc->getCallingUid(), handle, now());
        if (result < 0) rejected(result, {});
        return Void();
    }
    Return<int32_t> perfLockReleaseSync(int32_t handle, int32_t) override {
        auto ipc = android::hardware::IPCThreadState::self();
        return engine_.release(ipc->getCallingUid(), ipc->getCallingPid(), handle, now());
    }
    Return<int32_t> perfCusLockHint(int32_t, uint32_t) override { return -EOPNOTSUPP; }
  private:
    void rejected(int error, const hidl_vec<int32_t>& pairs) {
        // Bound diagnostics; never log package names, activities or media data.
        if (warnings_.fetch_add(1) < 20) {
            LOG(WARNING) << "vendor request rejected error=" << error << " words=" << pairs.size();
            for (size_t i = 0; i + 1 < pairs.size(); i += 2) LOG(WARNING) << "resource=" << pairs[i] << " value=" << pairs[i + 1];
        }
    }
    PowerEngine& engine_;
    std::atomic<unsigned> warnings_{0};
};

// These private control/query protocols have no demonstrated caller contract
// on the locked vendor. Do not invent results or report successful callbacks.
class MtkPower final : public mt::V1_2::IMtkPower {
  public:
    Return<void> mtkCusPowerHint(int32_t, int32_t) override { warn(); return Void(); }
    Return<void> mtkPowerHint(int32_t, int32_t) override { warn(); return Void(); }
    Return<void> notifyAppState(const hidl_string&, const hidl_string&, int32_t, int32_t, int32_t) override { warn(); return Void(); }
    Return<int32_t> querySysInfo(int32_t, int32_t) override { return -EOPNOTSUPP; }
    Return<int32_t> setSysInfo(int32_t, const hidl_string&) override { return -EOPNOTSUPP; }
    Return<void> setSysInfoAsync(int32_t, const hidl_string&) override { warn(); return Void(); }
    Return<int32_t> setMtkPowerCallback(const android::sp<mt::V1_1::IMtkPowerCallback>&) override { return -EOPNOTSUPP; }
    Return<int32_t> setMtkScnUpdateCallback(int32_t, const android::sp<mt::V1_2::IMtkPowerCallback>&) override { return -EOPNOTSUPP; }
  private:
    void warn() { if (warnings_.fetch_add(1) < 10) LOG(WARNING) << "unsupported private MTK control request"; }
    std::atomic<unsigned> warnings_{0};
};

void thermalWorker(PowerEngine& engine) {
    std::shared_ptr<t::IThermal> service;
    const std::string instance = std::string(t::IThermal::descriptor) + "/default";
    while (!stopping.load()) {
        if (!service) service = t::IThermal::fromBinder(ndk::SpAIBinder(AServiceManager_checkService(instance.c_str())));
        std::vector<t::Temperature> temperatures;
        bool safe = false;
        if (service && service->getTemperatures(&temperatures).isOk()) {
            bool found = false;
            safe = true;
            for (const auto& temperature : temperatures) {
                if (temperature.type == t::TemperatureType::CPU || temperature.type == t::TemperatureType::GPU ||
                        temperature.type == t::TemperatureType::SKIN || temperature.type == t::TemperatureType::BATTERY) {
                    found = true;
                    safe &= std::isfinite(temperature.value) && temperature.throttlingStatus == t::ThrottlingSeverity::NONE;
                }
            }
            safe &= found;
        } else service.reset();
        engine.thermal(safe, now());
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}
}  // namespace

int main(int, char** argv) {
    android::base::InitLogging(argv, android::base::LogdLogger(android::base::SYSTEM));
    gold::power::PosixNodeIo io;
    gold::power::NodeBackend backend(io);
    PowerEngine engine(backend, [&](int pid) { return gold::power::processGeneration(io, pid); });
    if (!engine.initialize(now())) { LOG(ERROR) << "Power backend unavailable: " << backend.error(); return 1; }
    std::signal(SIGTERM, stopSignal);
    std::signal(SIGINT, stopSignal);
    ABinderProcess_setThreadPoolMaxThreadCount(2);
    android::hardware::configureRpcThreadpool(2, false);
    auto power = ndk::SharedRefBase::make<Power>(engine);
    android::sp<Perf> perf = new Perf(engine);
    android::sp<MtkPower> mtk = new MtkPower;
    const std::string instance = std::string(p::IPower::descriptor) + "/default";
    if (AServiceManager_addService(power->asBinder().get(), instance.c_str()) != STATUS_OK ||
            perf->registerAsService() != android::OK || mtk->registerAsService() != android::OK) {
        engine.stop(now());
        LOG(ERROR) << "Power registration failed";
        return 1;
    }
    // One expiry/owner worker, independent of thermal Binder calls. A hung
    // thermal service becomes stale and cannot keep performance votes alive.
    std::thread([&] {
        while (!stopping.load()) {
            engine.tick(now());
            engine.waitForWork(now());
        }
        for (int attempt = 0; attempt < 5; ++attempt) {
            engine.stop(now());
            if (!engine.status().requests.dirty) _exit(0);
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        LOG(ERROR) << "Power vote reset failed during shutdown";
        _exit(1);
    }).detach();
    std::thread(thermalWorker, std::ref(engine)).detach();
    ABinderProcess_joinThreadPool();
    return 1;
}
