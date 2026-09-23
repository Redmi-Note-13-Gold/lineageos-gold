// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <cstdint>
#include <limits>
#include <optional>

namespace gold {

// The pinned Global 6.6.118 battery driver exposes charge_counter in mAh.
// Android's IHealth contract requires uAh. charge_full/current_now already use
// micro-units and must not be rescaled. See validation/device-baseline-20260920.json.
// Review this conversion when replacing the locked kernel; never guess units
// from battery level or the magnitude of a sample.
inline std::optional<int32_t> ChargeCounterUah(int32_t counterMah) {
    if (counterMah < 0 || counterMah > std::numeric_limits<int32_t>::max() / 1000) {
        return std::nullopt;
    }
    return counterMah * 1000;
}

}  // namespace gold
