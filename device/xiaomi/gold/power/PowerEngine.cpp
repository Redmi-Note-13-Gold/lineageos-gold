// SPDX-License-Identifier: Apache-2.0
#include "PowerEngine.h"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <limits>
#include <set>
#include <sstream>

namespace gold::power {
namespace {
constexpr Millis kMaximumDuration = 2000;
constexpr Millis kThermalFreshness = 3000;
// Framework oneway calls have no calling PID. They share one authenticated
// framework controller; vendor callers always use their real process instance.
const Owner kFramework{1000, std::numeric_limits<int32_t>::max(), 1};
}

std::optional<uint64_t> processGeneration(NodeIo& io, int pid) {
    if (pid <= 0) return std::nullopt;
    std::string text;
    if (!io.read("/proc/" + std::to_string(pid) + "/stat", &text)) return std::nullopt;
    // comm may contain spaces and parentheses; fields after its final ')' are
    // unambiguous. starttime is field 22 (20th token starting at state).
    auto end = text.rfind(')');
    if (end == std::string::npos) return std::nullopt;
    std::istringstream stream(text.substr(end + 1));
    std::string token;
    for (int field = 3; field < 22; ++field) {
        if (!(stream >> token) || (field == 3 && (token == "Z" || token == "X"))) return std::nullopt;
    }
    uint64_t generation = 0;
    if (!(stream >> token) || token.empty() || token.find_first_not_of("0123456789") != std::string::npos) return std::nullopt;
    for (char ch : token) {
        unsigned digit = ch - '0';
        if (generation > (std::numeric_limits<uint64_t>::max() - digit) / 10) return std::nullopt;
        generation = generation * 10 + digit;
    }
    return generation ? std::optional<uint64_t>{generation} : std::nullopt;
}

PowerEngine::PowerEngine(NodeBackend& backend, Generation generation)
    : backend_(backend), generation_(std::move(generation)) {}

bool PowerEngine::initialize(Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    return initializeLocked(now);
}

bool PowerEngine::initializeLocked(Millis now) {
    if (manager_) return true;
    lastInitialize_ = now;
    if (stopped_ || !backend_.discover()) return false;
    manager_ = std::make_unique<RequestManager>(backend_.resources(), backend_, kMaximumDuration);
    bool reset = manager_->setInhibit(Inhibit::Thermal,
            !thermalSafe_ || lastThermal_ < 0 || now - lastThermal_ > kThermalFreshness, now);
    reset = manager_->setInhibit(Inhibit::DisplayOff,
            !interactive_ || displayInactive_ || deviceIdle_, now) && reset;
    reset = manager_->setInhibit(Inhibit::LowPower, lowPower_, now) && reset;
    if (!reset) manager_.reset();
    return reset;
}

bool PowerEngine::identity(int uid, int pid, Owner* owner) const {
    // The compatibility entry points serve native vendor services. App UIDs
    // must use framework APIs, which also provide screen and power policy.
    if (uid < 0 || uid >= 10000 || pid <= 0) return false;
    auto generation = generation_(pid);
    if (!generation) return false;
    *owner = {uid, pid, *generation};
    return true;
}

int PowerEngine::record(const char* operation, int uid, int pid, int handle, Millis duration,
                        int result, Millis now, const std::vector<int32_t>& pairs) {
    // Caller/resource evidence stays bounded and in memory. No package names,
    // activities, media contents or persistent log stream are collected.
    if (events_.size() == 64) events_.pop_front();
    const auto end = pairs.begin() + std::min<size_t>(pairs.size(), 64);
    events_.push_back({now, operation, uid, pid, handle, duration, result, pairs.size(),
                       std::vector<int32_t>(pairs.begin(), end)});
    return result;
}

void PowerEngine::gate(Inhibit reason, bool blocked, Millis now) {
    changed_.notify_all();
    if (!manager_) return;
    manager_->setInhibit(reason, blocked, now);
    // A gate cancels modes too; a later enable call must explicitly vote again.
    if (blocked) { leases_.clear(); launch_ = interaction_ = 0; audio_.fill(0); }
}

void PowerEngine::tickLocked(Millis now) {
    if (!manager_) {
        if (stopped_ || (lastInitialize_ >= 0 && now - lastInitialize_ < 1000)) return;
        if (!initializeLocked(now)) return;
    }
    if (lastThermal_ < 0 || now - lastThermal_ > kThermalFreshness) gate(Inhibit::Thermal, true, now);
    for (auto it = leases_.begin(); it != leases_.end();) {
        auto generation = generation_(it->second.owner.pid);
        if (!generation || *generation != it->second.owner.generation) {
            manager_->releaseOwner(it->second.owner, now);
            it = leases_.erase(it);
        } else if (it->second.expiry <= now) {
            it = leases_.erase(it);
        } else ++it;
    }
    manager_->expire(now);
}

int PowerEngine::acquire(int uid, int pid, int handle, Millis duration,
                         const std::vector<int32_t>& pairs, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    changed_.notify_all();
    tickLocked(now);
    const auto finish = [&](int result) { return record("acquire", uid, pid, handle, duration, result, now, pairs); };
    const auto reject = [&](int error) { ++rejected_; return finish(error); };
    if (!manager_) return reject(-ENODEV);
    Owner owner;
    if (!identity(uid, pid, &owner)) return reject(-EPERM);
    if (pairs.empty() || pairs.size() > 64 || pairs.size() % 2 || duration < 0 || duration > kMaximumDuration) return reject(-EINVAL);
    Values values;
    std::set<int> seen;
    const auto resources = backend_.resources();
    for (size_t i = 0; i < pairs.size(); i += 2) {
        int id = pairs[i], value = pairs[i + 1];
        if (!seen.insert(id).second) return reject(-EINVAL);
        auto resource = std::find_if(resources.begin(), resources.end(), [id](const auto& item) { return item.id == id; });
        if (resource == resources.end()) {
            // Unset core constraints do not request an action. Actual core_ctl
            // requests are unsupported until independent thermal-safe voting
            // and a caller benefit have been established on this kernel.
            if ((id == 0x00800000 || id == 0x00800100 || id == 0x00804000 || id == 0x00804100) && value == -1) continue;
            return reject(-EOPNOTSUPP);
        }
        bool frequency = id == kCpu0Min || id == kCpu1Min || id == kCpu0Max || id == kCpu1Max;
        if (frequency && value == -1) continue;
        if (frequency) value = std::min(value, resource->maximum);
        if (value < resource->minimum || value > resource->maximum) return reject(-EINVAL);
        values.emplace(id, value);
    }
    if (values.empty()) {
        if (handle > 0) {
            int result = manager_->release(owner, handle, now);
            if (result == 0 || result == -EIO) leases_.erase(handle);
            return finish(result);
        }
        return reject(-ENODATA);
    }
    int result = manager_->acquire(owner, handle, duration, values, now);
    if (result > 0) {
        leases_[result] = {owner, duration == 0 ? std::numeric_limits<Millis>::max() : now + duration};
        ++accepted_;
    } else ++rejected_;
    return finish(result);
}

int PowerEngine::release(int uid, int pid, int handle, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    changed_.notify_all();
    tickLocked(now);
    const auto finish = [&](int result) { return record("release", uid, pid, handle, 0, result, now); };
    Owner owner;
    if (!manager_) return finish(-ENODEV);
    if (!identity(uid, pid, &owner)) return finish(-EPERM);
    int result = manager_->release(owner, handle, now);
    if (result == 0 || result == -EIO) leases_.erase(handle);
    return finish(result);
}

int PowerEngine::releaseAsync(int uid, int handle, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    changed_.notify_all();
    tickLocked(now);
    const auto finish = [&](int result) { return record("release-oneway", uid, 0, handle, 0, result, now); };
    if (!manager_) return finish(-ENODEV);
    auto lease = leases_.find(handle);
    if (lease == leases_.end()) return finish(-ENOENT);
    if (lease->second.owner.uid != uid) return finish(-EPERM);
    // HIDL oneway carries UID but no PID; even a single known lease does not
    // authenticate the process sending this release. The current C ABI adapter
    // uses the existing 1.2 synchronous release. Do not guess from reserved/TID
    // or release a forked process's inherited handle on UID alone.
    return finish(-EOPNOTSUPP);
}

void PowerEngine::displayGate(Millis now) {
    gate(Inhibit::DisplayOff, !interactive_ || displayInactive_ || deviceIdle_, now);
}
void PowerEngine::interactive(bool enabled, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_); interactive_ = enabled; displayGate(now);
}
void PowerEngine::displayInactive(bool enabled, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_); displayInactive_ = enabled; displayGate(now);
}
void PowerEngine::deviceIdle(bool enabled, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_); deviceIdle_ = enabled; displayGate(now);
}
void PowerEngine::lowPower(bool enabled, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_); lowPower_ = enabled; gate(Inhibit::LowPower, enabled, now);
}
void PowerEngine::thermal(bool safe, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_); lastThermal_ = now; thermalSafe_ = safe; gate(Inhibit::Thermal, !safe, now);
}

