// SPDX-License-Identifier: Apache-2.0
#include "RequestManager.h"

#include <atomic>
#include <cerrno>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <thread>

using namespace gold::power;

struct FakeBackend : Backend {
    Values hardware;
    unsigned writes = 0;
    unsigned failures = 0;
    bool apply(const Values& values) override {
        ++writes;
        // Exercise recovery even if a real multi-node write fails halfway.
        hardware[values.begin()->first] = values.begin()->second;
        if (failures > 0) { --failures; return false; }
        hardware = values;
        return true;
    }
};

void check(bool condition) {
    if (!condition) throw std::runtime_error("expectation failed");
}

struct Fixture {
    FakeBackend backend;
    RequestManager manager{{{1, 0, 100, 0, true}, {2, 0, 100, 100, false}}, backend, 2000};
    Owner a{1000, 10, 1};
    Owner b{1046, 20, 2};
};

int main() {
    int passed = 0;
    int failed = 0;
    const auto test = [&](const char* name, const std::function<void(Fixture&)>& body) {
        Fixture fixture;
        try {
            body(fixture);
            ++passed;
            std::cout << "PASS " << name << '\n';
        } catch (const std::exception& error) {
            ++failed;
            std::cerr << "FAIL " << name << ": " << error.what() << '\n';
        }
    };
    test("overlap releases only the owner vote", [](auto& f) {
        int a = f.manager.acquire(f.a, 0, 100, {{1, 40}}, 0);
        int b = f.manager.acquire(f.b, 0, 200, {{1, 80}}, 0);
        check(a > 0 && b > a && f.backend.hardware.at(1) == 80);
        check(f.manager.release(f.a, a, 10) == 0 && f.backend.hardware.at(1) == 80);
        check(f.manager.release(f.b, b, 20) == 0 && f.backend.hardware.at(1) == 0);
    });
    test("update replaces resources and duration atomically", [](auto& f) {
        int a = f.manager.acquire(f.a, 0, 100, {{1, 80}}, 0);
        check(f.manager.acquire(f.a, a, 300, {{2, 60}}, 90) == a);
        check(f.backend.hardware.at(1) == 0 && f.backend.hardware.at(2) == 60);
        check(f.manager.expire(100) && f.manager.snapshot().requests == 1);
        check(f.manager.expire(390) && f.backend.hardware.at(2) == 100);
    });
    test("early expiration cannot release a longer concurrent request", [](auto& f) {
        check(f.manager.acquire(f.a, 0, 100, {{1, 90}}, 0) > 0);
        check(f.manager.acquire(f.b, 0, 300, {{1, 50}}, 0) > 0);
        check(f.manager.expire(100) && f.backend.hardware.at(1) == 50);
        check(f.manager.expire(300) && f.backend.hardware.at(1) == 0);
    });
    test("lower wins for maximum constraints", [](auto& f) {
        int a = f.manager.acquire(f.a, 0, 100, {{2, 60}}, 0);
        check(f.manager.acquire(f.b, 0, 300, {{2, 80}}, 0) > 0);
        check(f.backend.hardware.at(2) == 60);
        check(f.manager.release(f.a, a, 20) == 0 && f.backend.hardware.at(2) == 80);
    });
    test("cross process release and update rejected", [](auto& f) {
        int a = f.manager.acquire(f.a, 0, 100, {{1, 50}}, 0);
        check(f.manager.release(f.b, a, 1) == -EPERM);
        check(f.manager.acquire(f.b, a, 100, {{1, 90}}, 1) == -EPERM);
        check(f.backend.hardware.at(1) == 50);
    });
    test("PID reuse cannot acquire old process locks", [](auto& f) {
        int a = f.manager.acquire(f.a, 0, 100, {{1, 50}}, 0);
        auto reused = f.a;
        ++reused.generation;
        check(f.manager.release(reused, a, 1) == -EPERM);
    });
    test("owner death clears only that process", [](auto& f) {
        check(f.manager.acquire(f.a, 0, 100, {{1, 90}}, 0) > 0);
        check(f.manager.acquire(f.b, 0, 100, {{1, 30}}, 0) > 0);
        check(f.manager.releaseOwner(f.a, 10) && f.backend.hardware.at(1) == 30);
    });
    test("unknown resource rejects entire request", [](auto& f) {
        check(f.manager.acquire(f.a, 0, 100, {{1, 90}, {99, 1}}, 0) == -EOPNOTSUPP);
        check(f.manager.snapshot().requests == 0 && f.backend.hardware.at(1) == 0);
    });
    test("out of range value does not affect existing request", [](auto& f) {
        int a = f.manager.acquire(f.a, 0, 100, {{1, 50}}, 0);
        check(f.manager.acquire(f.a, a, 100, {{1, 101}}, 1) == -EINVAL);
        check(f.backend.hardware.at(1) == 50 && f.manager.snapshot().nextExpiry == 100);
    });
    test("empty and indefinite requests do not claim success", [](auto& f) {
        check(f.manager.acquire(f.a, 0, 100, {}, 0) == -EINVAL);
        check(f.manager.acquire(f.a, 0, 0, {{1, 50}}, 0) == -EINVAL);
        check(f.manager.acquire(f.a, 0, -1, {{1, 50}}, 0) == -EINVAL);
        check(f.manager.acquire(f.a, 0, 2001, {{1, 50}}, 0) == -EINVAL);
    });
    test("expiry overflow rejected", [](auto& f) {
        check(f.manager.acquire(f.a, 0, 100, {{1, 50}}, std::numeric_limits<Millis>::max() - 10) == -EINVAL);
    });
    test("untimed session resources require authenticated process identity", [](auto& f) {
        FakeBackend backend;
        RequestManager manager{{{3, 0, 100, 0, true, true}}, backend, 2000};
        Owner missingGeneration{1000, 10, 0};
        check(manager.acquire(missingGeneration, 0, 0, {{3, 40}}, 0) == -EINVAL);
        int handle = manager.acquire(f.a, 0, 0, {{3, 40}}, 0);
        check(handle > 0 && manager.expire(100000) && backend.hardware.at(3) == 40);
        check(manager.releaseOwner(f.a, 100001) && backend.hardware.at(3) == 0);
    });
    test("mixed untimed request cannot keep frequency resources pinned", [](auto& f) {
        FakeBackend backend;
        RequestManager manager{{{1, 0, 100, 0, true}, {3, 0, 100, 0, true, true}}, backend, 2000};
        check(manager.acquire(f.a, 0, 0, {{1, 50}, {3, 40}}, 0) == -EINVAL);
        check(manager.snapshot().requests == 0 && backend.hardware.at(1) == 0);
    });
    test("held session can atomically become a timed request", [](auto& f) {
        FakeBackend backend;
        RequestManager manager{{{3, 0, 100, 0, true, true}}, backend, 2000};
        int handle = manager.acquire(f.a, 0, 0, {{3, 40}}, 0);
        check(manager.acquire(f.a, handle, 100, {{3, 20}}, 10) == handle);
        check(manager.snapshot().nextExpiry == 110 && backend.hardware.at(3) == 20);
        check(manager.expire(110) && backend.hardware.at(3) == 0);
    });
    test("thermal inhibit cancels held sessions without resurrection", [](auto& f) {
        FakeBackend backend;
        RequestManager manager{{{3, 0, 100, 0, true, true}}, backend, 2000};
        check(manager.acquire(f.a, 0, 0, {{3, 40}}, 0) > 0);
        check(manager.setInhibit(Inhibit::Thermal, true, 1) && backend.hardware.at(3) == 0);
        check(manager.setInhibit(Inhibit::Thermal, false, 2) && manager.snapshot().requests == 0);
    });
    test("expired handles cannot resurrect an old vote", [](auto& f) {
        int a = f.manager.acquire(f.a, 0, 100, {{1, 50}}, 0);
        check(f.manager.acquire(f.a, a, 100, {{1, 90}}, 100) == -ENOENT);
        int b = f.manager.acquire(f.a, 0, 100, {{1, 20}}, 100);
        check(b > a);
        check(f.manager.release(f.a, a, 101) == -ENOENT && f.backend.hardware.at(1) == 20);
    });
    test("failed acquisition never returns a handle", [](auto& f) {
        check(f.manager.expire(0));
        f.backend.failures = 1;
        check(f.manager.acquire(f.a, 0, 100, {{1, 90}}, 0) == -EIO);
        check(f.manager.snapshot().requests == 0 && f.backend.hardware.at(1) == 0);
    });
    test("failed update keeps earlier lease and expiry", [](auto& f) {
        int a = f.manager.acquire(f.a, 0, 100, {{1, 50}}, 0);
        f.backend.failures = 1;
        check(f.manager.acquire(f.a, a, 200, {{1, 90}}, 10) == -EIO);
        check(f.backend.hardware.at(1) == 50 && f.manager.snapshot().nextExpiry == 100);
    });
    test("failed expiry restoration is retried with no live leases", [](auto& f) {
        check(f.manager.acquire(f.a, 0, 100, {{1, 90}, {2, 20}}, 0) > 0);
        f.backend.failures = 1;
        check(!f.manager.expire(100) && f.manager.snapshot().dirty);
        check(f.manager.snapshot().requests == 0);
        check(f.manager.expire(110) && !f.manager.snapshot().dirty && f.backend.hardware.at(2) == 100);
    });
    test("failed rollback remains visible and retries", [](auto& f) {
        check(f.manager.expire(0));
        f.backend.failures = 2;
        check(f.manager.acquire(f.a, 0, 100, {{1, 90}}, 0) == -EIO);
        check(f.manager.snapshot().dirty);
        check(f.manager.expire(1) && !f.manager.snapshot().dirty);
    });
    test("display off cancels pending boosts and blocks new requests", [](auto& f) {
        check(f.manager.acquire(f.a, 0, 100, {{1, 90}}, 0) > 0);
        check(f.manager.setInhibit(Inhibit::DisplayOff, true, 10));
        check(f.backend.hardware.at(1) == 0 && f.manager.snapshot().requests == 0);
        check(f.manager.acquire(f.a, 0, 100, {{1, 90}}, 11) == -EAGAIN);
        check(f.manager.setInhibit(Inhibit::DisplayOff, false, 12));
        check(f.manager.snapshot().requests == 0);
    });
    test("independent thermal and battery saver gates cannot override each other", [](auto& f) {
        check(f.manager.setInhibit(Inhibit::Thermal, true, 0));
        check(f.manager.setInhibit(Inhibit::LowPower, true, 0));
        check(f.manager.setInhibit(Inhibit::Thermal, false, 0));
        check(f.manager.acquire(f.a, 0, 100, {{1, 90}}, 1) == -EAGAIN);
        check(f.manager.setInhibit(Inhibit::LowPower, false, 2));
        check(f.manager.acquire(f.a, 0, 100, {{1, 40}}, 2) > 0);
    });
    test("unchanged aggregate avoids duplicate writes", [](auto& f) {
        int a = f.manager.acquire(f.a, 0, 100, {{1, 90}}, 0);
        unsigned writes = f.backend.writes;
        int b = f.manager.acquire(f.b, 0, 100, {{1, 50}}, 0);
        check(a > 0 && b > 0 && f.backend.writes == writes);
        check(f.manager.release(f.b, b, 10) == 0 && f.backend.writes == writes);
    });
    test("per owner allocation is bounded without discarding existing votes", [](auto& f) {
        for (int i = 0; i < 16; ++i) check(f.manager.acquire(f.a, 0, 100, {{1, i}}, 0) > 0);
        check(f.manager.acquire(f.a, 0, 100, {{1, 99}}, 0) == -ENOSPC);
        check(f.backend.hardware.at(1) == 15 && f.manager.snapshot().requests == 16);
    });
    test("parallel framework and vendor requests are serialized", [](auto& f) {
        std::atomic<int> errors{0};
        std::vector<std::thread> threads;
        for (int i = 1; i <= 32; ++i) {
            threads.emplace_back([&, i] {
                Owner owner{1000, i, static_cast<uint64_t>(i)};
                int handle = f.manager.acquire(owner, 0, 100, {{1, i}}, 0);
                if (handle <= 0 || f.manager.release(owner, handle, 1) != 0) ++errors;
            });
        }
        for (auto& thread : threads) thread.join();
        check(errors == 0 && f.manager.snapshot().requests == 0 && f.backend.hardware.at(1) == 0);
    });
    test("duplicate resource specifications rejected", [](auto&) {
        FakeBackend backend;
        bool rejected = false;
        try { RequestManager bad{{{1, 0, 100, 0, true}, {1, 0, 100, 0, true}}, backend, 100}; }
        catch (const std::invalid_argument&) { rejected = true; }
        check(rejected);
    });
    std::cout << passed << " passed, " << failed << " failed\n";
    return failed == 0 ? 0 : 1;
}
