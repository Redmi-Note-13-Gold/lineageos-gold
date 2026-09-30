// SPDX-License-Identifier: Apache-2.0
#pragma once

#include "NodeBackend.h"

#include <array>
#include <functional>
#include <condition_variable>
#include <deque>
#include <memory>
#include <optional>

namespace gold::power {

struct RequestEvent {
    Millis when;
    const char* operation;
    int uid, pid, handle;
    Millis duration;
    int result;
    size_t words;
    std::vector<int32_t> pairs;
};

struct EngineStatus {
    bool ready;
    Snapshot requests;
    Values effective;
    uint64_t accepted;
    uint64_t rejected;
    std::string backendError;
    std::deque<RequestEvent> events;
};

// Binder adapters pass credentials supplied by the transport, never reserved,
// UID, PID or TID fields in a vendor request. tick() is driven by one worker.
class PowerEngine {
  public:
    using Generation = std::function<std::optional<uint64_t>(int32_t)>;
    PowerEngine(NodeBackend& backend, Generation generation);
    bool initialize(Millis now);
    int acquire(int uid, int pid, int handle, Millis duration, const std::vector<int32_t>& pairs, Millis now);
    int release(int uid, int pid, int handle, Millis now);
    int releaseAsync(int uid, int handle, Millis now);
    void interactive(bool enabled, Millis now);
    void displayInactive(bool enabled, Millis now);
    void deviceIdle(bool enabled, Millis now);
    void lowPower(bool enabled, Millis now);
    void thermal(bool safe, Millis now);
    void launch(bool enabled, int clamp, Millis now);
    void interaction(int duration, int clamp, Millis now);
    // Source 0 is AIDL; 1..5 are the five reviewed MTK audio hints.
    void audioStreaming(unsigned source, bool enabled, Millis now);
    void tick(Millis now);
    void waitForWork(Millis now);
    void stop(Millis now);
    EngineStatus status() const;

  private:
    struct Lease { Owner owner; Millis expiry; };
    bool initializeLocked(Millis now);
    bool identity(int uid, int pid, Owner* owner) const;
    void displayGate(Millis now);
    void gate(Inhibit reason, bool blocked, Millis now);
    void tickLocked(Millis now);
    void framework(int* handle, bool enabled, int duration, const Values& values, Millis now);
    int record(const char* operation, int uid, int pid, int handle, Millis duration,
               int result, Millis now, const std::vector<int32_t>& pairs = {});
    mutable std::mutex mutex_;
    std::condition_variable changed_;
    NodeBackend& backend_;
    Generation generation_;
    std::unique_ptr<RequestManager> manager_;
    std::map<int, Lease> leases_;
    bool interactive_ = false;
    bool displayInactive_ = false;
    bool deviceIdle_ = false;
    bool lowPower_ = false;
    bool thermalSafe_ = false;
    bool stopped_ = false;
    Millis lastInitialize_ = -1;
    Millis lastThermal_ = -1;
    int launch_ = 0, interaction_ = 0;
    std::array<int, 6> audio_{};
    uint64_t accepted_ = 0, rejected_ = 0;
    std::deque<RequestEvent> events_;
};

std::optional<uint64_t> processGeneration(NodeIo& io, int pid);

}  // namespace gold::power
