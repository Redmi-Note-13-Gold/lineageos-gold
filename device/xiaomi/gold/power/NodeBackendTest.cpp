// SPDX-License-Identifier: Apache-2.0
#include "NodeBackend.h"
#include "PowerEngine.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <csignal>
#include <dlfcn.h>
#include <functional>
#include <future>
#include <iostream>
#include <poll.h>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <unistd.h>

using namespace gold::power;

struct FakeNodes final : NodeIo {
    std::map<std::string, std::string> files{
        {"/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies", "2000000 1000000 500000\n"},
        {"/sys/devices/system/cpu/cpufreq/policy6/scaling_available_frequencies", "2400000 1500000 725000\n"},
        {"/proc/ppm/policy_status", "PPM_POLICY_THERMAL: enabled\nPPM_POLICY_DLPT: enabled\nPPM_POLICY_SYS_BOOST: enabled\n"},
        {NodeBackend::kPpm, "[1] WIFI: 0\t(1)(-1)(-1)(-1)\n[2] PERFSERV: 0\t(-1)(-1)(-1)(-1)\n[8] XM_THERM: 0\t(-1)(1)(-1)(1)\n"},
        {NodeBackend::kUclamp, "0.00\n"}, {NodeBackend::kPreferIdle, "0\n"}, {NodeBackend::kIdleTime, "50\n"}};
    std::array<std::array<int, 2>, 2> indices{{{{-1, -1}}, {{-1, -1}}}};
    std::vector<std::pair<std::string, std::string>> writes;
    std::string failPath, ignorePath;
    int failures = 0;
    bool read(const std::string& path, std::string* value) override {
        auto it = files.find(path);
        if (it == files.end()) return false;
        *value = it->second;
        return true;
    }
    bool write(const std::string& path, const std::string& value) override {
        writes.emplace_back(path, value);
        if (path == failPath && failures-- > 0) return false;
        if (path == ignorePath) return true;
        if (path == NodeBackend::kPpm) {
            int user, cluster, minimum, maximum;
            std::istringstream input(value);
            if (!(input >> user >> cluster >> minimum >> maximum) || user != 2 || cluster < 0 || cluster > 1) return false;
            const std::array<int, 3> table = cluster == 0 ? std::array<int, 3>{2000000, 1000000, 500000} :
                    std::array<int, 3>{2400000, 1500000, 725000};
            const auto index = [&](int frequency) {
                return frequency == -1 ? -1 : static_cast<int>(std::find(table.begin(), table.end(), frequency) - table.begin());
            };
            indices[cluster] = {index(minimum), index(maximum)};
            int global = 0;
            const auto start = files[path].find("[2] PERFSERV:");
            if (start != std::string::npos) {
                std::istringstream globalValue(files[path].substr(start + 13));
                globalValue >> global;
            }
            files[path] = "[1] WIFI: 0\t(1)(-1)(-1)(-1)\n[2] PERFSERV: " + std::to_string(global) + "\t(" +
                std::to_string(indices[0][0]) + ")(" + std::to_string(indices[0][1]) + ")(" +
                std::to_string(indices[1][0]) + ")(" + std::to_string(indices[1][1]) +
                ")\n[8] XM_THERM: 0\t(-1)(1)(-1)(1)\n";
            return true;
        }
        if (files.find(path) == files.end()) return false;
        files[path] = value;
        return true;
    }
};

void check(bool condition) { if (!condition) throw std::runtime_error("expectation failed"); }
struct Fixture {
    FakeNodes io;
    NodeBackend backend{io};
    Values reset;
    Fixture() {
        check(backend.discover());
        for (const auto& resource : backend.resources()) reset[resource.id] = resource.reset;
        check(backend.apply(reset));
        io.writes.clear();
    }
};

