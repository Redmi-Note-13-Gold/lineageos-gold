// SPDX-License-Identifier: Apache-2.0
#include "NodeBackend.h"

#include <algorithm>
#include <functional>
#include <iostream>
#include <sstream>
#include <stdexcept>

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

int main() {
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
    std::cout << passed << " passed; " << failed << " failed\n";
    return failed != 0;
}
