// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <array>
#include <cerrno>
#include <cstdint>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <unistd.h>

namespace gold::power {
// Global 6.6.118 xiaomi_touch copies 256 int32s, even though the ioctl size
// field is one int. Its payload is [mode, value], without a touch-id prefix.
// FocalTech mode 14 updates the double-tap bit independently of the AOD bit,
// including requests staged while the panel is suspended.
inline int setDoubleTapWake(bool enabled) {
    const int fd = open("/dev/xiaomi-touch", O_RDWR | O_CLOEXEC);
    if (fd < 0) return -errno;
    std::array<int32_t, 256> values{};
    values[0] = 14;
    values[1] = enabled ? 1 : 0;
    int result;
    do {
        result = ioctl(fd, _IOWR('T', 0, int32_t), values.data());
    } while (result < 0 && errno == EINTR);
    const int error = result < 0 ? -errno : result != 0 ? -EIO :
            values[0] < 0 ? values[0] : values[0] != 0 ? -EIO : 0;
    close(fd);
    return error;
}
}  // namespace gold::power