void PowerEngine::framework(int* handle, bool enabled, int duration, const Values& values, Millis now) {
    changed_.notify_all();
    tickLocked(now);
    if (!manager_) return;
    if (!enabled) {
        if (*handle > 0) manager_->release(kFramework, *handle, now);
        *handle = 0;
        return;
    }
    int result = manager_->acquire(kFramework, *handle, duration, values, now);
    if (result == -ENOENT) result = manager_->acquire(kFramework, 0, duration, values, now);
    if (result > 0) *handle = result;
    if (result > 0) ++accepted_; else ++rejected_;
}
void PowerEngine::launch(bool enabled, int clamp, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    framework(&launch_, enabled && clamp > 0, 500, {{kTopAppUclamp, clamp}}, now);
}
void PowerEngine::interaction(int duration, int clamp, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    framework(&interaction_, duration >= 0 && clamp > 0,
              duration == 0 ? 120 : std::min<int>(duration, kMaximumDuration),
              {{kTopAppUclamp, clamp}}, now);
}
void PowerEngine::audioStreaming(unsigned source, bool enabled, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (source >= audio_.size()) return;
    framework(&audio_[source], enabled, 0, {{kTopAppPreferIdle, 1}}, now);
}
void PowerEngine::tick(Millis now) { std::lock_guard<std::mutex> lock(mutex_); tickLocked(now); }
void PowerEngine::waitForWork(Millis now) {
    std::unique_lock<std::mutex> lock(mutex_);
    auto status = manager_ ? manager_->snapshot() : Snapshot{};
    Millis delay = status.requests ? 250 : 1000;
    if (status.requests) delay = std::min(delay, std::max<Millis>(1, status.nextExpiry - now));
    // Compute the deadline while holding the same mutex as every request.
    // Releasing it atomically in wait_for prevents a short incoming boost from
    // missing a wakeup during the otherwise one-second idle wait.
    changed_.wait_for(lock, std::chrono::milliseconds(delay));
}
void PowerEngine::stop(Millis now) {
    std::lock_guard<std::mutex> lock(mutex_); stopped_ = true; gate(Inhibit::Manual, true, now);
}
EngineStatus PowerEngine::status() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return {manager_ != nullptr, manager_ ? manager_->snapshot() : Snapshot{}, backend_.effective(),
            accepted_, rejected_, backend_.error(), events_};
}

}  // namespace gold::power
