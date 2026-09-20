// SPDX-License-Identifier: Apache-2.0
#include "ChargeCounter.h"

#include <iostream>

int main() {
    struct Example {
        int32_t raw;
        std::optional<int32_t> expected;
    };
    const Example examples[] = {
        {4515, 4515000},  // Real device: 91%, full charge 4962300 uAh.
        {0, 0},
        {1, 1000},      // No low-charge heuristic or discontinuity.
        {20001, 20001000},
        {-1, std::nullopt},
        {2147483, 2147483000},
        {2147484, std::nullopt},
        {std::numeric_limits<int32_t>::max(), std::nullopt},
    };
    for (const auto& example : examples) {
        if (gold::ChargeCounterUah(example.raw) != example.expected) {
            std::cerr << "Charge counter conversion failed for " << example.raw << '\n';
            return 1;
        }
    }
    std::cout << "Eight charge-counter unit and boundary cases passed\n";
    return 0;
}
