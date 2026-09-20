// SPDX-License-Identifier: Apache-2.0
#include "NodeBackend.h"
#include "PowerEngine.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <csignal>
#include <functional>
#include <future>
#include <iostream>
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
            files[path] = "[1] WIFI: 0\t(1)(-1)(-1)(-1)\n[2] PERFSERV: 0\t(" +
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
            {NodeBackend::kUclamp, 0}, {NodeBackend::kPreferIdle, 0}, {NodeBackend::kIdleTime, 50}}) {
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
    for (const Values& values : {Values{{kTopAppUclamp, 10}}, Values{{kCpu0Min, floor}},
                                Values{{kDisplayIdleTime, 100}}}) {
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

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--hardware") return hardwareProbe();
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
        f.io.failPath = NodeBackend::kIdleTime; f.io.failures = 1;
        auto desired = f.reset;
        desired[kCpu0Min] = 1000000; desired[kTopAppUclamp] = 40; desired[kDisplayIdleTime] = 100;
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
        check(!f.backend.apply(f.reset));
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
    test("stale thermal updates cancel held display and frequency requests", [&](auto& f) {
        PowerEngine engine(f.backend, generation); check(engine.initialize(0));
        engine.thermal(true, 0); engine.interactive(true, 0);
        check(engine.acquire(1046, 42, 0, 0, {kDisplayIdleTime, 100}, 0) > 0);
        engine.tick(3001);
        check(engine.status().requests.requests == 0 && f.backend.effective().at(kDisplayIdleTime) == 50);
        engine.thermal(true, 4000);
        check(engine.status().requests.requests == 0);
    });
    test("process death and PID reuse release the original generation", [&](auto& f) {
        uint64_t current = 5;
        PowerEngine engine(f.backend, [&](int) { return std::optional<uint64_t>{current}; });
        check(engine.initialize(0)); engine.thermal(true, 0); engine.interactive(true, 0);
        int old = engine.acquire(1046, 42, 0, 0, {kDisplayIdleTime, 100}, 0);
        check(old > 0); current = 6; engine.tick(10);
        check(engine.status().requests.requests == 0 && f.backend.effective().at(kDisplayIdleTime) == 50);
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
    std::cout << passed << " passed; " << failed << " failed\n";
    return failed != 0;
}
