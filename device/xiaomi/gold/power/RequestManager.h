// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <cstdint>
#include <map>
#include <mutex>
#include <vector>

namespace gold::power {

using Values = std::map<int32_t, int32_t>;
using Millis = int64_t;
enum class Inhibit : uint32_t { DisplayOff = 1, LowPower = 2, Thermal = 4, Manual = 8 };

struct Resource {
    int32_t id;
    int32_t minimum;
    int32_t maximum;
    int32_t reset;
    bool preferHigher;
    // Only reviewed non-frequency mode/session resources may use duration == 0.
    // Vendor sessions authenticate and monitor their owner; framework modes
    // use one global controller and release on disable or a policy gate.
    bool allowUntimed = false;
};

// Identifies an authenticated process instance, not a caller-supplied TID.
struct Owner {
    int32_t uid;
    int32_t pid;
    uint64_t generation;
    bool operator==(const Owner& other) const;
};

class Backend {
  public:
    virtual ~Backend() = default;
    // On failure the manager retries its last authoritative desired state.
    // A hardware adapter must implement rollback for a partial multi-node write.
    virtual bool apply(const Values& values) = 0;
};

struct Snapshot {
    size_t requests;
    bool enabled;
    bool dirty;
    Values desired;
    Values applied;
    Millis nextExpiry;
};

// One instance owns all framework and vendor votes for a set of resources.
// The service must call expire() at nextExpiry, on owner death, and periodically
// while dirty. No per-request detached threads or unkeyed global "release".
class RequestManager {
  public:
    RequestManager(std::vector<Resource> resources, Backend& backend, Millis maximumDuration);
    int32_t acquire(Owner owner, int32_t handle, Millis duration, const Values& values, Millis now);
    int release(Owner owner, int32_t handle, Millis now);
    bool releaseOwner(Owner owner, Millis now);
    bool expire(Millis now);
    bool setEnabled(bool enabled, Millis now);
    bool setInhibit(Inhibit reason, bool blocked, Millis now);
    Snapshot snapshot() const;

  private:
    struct Request {
        Owner owner;
        Millis expiry;
        Values values;
    };
    using Requests = std::map<int32_t, Request>;
    Values aggregate(const Requests& requests) const;
    bool reconcile();
    void removeExpired(Millis now);
    mutable std::mutex mutex_;
    const std::vector<Resource> resources_;
    Backend& backend_;
    const Millis maximumDuration_;
    Requests requests_;
    Values applied_;
    int64_t nextHandle_ = 1;
    bool enabled_ = true;
    uint32_t inhibited_ = 0;
    bool dirty_ = true;
};

}  // namespace gold::power
