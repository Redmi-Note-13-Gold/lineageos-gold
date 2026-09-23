"""Exercise the shipped C adapter with a deterministic Binder transport double."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HEADER = r"""
#pragma once
#include <cerrno>
#include <cstdint>
#include <map>
#include <memory>
#include <vector>
namespace android {
template<class T> class sp {
    std::shared_ptr<T> value;
  public:
    sp() = default;
    explicit sp(T* pointer) : value(pointer) {}
    explicit operator bool() const { return bool(value); }
    T* operator->() const { return value.get(); }
    void clear() { value.reset(); }
    bool operator==(const sp& other) const { return value == other.value; }
};
namespace hardware {
template<class T> using hidl_vec = std::vector<T>;
struct Result {
    int value; bool ok = true;
    bool isOk() const { return ok; }
    operator int32_t() const { return value; }
};
}}
namespace vendor::mediatek::hardware::mtkpower::V1_2 {
class IMtkPerf {
  public:
    inline static android::sp<IMtkPerf> current;
    inline static int lookups = 0;
    bool alive = true, failNext = false;
    int next = 1, acquires = 0, releases = 0, lastHandle = -1;
    std::map<int, std::vector<int32_t>> active;
    static android::sp<IMtkPerf> tryGetService() { ++lookups; return current; }
    android::hardware::Result perfLockAcquire(int handle, unsigned,
            const std::vector<int32_t>& pairs, int) {
        ++acquires; lastHandle = handle;
        if (!alive || failNext) { failNext = false; return {-1, false}; }
        if (handle && !active.count(handle)) return {-ENOENT};
        if (!handle) handle = next++;
        active[handle] = pairs;
        return {handle};
    }
    android::hardware::Result perfLockReleaseSync(int handle, int) {
        ++releases; lastHandle = handle;
        if (!alive) return {-1, false};
        return {active.erase(handle) ? 0 : -ENOENT};
    }
    android::hardware::Result perfCusLockHint(int, unsigned) { return {-EOPNOTSUPP}; }
};
}
"""
HARNESS = r"""
#include "adapter.cpp"
#include <iostream>
#include <set>
#include <thread>
#define CHECK(condition) do { if (!(condition)) { std::cerr << "line " << __LINE__ << ": " << #condition << '\n'; return 1; } } while (0)
int main() {
    using Peer = vendor::mediatek::hardware::mtkpower::V1_2::IMtkPerf;
    Peer::current = android::sp<Peer>(new Peer);
    auto original = Peer::current;
    int pairs[] = {0x0240C000, 100};
    CHECK(perf_lock_acq(0, 0, nullptr, 2) == -EINVAL);
    CHECK(perf_lock_acq(0, 2001, pairs, 2) == -EINVAL);
    CHECK(Peer::lookups == 0);
    int first = perf_lock_acq(0, 0, pairs, 2);
    int second = perf_lock_acq(0, 0, pairs, 2);
    CHECK(first > 0 && second > first && original->active.size() == 2);
    pairs[1] = 150;
    CHECK(perf_lock_acq(first, 0, pairs, 2) == first);
    CHECK(original->active.at(1).at(1) == 150);
    CHECK(perf_lock_rel(first) == 0 && original->active.size() == 1);
    std::cout << "PASS C ABI validation, distinct handles, update and release\n";

    original->alive = false;
    Peer::current = android::sp<Peer>(new Peer);
    CHECK(perf_lock_acq(second, 0, pairs, 2) == -EPIPE);
    CHECK(Peer::lookups == 1 && Peer::current->acquires == 0);
    int fresh = perf_lock_acq(0, 0, pairs, 2);
    CHECK(fresh > second && Peer::current->active.count(1));
    CHECK(perf_lock_rel(first) == -ENOENT && perf_lock_rel(second) == -ENOENT);
    CHECK(perf_lock_acq(second, 0, pairs, 2) == -ENOENT);
    CHECK(Peer::current->active.size() == 1 && Peer::current->releases == 0);
    CHECK(perf_lock_rel(fresh) == 0);
    std::cout << "PASS server restart cannot alias stale handles or replay ambiguous acquisition\n";

    int timed = perf_lock_acq(0, 1, pairs, 2);
    CHECK(timed > 0);
    Peer::current->active.clear(); // Model the independently tested HAL expiry.
    int releases = Peer::current->releases;
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(perf_lock_rel(timed) == -ENOENT && Peer::current->releases == releases);
    std::cout << "PASS expired client handles cannot address later server leases\n";

    std::vector<int> results(8);
    std::vector<std::thread> workers;
    for (size_t i = 0; i < results.size(); ++i)
        workers.emplace_back([&, i] { results[i] = perf_lock_acq(0, 0, pairs, 2); });
    for (auto& worker : workers) worker.join();
    std::set<int> unique(results.begin(), results.end());
    CHECK(unique.size() == results.size() && *unique.begin() > timed);
    CHECK(Peer::current->active.size() == results.size());
    for (int handle : results) CHECK(perf_lock_rel(handle) == 0);
    CHECK(Peer::current->active.empty());
    CHECK(perf_cus_lock_hint(42, 100) == -EOPNOTSUPP);
    std::cout << "PASS concurrent callers and unsupported private hint result\n";
    return 0;
}
"""


class PerfClientTest(unittest.TestCase):
    def test_actual_adapter_lifecycle(self):
        compiler = os.environ.get("CXX") or shutil.which("clang++") or shutil.which("g++")
        self.assertIsNotNone(compiler, "A native C++ compiler is required for the perf adapter test")
        patch = (ROOT / "patches/hardware__mediatek/0002-perf-client-forwarding.patch").read_text()
        added = patch.split("+++ b/libmtkperf_client/mtkperf_client.cpp\n", 1)[1].splitlines()
        self.assertTrue(added[0].startswith("@@ -0,0 +1,"))
        code = "\n".join(line[1:] for line in added[1:] if line.startswith("+")) + "\n"
        with tempfile.TemporaryDirectory(prefix="gold-perf-client-") as directory:
            root = Path(directory)
            header = root / "vendor/mediatek/hardware/mtkpower/1.2/IMtkPerf.h"
            header.parent.mkdir(parents=True)
            header.write_text(HEADER)
            (root / "adapter.cpp").write_text(code)
            (root / "test.cpp").write_text(HARNESS)
            built = subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pthread",
                                    "-I", str(root), str(root / "test.cpp"), "-o", str(root / "test")],
                                   text=True, capture_output=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            tested = subprocess.run([str(root / "test")], text=True, capture_output=True, timeout=10)
            self.assertEqual(tested.returncode, 0, tested.stdout + tested.stderr)
            self.assertEqual(tested.stdout.count("PASS "), 4, tested.stdout)


if __name__ == "__main__":
    unittest.main()
