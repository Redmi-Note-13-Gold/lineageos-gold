// SPDX-License-Identifier: Apache-2.0
#include <aidl/android/hardware/vibrator/BnVibratorCallback.h>
#include <gtest/gtest.h>

#include "Vibrator.h"

namespace aidl::android::hardware::vibrator {
namespace {

class Callback final : public BnVibratorCallback {
  public:
    ndk::ScopedAStatus onComplete() override {
        ADD_FAILURE() << "An unsupported request must not schedule a callback";
        return ndk::ScopedAStatus::ok();
    }
};

TEST(GoldVibrator, CapabilityQueryOverwritesOutput) {
    auto vibrator = ndk::SharedRefBase::make<Vibrator>();
    int32_t capabilities = -1;
    ASSERT_TRUE(vibrator->getCapabilities(&capabilities).isOk());
    EXPECT_EQ(0, capabilities);
}

TEST(GoldVibrator, UnimplementedEffectsAreNotAdvertised) {
    auto vibrator = ndk::SharedRefBase::make<Vibrator>();
    std::vector<Effect> effects{Effect::CLICK};
    ASSERT_TRUE(vibrator->getSupportedEffects(&effects).isOk());
    EXPECT_TRUE(effects.empty());
    int32_t duration = 0;
    EXPECT_EQ(EX_UNSUPPORTED_OPERATION,
              vibrator->perform(Effect::CLICK, EffectStrength::MEDIUM, nullptr,
                                &duration).getExceptionCode());
}

TEST(GoldVibrator, RejectsInvalidDurationBeforeAccessingDriver) {
    auto vibrator = ndk::SharedRefBase::make<Vibrator>();
    EXPECT_EQ(EX_ILLEGAL_ARGUMENT, vibrator->on(-1, nullptr).getExceptionCode());
    EXPECT_EQ(EX_ILLEGAL_ARGUMENT, vibrator->on(0, nullptr).getExceptionCode());
}

TEST(GoldVibrator, RejectsUnsupportedCallbackBeforeAccessingDriver) {
    auto vibrator = ndk::SharedRefBase::make<Vibrator>();
    auto callback = ndk::SharedRefBase::make<Callback>();
    EXPECT_EQ(EX_UNSUPPORTED_OPERATION, vibrator->on(10, callback).getExceptionCode());
}

}  // namespace
}  // namespace aidl::android::hardware::vibrator
