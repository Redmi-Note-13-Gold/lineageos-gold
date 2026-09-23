// SPDX-License-Identifier: Apache-2.0
// Linux host integration test for the actual merged Recovery FUSE source.
// Synthetic bytes only. Each mount point is created by mkdtemp and removed.
// This does not install an OTA or claim Android/Scudo peak-memory acceptance.
#include "fuse_sideload.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <memory>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>

constexpr uint32_t kBlock = 65536;
constexpr uint64_t kSize = 1174891230;
constexpr uint32_t kBlocks = (kSize + kBlock - 1) / kBlock;
constexpr uint32_t kRefetch = 600;
static std::array<void*, 1024> allocations{};
static unsigned live, peak, failures;
static bool failAllocation;

extern "C" void* __real_malloc(size_t);
extern "C" void __real_free(void*);
extern "C" void* __wrap_malloc(size_t size) {
    // Two working buffers plus 32 cached blocks. The next cache allocation
    // returns null once; subsequent allocations work normally.
    if (size == kBlock && failAllocation && live == 34 && failures == 0) {
        ++failures;
        return nullptr;
    }
    void* p = __real_malloc(size);
    if (size == kBlock && p) {
        auto slot = std::find(allocations.begin(), allocations.end(), nullptr);
        if (slot == allocations.end()) _exit(90);
        *slot = p;
        peak = std::max(peak, ++live);
    }
    return p;
}
extern "C" void __wrap_free(void* p) {
    if (p) {
        auto slot = std::find(allocations.begin(), allocations.end(), p);
        if (slot != allocations.end()) { *slot = nullptr; --live; }
    }
    __real_free(p);
}

struct Shared {
    uint32_t reads[kBlocks];
    uint32_t finished, mallocPeak, mallocLive, mallocFailures;
    int result;
};

class Provider final : public FuseDataProvider {
  public:
    Provider(Shared* shared, bool tamper) : FuseDataProvider(kSize, kBlock), shared_(shared), tamper_(tamper) {}
    bool Valid() const override { return true; }
    bool ReadBlockAlignedData(uint8_t* output, uint32_t count, uint32_t block) const override {
        if (block >= kBlocks) return false;
        uint32_t seen = ++shared_->reads[block];
        uint8_t value = static_cast<uint8_t>(block * 131U + 17U);
        if (tamper_ && block == kRefetch && seen > 1) value ^= 0x80;
        memset(output, value, count);
        return true;
    }
  private:
    Shared* shared_;
    bool tamper_;
};

static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