std::atomic<bool> probeStop{false};
void probeSignal(int) { probeStop.store(true); }
int hardwareProbe() {
    PosixNodeIo io;
    // Refuse to take nodes away from another active Power service/request.
    for (const auto& [path, expected] : std::map<std::string, double>{
            {NodeBackend::kUclamp, 0}, {NodeBackend::kPreferIdle, 0}}) {
        std::string value;
        double actual;
        if (!io.read(path, &value) || !(std::istringstream(value) >> actual) || actual != expected) {
            std::cerr << "Resource is not at the reviewed baseline: " << path << '\n'; return 2;
        }
    }
    std::string ppm;
    if (!io.read(NodeBackend::kPpm, &ppm) || ppm.find("[2] PERFSERV: 0\t(-1)(-1)(-1)(-1)") == std::string::npos) {
        std::cerr << "PERFSERV is not idle; refusing a parallel resource owner\n"; return 2;
    }
    NodeBackend backend(io);
    if (!backend.discover()) { std::cerr << backend.error() << '\n'; return 2; }
    RequestManager manager(backend.resources(), backend, 2000);
    struct Reset {
        RequestManager& manager;
        ~Reset() { manager.setEnabled(false, 0); }
    } reset{manager};
    std::signal(SIGINT, probeSignal);
    std::signal(SIGTERM, probeSignal);
    const auto clock = [] { return std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count(); };
    auto generation = processGeneration(io, getpid());
    if (!generation) return 2;
    Owner owner{static_cast<int>(getuid()), getpid(), *generation};
    // The frequency request is derived from this kernel's maximum and rounded
    // to its own OPP table. Every diagnostic lease expires after 150 ms.
    const int floor = backend.resources().front().maximum / 2;
    for (const Values& values : {Values{{kTopAppUclamp, 10}}, Values{{kCpu0Min, floor}}}) {
        if (probeStop.load()) return 130;
        Millis start = clock();
        if (manager.acquire(owner, 0, 150, values, start) <= 0) {
            std::cerr << "Acquire/readback failed: " << backend.error() << '\n'; return 1;
        }
        for (const auto& [id, value] : backend.effective()) std::cout << "active 0x" << std::hex << id << std::dec << '=' << value << '\n';
        while (clock() < start + 160 && !probeStop.load()) std::this_thread::sleep_for(std::chrono::milliseconds(5));
        if (!manager.expire(clock()) || manager.snapshot().requests != 0) return 1;
        std::cout << "PASS hardware write/readback and expiry reset\n";
    }
    return manager.setEnabled(false, clock()) ? 0 : 1;
}

int clientProbe() {
    // This probe only calls the installed C ABI. All resource writes and
    // readbacks must succeed inside the running HAL's enforcing SELinux domain.
    // Run with framework experiments disabled and no competing media workload.
    PosixNodeIo io;
    const auto readScalar = [&](const char* path) {
        std::string text;
        double value;
        if (!io.read(path, &text) || !(std::istringstream(text) >> value))
            throw std::runtime_error(std::string("cannot read ") + path);
        return value;
    };
    void* library = dlopen(sizeof(void*) == 8 ? "/vendor/lib64/libmtkperf_client_vendor.so" :
                                             "/vendor/lib/libmtkperf_client_vendor.so", RTLD_NOW | RTLD_LOCAL);
    if (!library) { std::cerr << dlerror() << '\n'; return 2; }
    const auto acquire = reinterpret_cast<int (*)(int, int, int*, int)>(dlsym(library, "perf_lock_acq"));
    const auto release = reinterpret_cast<int (*)(int)>(dlsym(library, "perf_lock_rel"));
    if (!acquire || !release) { std::cerr << "missing reviewed perf C ABI\n"; return 2; }
    struct Leases {
        int (*release)(int);
        std::vector<int> handles;
        ~Leases() { for (int handle : handles) release(handle); }
    } leases{release, {}};
    const auto request = [&](int handle, int duration, std::vector<int> pairs) {
        int result = acquire(handle, duration, pairs.data(), pairs.size());
        if (result <= 0) throw std::runtime_error("C ABI acquire failed: " + std::to_string(result));
        if (!handle) leases.handles.push_back(result);
        else check(result == handle);
        return result;
    };
    try {
        if (readScalar(NodeBackend::kUclamp) != 0 || readScalar(NodeBackend::kPreferIdle) != 0) {
            std::cerr << "Resources are busy; refusing to attribute another caller's votes\n"; return 2;
        }
        int first = request(0, 1000, {kTopAppUclamp, 10});
        check(readScalar(NodeBackend::kUclamp) == 10);
        int second = request(0, 1400, {kTopAppUclamp, 20});
        check(second != first && readScalar(NodeBackend::kUclamp) == 20);
        request(first, 1000, {kTopAppUclamp, 30});
        check(readScalar(NodeBackend::kUclamp) == 30);
        check(release(first) == 0 && readScalar(NodeBackend::kUclamp) == 20);
        std::cout << "PASS C ABI acquire, concurrent maximum, update and independent release\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(1600));
        check(readScalar(NodeBackend::kUclamp) == 0);
        check(release(second) == -ENOENT);
        std::cout << "PASS HAL worker timeout and expired-handle rejection\n";
        int display[] = {kDisplayIdleTime, 100};
        check(acquire(0, 0, display, 2) == -EOPNOTSUPP);
        std::cout << "PASS shared display scalar explicitly unsupported\n";
        int unknown[] = {kTopAppUclamp, 10, 0x7fffffff, 1};
        check(acquire(0, 100, unknown, 4) == -EOPNOTSUPP);
        check(readScalar(NodeBackend::kUclamp) == 0);
        int invalid[] = {kTopAppUclamp, 10};
        check(acquire(0, 0, invalid, 2) == -EINVAL);
        check(acquire(0, 2001, invalid, 2) == -EINVAL);
        std::cout << "PASS unknown resources and unsafe duration rejected without partial action\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL C ABI / HAL lifecycle: " << error.what() << '\n';
        return 1;
    }
}

