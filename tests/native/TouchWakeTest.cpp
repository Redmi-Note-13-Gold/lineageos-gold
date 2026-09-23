// SPDX-License-Identifier: Apache-2.0
// Run on Linux with the production header and syscall doubles; no device I/O.
#include <array>
#include <cerrno>
#include <cstdint>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <unistd.h>

static int openError, ioctlError, kernelResult, syscallResult, closes, calls;
static bool expectedEnabled, interruptOnce;
static int fakeOpen(const char* path, int flags, ...) {
    if (std::strcmp(path, "/dev/xiaomi-touch") || flags != (O_RDWR | O_CLOEXEC)) return -1;
    if (openError) { errno = openError; return -1; }
    return 42;
}
static int fakeClose(int fd) { ++closes; return fd == 42 ? 0 : -1; }
static int fakeIoctl(int fd, unsigned long command, ...) {
    ++calls;
    va_list args;
    va_start(args, command);
    auto* values = va_arg(args, int32_t*);
    va_end(args);
    if (fd != 42 || command != _IOWR('T', 0, int32_t) ||
            values[0] != 14 || values[1] != expectedEnabled) { errno = EPROTO; return -1; }
    for (int i = 2; i < 256; ++i) if (values[i]) { errno = EPROTO; return -1; }
    if (interruptOnce) { interruptOnce = false; errno = EINTR; return -1; }
    if (ioctlError) { errno = ioctlError; return -1; }
    values[0] = kernelResult;
    return syscallResult;
}
#define open fakeOpen
#define close fakeClose
#define ioctl fakeIoctl
#include "TouchWake.h"
#undef open
#undef close
#undef ioctl
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "failed line %d\n", __LINE__); return 1; } } while (0)
int main() {
    openError = ENOENT;
    CHECK(gold::power::setDoubleTapWake(true) == -ENOENT && calls == 0 && closes == 0);
    openError = EACCES;
    CHECK(gold::power::setDoubleTapWake(true) == -EACCES && calls == 0 && closes == 0);
    openError = 0; expectedEnabled = true;
    CHECK(gold::power::setDoubleTapWake(true) == 0 && closes == 1);
    expectedEnabled = false;
    CHECK(gold::power::setDoubleTapWake(false) == 0 && closes == 2);
    interruptOnce = true;
    const auto before = calls;
    CHECK(gold::power::setDoubleTapWake(false) == 0 && calls == before + 2 && closes == 3);
    ioctlError = EIO;
    CHECK(gold::power::setDoubleTapWake(false) == -EIO && closes == 4);
    ioctlError = 0; kernelResult = -EINVAL;
    CHECK(gold::power::setDoubleTapWake(false) == -EINVAL && closes == 5);
    kernelResult = 1;
    CHECK(gold::power::setDoubleTapWake(false) == -EIO && closes == 6);
    kernelResult = 0; syscallResult = 4;
    CHECK(gold::power::setDoubleTapWake(false) == -EIO && closes == 7);
    std::puts("9 touch wake protocol and failure cases passed");
}