static void runCase(const std::string& directory, const char* label, bool tamper, bool fail) {
    std::string pattern = directory + "/gold-fuse-XXXXXX";
    require(mkdtemp(pattern.data()) != nullptr, "mkdtemp failed");
    Shared* shared = static_cast<Shared*>(mmap(nullptr, sizeof(Shared), PROT_READ | PROT_WRITE,
                                             MAP_SHARED | MAP_ANONYMOUS, -1, 0));
    require(shared != MAP_FAILED, "shared counters failed");
    pid_t child = fork();
    require(child >= 0, "fork failed");
    if (child == 0) {
        alarm(90);
        failAllocation = fail;
        shared->result = run_fuse_sideload(std::make_unique<Provider>(shared, tamper), pattern.c_str());
        shared->mallocPeak = peak;
        shared->mallocLive = live;
        shared->mallocFailures = failures;
        shared->finished = 1;
        _exit(shared->result == 0 ? 0 : 1);
    }
    int package = -1;
    void* buffer = nullptr;
    bool reaped = false;
    try {
        // O_DIRECT prevents the Linux page cache from hiding provider refetches.
        for (unsigned attempt = 0; attempt < 200 && package == -1; ++attempt) {
            package = open((pattern + "/package.zip").c_str(), O_RDONLY | O_DIRECT);
            if (package == -1) std::this_thread::sleep_for(std::chrono::milliseconds(25));
        }
        require(package >= 0, "synthetic FUSE mount did not become readable");
        require(posix_memalign(&buffer, 4096, kBlock) == 0, "aligned reader allocation failed");
        // Read the full OTA-sized virtual file in the normal case. The other
        // cases exceed the real 512-block cap before testing an evicted block.
        uint32_t count = (!tamper && !fail) ? kBlocks : 1024;
        for (uint32_t block = 0; block < count; ++block) {
            ssize_t bytes = pread(package, buffer, kBlock, uint64_t(block) * kBlock);
            size_t expected = std::min<uint64_t>(kBlock, kSize - uint64_t(block) * kBlock);
            // The production FUSE code deliberately zero-pads a read spanning
            // EOF for mmap clients. O_DIRECT exposes that full padded reply.
            if (bytes != kBlock) {
                throw std::runtime_error("sequential FUSE read block=" + std::to_string(block)
                    + " bytes=" + std::to_string(bytes) + " expected=" + std::to_string(expected)
                    + " errno=" + std::to_string(errno));
            }
            uint8_t value = static_cast<uint8_t>(block * 131U + 17U);
            require(std::all_of(static_cast<uint8_t*>(buffer), static_cast<uint8_t*>(buffer) + expected,
                                [value](uint8_t byte) { return byte == value; }), "provider bytes changed");
            require(std::all_of(static_cast<uint8_t*>(buffer) + expected,
                                static_cast<uint8_t*>(buffer) + bytes,
                                [](uint8_t byte) { return byte == 0; }), "EOF padding is not zero");
        }
        uint32_t before = shared->reads[kRefetch];
        errno = 0;
        ssize_t bytes = pread(package, buffer, kBlock, uint64_t(kRefetch) * kBlock);
        require(shared->reads[kRefetch] > before, "page/cache hit hid expected provider refetch");
        if (tamper) require(bytes == -1 && errno == EIO, "changed block was not rejected by retained SHA256");
        else require(bytes == kBlock, "unchanged evicted block could not be refetched");
        close(package); package = -1;
        struct stat ignored{};
        stat((pattern + "/exit").c_str(), &ignored);
        int status = 0;
        struct rusage usage{};
        require(wait4(child, &status, 0, &usage) == child, "wait4 failed");
        reaped = true;
        require(WIFEXITED(status) && WEXITSTATUS(status) == 0 && shared->finished,
                "FUSE did not exit successfully");
        require(shared->mallocLive == 0, "FUSE block allocation leaked");
        require(shared->mallocPeak == (fail ? 34U : 514U), "unexpected block cache peak");
        require(shared->mallocFailures == (fail ? 1U : 0U), "allocation failure path not exercised");
        printf("{\"case\":\"%s\",\"passed\":true,\"file_bytes\":%llu,\"blocks_read\":%u,"
               "\"refetch_requests\":%u,\"peak_64k_allocations\":%u,\"peak_cache_bytes\":%u,"
               "\"live_block_allocations_at_exit\":%u,\"injected_allocation_failures\":%u,"
               "\"host_child_max_rss_kib\":%ld}\n", label, static_cast<unsigned long long>(kSize),
               count, shared->reads[kRefetch], shared->mallocPeak, (shared->mallocPeak - 2) * kBlock,
               shared->mallocLive, shared->mallocFailures, usage.ru_maxrss);
    } catch (...) {
        if (package >= 0) close(package);
        if (!reaped) {
            // Only the child and new empty mount directory owned by this case.
            umount2(pattern.c_str(), MNT_DETACH);
            kill(child, SIGTERM);
            waitpid(child, nullptr, 0);
        }
        free(buffer);
        munmap(shared, sizeof(Shared));
        rmdir(pattern.c_str());
        throw;
    }
    free(buffer);
    munmap(shared, sizeof(Shared));
    require(rmdir(pattern.c_str()) == 0, "owned FUSE mount directory remains");
}

int main(int argc, char** argv) {
    if (argc != 2 || getuid() != 0) return 2;
    try {
        runCase(argv[1], "ota_size_cache_cap_and_refetch", false, false);
        runCase(argv[1], "evicted_block_tamper_rejected", true, false);
        runCase(argv[1], "allocation_failure_fallback", false, true);
    } catch (const std::exception& error) {
        fprintf(stderr, "FAIL: %s\n", error.what());
        return 1;
    }
}