int clientRecoveryProbe(bool restart) {
    PosixNodeIo io;
    const auto clamp = [&] {
        std::string text;
        double value;
        if (!io.read(NodeBackend::kUclamp, &text) || !(std::istringstream(text) >> value))
            throw std::runtime_error("cannot read uclamp");
        return value;
    };
    void* library = dlopen(sizeof(void*) == 8 ? "/vendor/lib64/libmtkperf_client_vendor.so" :
                                             "/vendor/lib/libmtkperf_client_vendor.so", RTLD_NOW | RTLD_LOCAL);
    if (!library) { std::cerr << dlerror() << '\n'; return 2; }
    const auto acquire = reinterpret_cast<int (*)(int, int, int*, int)>(dlsym(library, "perf_lock_acq"));
    const auto release = reinterpret_cast<int (*)(int)>(dlsym(library, "perf_lock_rel"));
    if (!acquire || !release) return 2;
    int first = 0, second = 0;
    try {
        if (clamp() != 0) { std::cerr << "uclamp is busy\n"; return 2; }
        int values[] = {kTopAppUclamp, 10};
        first = acquire(0, 2000, values, 2);
        check(first > 0 && clamp() == 10);
        if (!restart) {
            // Deliberately exit without perf_lock_rel. Observe the actual HAL
            // reset after this process exits and before the 2000 ms timeout.
            std::cout << "EXITING_WITH_LEASE handle=" << first << " duration_ms=2000" << std::endl;
            return 0;
        }
        std::cout << "READY_FOR_HAL_RESTART handle=" << first << std::endl;
        pollfd input{STDIN_FILENO, POLLIN, 0};
        char command = 0;
        if (poll(&input, 1, 10000) != 1 || read(STDIN_FILENO, &command, 1) != 1 || command != 'G')
            throw std::runtime_error("coordinator did not confirm HAL restart");
        check(clamp() == 0);
        values[1] = 20;
        second = acquire(0, 2000, values, 2);
        // The first operation on the dead Binder reports the failure without
        // replaying it. This separate diagnostic request may use the new HAL.
        check(second == -EPIPE);
        second = acquire(0, 2000, values, 2);
        check(second > 0 && second != first && clamp() == 20);
        check(release(first) == -ENOENT && clamp() == 20);
        check(release(second) == 0 && clamp() == 0);
        second = 0;
        std::cout << "PASS HAL restart rejects stale C handles without releasing the new vote\n";
        return 0;
    } catch (const std::exception& error) {
        if (second > 0) release(second);
        if (first > 0) release(first);
        std::cerr << "FAIL C ABI recovery: " << error.what() << '\n';
        return 1;
    }
}

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--hardware") return hardwareProbe();
    if (argc == 2 && std::string(argv[1]) == "--client") return clientProbe();
    if (argc == 2 && std::string(argv[1]) == "--client-exit") return clientRecoveryProbe(false);
    if (argc == 2 && std::string(argv[1]) == "--client-restart") return clientRecoveryProbe(true);
    if (argc != 1) return 2;
    int passed = 0, failed = 0;
    const auto test = [&](const char* name, const std::function<void(Fixture&)>& body) {
        try {
            Fixture f;
            body(f);
            ++passed;
            std::cout << "PASS " << name << '\n';
        } catch (const std::exception& e) {
            ++failed;
            std::cerr << "FAIL " << name << ": " << e.what() << '\n';
        }
    };
    test("unchanged aggregate does not rewrite nodes", [](auto& f) {
        check(f.backend.apply(f.reset) && f.io.writes.empty());
    });
    test("PPM writes only PERFSERV and preserves other users", [](auto& f) {
        auto desired = f.reset;
        desired[kCpu0Min] = 1000000;
        check(f.backend.apply(desired));
        check(f.io.writes.size() == 1 && f.io.writes[0].second == "2 0 1000000 -1\n");
        check(f.io.files[NodeBackend::kPpm].find("[8] XM_THERM: 0\t(-1)(1)(-1)(1)") != std::string::npos);
        check(f.backend.apply(f.reset));
        check(f.io.writes.back().second == "2 0 -1 -1\n");
    });
    test("frequency floors round up and caps round down to actual OPPs", [](auto& f) {
        auto desired = f.reset;
        desired[kCpu0Min] = 750000;
        desired[kCpu1Max] = 2000000;
        check(f.backend.apply(desired));
        check(f.backend.effective().at(kCpu0Min) == 1000000 && f.backend.effective().at(kCpu1Max) == 1500000);
    });
    test("maximum constraint wins over a conflicting floor", [](auto& f) {
        auto desired = f.reset;
        desired[kCpu0Min] = 2000000;
        desired[kCpu0Max] = 1000000;
        check(f.backend.apply(desired));
        check(f.io.writes.back().second == "2 0 1000000 1000000\n");
    });
    test("unknown out of range or incomplete requests never write", [](auto& f) {
        auto desired = f.reset;
        desired[kCpu0Min] = 0;
        check(!f.backend.apply(desired));
        desired = f.reset; desired[kCpu1Max] = 3000000;
        check(!f.backend.apply(desired));
        desired = f.reset; desired[123] = 1;
        check(!f.backend.apply(desired));
        desired = f.reset; desired.erase(kCpu0Min);
        check(!f.backend.apply(desired) && f.io.writes.empty());
    });
    test("write success with no kernel action is rejected", [](auto& f) {
        f.io.ignorePath = NodeBackend::kPpm;
        auto desired = f.reset;
        desired[kCpu1Min] = 1500000;
        check(!f.backend.apply(desired) && !f.backend.error().empty());
        check(f.backend.effective() == f.reset);
    });
    test("partial scalar failure rolls back PPM and previous scalars", [](auto& f) {
        f.io.failPath = NodeBackend::kUclamp; f.io.failures = 1;
        auto desired = f.reset;
        desired[kCpu0Min] = 1000000; desired[kTopAppPreferIdle] = 1; desired[kTopAppUclamp] = 40;
        check(!f.backend.apply(desired));
        check(f.backend.effective() == f.reset && f.io.indices[0][0] == -1 && f.io.files[NodeBackend::kUclamp] == "0\n");
        check(f.backend.apply(desired) && f.backend.effective() == desired);
    });
    test("failed rollback cannot publish an applied state", [](auto& f) {
        f.io.failPath = NodeBackend::kPpm; f.io.failures = 3;
        auto desired = f.reset; desired[kCpu0Min] = 1000000;
        check(!f.backend.apply(desired) && f.backend.effective() == f.reset);
        check(!f.backend.apply(f.reset));
        check(f.backend.apply(f.reset));
    });
    test("kernel changes are detected and reconciled", [](auto& f) {
        f.io.files[NodeBackend::kUclamp] = "90\n";
        check(f.backend.apply(f.reset) && f.io.files[NodeBackend::kUclamp] == "0\n");
    });
    test("malformed or external PPM global votes cannot look applied", [](auto& f) {
        f.io.files[NodeBackend::kPpm] = "[2] PERFSERV: 900000\t(-1)(-1)(-1)(-1)\n";
        check(!f.backend.apply(f.reset));
    });
    test("missing thermal arbitration refuses initialization", [](auto& f) {
        f.io.files["/proc/ppm/policy_status"] = "PPM_POLICY_SYS_BOOST: enabled\n";
        check(!f.backend.discover() && f.backend.resources().empty());
    });
    test("unexpected OPP ordering refuses initialization", [](auto& f) {
        f.io.files["/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies"] = "500000 2000000\n";
        check(!f.backend.discover());
    });
    test("manager expiration really resets hardware votes", [](auto& f) {
        RequestManager manager(f.backend.resources(), f.backend, 2000);
        check(manager.acquire({1000, 42, 3}, 0, 100, {{kCpu1Min, 1500000}, {kTopAppUclamp, 40}}, 10) > 0);
        check(f.io.indices[1][0] == 1);
        check(manager.expire(110) && f.io.indices[1][0] == -1 && f.io.files[NodeBackend::kUclamp] == "0\n");
    });
    test("failed kernel action never returns a live handle", [](auto& f) {
        RequestManager manager(f.backend.resources(), f.backend, 2000);
        check(manager.expire(0));
        f.io.ignorePath = NodeBackend::kUclamp;
        check(manager.acquire({1000, 42, 3}, 0, 100, {{kTopAppUclamp, 40}}, 0) < 0);
        check(manager.snapshot().requests == 0);
    });
    const auto generation = [](int pid) -> std::optional<uint64_t> {
        return pid == 42 || pid == 43 ? std::optional<uint64_t>{5} : std::nullopt;
    };
    test("unknown thermal or display state refuses a vendor boost", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        check(engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 40}, 0) < 0);
        engine.thermal(true, 0);
        check(engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 40}, 0) < 0);
        engine.interactive(true, 0);
        check(engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 40}, 0) > 0);
    });
    test("shared display state neither gates initialization nor gets overwritten", [&](auto& f) {
        f.io.files.erase(NodeBackend::kIdleTime);
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        f.io.files[NodeBackend::kIdleTime] = "34";
        check(engine.acquire(1046, 42, 0, 0, {kDisplayIdleTime, 100}, 0) == -EOPNOTSUPP);
        int handle = engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 20}, 0);
        check(handle > 0 && f.io.files[NodeBackend::kIdleTime] == "34");
        f.io.files[NodeBackend::kIdleTime] = "50";
        check(engine.release(1046, 42, handle, 10) == 0);
        check(std::none_of(f.io.writes.begin(), f.io.writes.end(),
                [](const auto& write) { return write.first == NodeBackend::kIdleTime; }));
    });
    test("unavailable backend rejects requests and retries with all cached policy gates", [&](auto& f) {
        const auto frequencies = f.io.files["/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies"];
        f.io.files.erase("/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies");
        PowerEngine engine(f.backend, generation);
        check(!engine.initialize(0) && !engine.status().ready);
        check(engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 20}, 1) == -ENODEV);
        engine.interactive(true, 10); engine.thermal(true, 10); engine.lowPower(true, 10);
        f.io.files["/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies"] = frequencies;
        engine.tick(999); check(!engine.status().ready);
        engine.tick(1000); check(engine.status().ready && !engine.status().requests.enabled);
        check(engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 20}, 1001) == -EAGAIN);
        engine.displayInactive(true, 1002); engine.lowPower(false, 1002);
        check(!engine.status().requests.enabled);
        engine.displayInactive(false, 1003);
        check(engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 20}, 1003) > 0);
    });
    test("backend recovery does not reuse a stale thermal approval", [&](auto& f) {
        const auto table = f.io.files["/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies"];
        f.io.files.erase("/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies");
        PowerEngine engine(f.backend, generation); check(!engine.initialize(0));
        engine.interactive(true, 0); engine.thermal(true, 0);
        f.io.files["/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies"] = table;
        engine.tick(3001);
        check(engine.status().ready && !engine.status().requests.enabled);
        engine.thermal(true, 3002);
        check(engine.status().requests.enabled);
    });
    test("manager checks an unchanged lease against the real backend", [&](auto& f) {
        RequestManager manager(f.backend.resources(), f.backend, 2000);
        int handle = manager.acquire({1000, 42, 3}, 0, 100, {{kTopAppUclamp, 40}}, 0);
        check(handle > 0);
        f.io.files[NodeBackend::kUclamp] = "0";
        check(manager.acquire({1000, 43, 4}, 0, 80, {{kTopAppUclamp, 20}}, 1) > 0);
        check(f.io.files[NodeBackend::kUclamp] == "40\n");
        f.io.files[NodeBackend::kUclamp] = "0";
        f.io.ignorePath = NodeBackend::kUclamp;
        check(manager.acquire({1000, 43, 4}, 0, 80, {{kTopAppUclamp, 20}}, 2) == -EIO);
        check(manager.snapshot().dirty && manager.snapshot().requests == 2);
        f.io.ignorePath.clear();
        check(manager.expire(3) && !manager.snapshot().dirty);
    });
    test("framework and vendor votes share one aggregate", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        engine.launch(true, 40, 0); engine.interaction(0, 20, 0);
        int handle = engine.acquire(1046, 42, 0, 800, {kTopAppUclamp, 60}, 0);
        check(handle > 0 && engine.status().requests.requests == 3);
        engine.launch(false, 40, 50); engine.tick(200);
        check(f.backend.effective().at(kTopAppUclamp) == 60);
        check(engine.release(1046, 42, handle, 300) == 0);
        check(f.backend.effective().at(kTopAppUclamp) == 0);
    });
    test("repeated interaction updates instead of adding leases", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        for (int now = 0; now < 50; ++now) engine.interaction(120, 20, now);
        check(engine.status().requests.requests == 1);
        engine.tick(168); check(f.backend.effective().at(kTopAppUclamp) == 20);
        engine.tick(169); check(f.backend.effective().at(kTopAppUclamp) == 0);
    });
    test("audio mode is persistent, idempotent, and explicitly released", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        engine.audioStreaming(0, true, 0); engine.audioStreaming(0, true, 100);
        check(engine.status().requests.requests == 1);
        engine.tick(2001);
        check(f.backend.effective().at(kTopAppPreferIdle) == 1);
        engine.audioStreaming(1, true, 2002);
        check(engine.status().requests.requests == 2);
        engine.audioStreaming(1, false, 2002);
        check(engine.status().requests.requests == 1 && f.backend.effective().at(kTopAppPreferIdle) == 1);
        engine.audioStreaming(0, false, 2002);
        check(engine.status().requests.requests == 0 && f.backend.effective().at(kTopAppPreferIdle) == 0);
        engine.audioStreaming(0, true, 2003); engine.lowPower(true, 2004);
        check(engine.status().requests.requests == 0 && f.backend.effective().at(kTopAppPreferIdle) == 0);
        engine.lowPower(false, 2005);
        check(f.backend.effective().at(kTopAppPreferIdle) == 0);
    });
    test("display and power restrictions cannot clear each other", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0); engine.launch(true, 40, 0);
        engine.lowPower(true, 10); engine.displayInactive(true, 10); engine.interactive(false, 10);
        engine.lowPower(false, 20); engine.interactive(true, 20); engine.launch(true, 40, 20);
        check(engine.status().requests.requests == 0);
        engine.displayInactive(false, 30); engine.launch(true, 40, 30);
        check(engine.status().requests.requests == 1);
        engine.deviceIdle(true, 40); check(engine.status().requests.requests == 0);
    });
    test("stale thermal updates cancel unexpired frequency requests", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        check(engine.acquire(1046, 42, 0, 1000, {kCpu0Min, 1000000}, 2500) > 0);
        engine.tick(3001);
        check(engine.status().requests.requests == 0 && f.backend.effective().at(kCpu0Min) == -1);
        engine.thermal(true, 4000);
        check(engine.status().requests.requests == 0);
    });
    test("process death and PID reuse release the original generation", [&](auto& f) {
        uint64_t current = 5;
        PowerEngine engine(f.backend, [&](int) { return std::optional<uint64_t>{current}; });
        check(engine.initialize(0)); engine.thermal(true, 0); engine.interactive(true, 0);
        int old = engine.acquire(1046, 42, 0, 1000, {kCpu0Min, 1000000}, 0);
        check(old > 0); current = 6; engine.tick(10);
        check(engine.status().requests.requests == 0 && f.backend.effective().at(kCpu0Min) == -1);
        check(engine.release(1046, 42, old, 20) < 0);
    });
    test("vendor release requires the authenticated process not a shared UID", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        int handle = engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 40}, 0);
        check(handle > 0 && engine.release(1046, 43, handle, 10) == -EPERM);
        check(engine.releaseAsync(1046, handle, 10) == -EOPNOTSUPP);
        check(engine.status().requests.requests == 1 && engine.release(1046, 42, handle, 10) == 0);
    });
    test("application UIDs invalid processes and duplicate pairs cannot acquire", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        check(engine.acquire(10001, 42, 0, 100, {kTopAppUclamp, 40}, 0) == -EPERM);
        check(engine.acquire(1046, 0, 0, 100, {kTopAppUclamp, 40}, 0) == -EPERM);
        check(engine.acquire(1046, 44, 0, 100, {kTopAppUclamp, 40}, 0) == -EPERM);
        check(engine.acquire(1046, 42, 0, 100, {kCpu0Min, -1, kCpu0Min, 1000000}, 0) == -EINVAL);
    });
    test("private unsupported resources do not partially acquire valid resources", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        check(engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 40, 123, 3}, 0) == -EOPNOTSUPP);
        check(engine.status().requests.requests == 0);
        int handle = engine.acquire(1046, 42, 0, 100, {0x00800000, -1, kCpu0Min, 3000000}, 0);
        check(handle > 0 && f.backend.effective().at(kCpu0Min) == 2000000);
        check(engine.acquire(1046, 42, handle, 100, {kCpu0Min, -1}, 10) == 0);
        check(f.backend.effective().at(kCpu0Min) == -1);
    });
    test("invalid framework update keeps the original handle releasable", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0); engine.launch(true, 40, 0);
        engine.launch(true, 120, 10); engine.launch(false, 40, 20);
        check(engine.status().requests.requests == 0 && f.backend.effective().at(kTopAppUclamp) == 0);
    });
    test("process generation parses parenthesized names and rejects zombies", [&](auto& f) {
        std::string tail;
        for (int i = 4; i < 22; ++i) tail += " 0";
        f.io.files["/proc/42/stat"] = "42 (a name with ) brackets) R" + tail + " 9876 0\n";
        check(processGeneration(f.io, 42) == 9876);
        f.io.files["/proc/42/stat"] = "42 (dead) Z" + tail + " 9876\n";
        check(!processGeneration(f.io, 42));
        f.io.files["/proc/42/stat"] = "42 (short) R 0\n";
        check(!processGeneration(f.io, 42));
    });
    test("a short request wakes an idle expiry worker", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        auto waiting = std::async(std::launch::async, [&] { engine.waitForWork(0); });
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        check(engine.acquire(1046, 42, 0, 50, {kTopAppUclamp, 10}, 0) > 0);
        check(waiting.wait_for(std::chrono::milliseconds(250)) == std::future_status::ready);
        engine.tick(50); check(engine.status().requests.requests == 0);
    });
    test("diagnostics distinguish authenticated requests and failed release attempts", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        int handle = engine.acquire(1046, 42, 0, 100, {kTopAppUclamp, 10}, 0);
        check(handle > 0);
        check(engine.release(1046, 43, handle, 10) == -EPERM);
        check(engine.release(1046, 42, handle, 20) == 0);
        const auto events = engine.status().events;
        check(events.size() == 3 && events[0].uid == 1046 && events[0].pid == 42);
        check(events[0].result == handle && events[0].pairs == std::vector<int32_t>({kTopAppUclamp, 10}));
        check(events[1].pid == 43 && events[1].result == -EPERM && events[1].handle == handle);
        check(events[2].when == 20 && events[2].result == 0 && std::string(events[2].operation) == "release");
    });
    test("untrusted diagnostic requests cannot grow the event buffer or payload", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        std::vector<int32_t> oversized(10000, 42);
        for (int i = 0; i < 100; ++i) check(engine.acquire(1046, 42, 0, 100, oversized, i) == -EINVAL);
        const auto events = engine.status().events;
        check(events.size() == 64 && events.front().when == 36 && events.back().when == 99);
        check(events.back().words == oversized.size() && events.back().pairs.size() == 64);
        check(engine.status().requests.requests == 0);
    });
    std::cout << passed << " passed; " << failed << " failed\n";
    return failed != 0;
}
