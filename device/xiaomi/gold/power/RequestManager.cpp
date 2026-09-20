// SPDX-License-Identifier: Apache-2.0
#include "RequestManager.h"

#include <algorithm>
#include <cerrno>
#include <limits>
#include <stdexcept>

namespace gold::power {

bool Owner::operator==(const Owner& other) const {
    return uid == other.uid && pid == other.pid && generation == other.generation;
}

RequestManager::RequestManager(std::vector<Resource> resources, Backend& backend, Millis maximumDuration)
    : resources_(std::move(resources)), backend_(backend), maximumDuration_(maximumDuration) {
    if (resources_.empty() || maximumDuration <= 0) {
        throw std::invalid_argument("Empty resources or invalid duration bound");
    }
    Values ids;
    for (const auto& resource : resources_) {
        if (resource.minimum > resource.maximum || resource.reset < resource.minimum ||
            resource.reset > resource.maximum || !ids.emplace(resource.id, 0).second) {
            throw std::invalid_argument("Invalid or duplicate resource definition");
        }
    }
}

Values RequestManager::aggregate(const Requests& requests) const {
    Values values;
    for (const auto& resource : resources_) {
        // Reset is the neutral value for this resource, never an active vote.
        bool voted = false;
        int32_t value = resource.reset;
        for (const auto& [handle, request] : requests) {
            const auto item = request.values.find(resource.id);
            if (item == request.values.end()) continue;
            if (!voted) value = item->second;
            else value = resource.preferHigher ? std::max(value, item->second) : std::min(value, item->second);
            voted = true;
        }
        values.emplace(resource.id, value);
    }
    return values;
}

bool RequestManager::reconcile() {
    const Values desired = aggregate(requests_);
    if (!dirty_ && desired == applied_) return true;
    dirty_ = true;
    if (!backend_.apply(desired)) return false;
    applied_ = desired;
    dirty_ = false;
    return true;
}

void RequestManager::removeExpired(Millis now) {
    for (auto it = requests_.begin(); it != requests_.end();) {
        if (it->second.expiry <= now) it = requests_.erase(it);
        else ++it;
    }
}

int32_t RequestManager::acquire(Owner owner, int32_t handle, Millis duration, const Values& values, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    removeExpired(now);
    if (!reconcile()) return -EIO;
    if (!enabled_) return -EAGAIN;
    // Some vendor display/media requests use zero until explicit release. Only
    // resources reviewed for this lifetime can opt in; frequency boosts cannot
    // silently become permanent locks or be acknowledged without an action.
    if (owner.uid < 0 || owner.pid <= 0 || owner.generation == 0 || handle < 0 || duration < 0 ||
        duration > maximumDuration_ || now < 0 || now > std::numeric_limits<Millis>::max() - duration ||
        values.empty()) return -EINVAL;
    for (const auto& [id, value] : values) {
        const int32_t wanted = id;
        const auto resource = std::find_if(resources_.begin(), resources_.end(),
                                          [wanted](const auto& item) { return item.id == wanted; });
        if (resource == resources_.end()) return -EOPNOTSUPP;
        if (duration == 0 && !resource->allowUntimed) return -EINVAL;
        if (value < resource->minimum || value > resource->maximum) return -EINVAL;
    }
    const auto old = requests_.find(handle);
    if (handle > 0 && old == requests_.end()) return -ENOENT;
    if (old != requests_.end() && !(old->second.owner == owner)) return -EPERM;
    if (handle == 0 && (requests_.size() >= 128 || std::count_if(requests_.begin(), requests_.end(),
            [&owner](const auto& item) { return item.second.owner == owner; }) >= 16)) return -ENOSPC;
    if (handle == 0 && nextHandle_ > std::numeric_limits<int32_t>::max()) return -ENOSPC;
    const int32_t actualHandle = handle == 0 ? static_cast<int32_t>(nextHandle_) : handle;
    Requests candidate = requests_;
    candidate.insert_or_assign(actualHandle, Request{owner, duration == 0 ?
            std::numeric_limits<Millis>::max() : now + duration, values});
    const Values desired = aggregate(candidate);
    if (desired != applied_ && !backend_.apply(desired)) {
        // Even a partially failing adapter cannot publish a successful handle.
        dirty_ = true;
        reconcile();
        return -EIO;
    }
    requests_ = std::move(candidate);
    applied_ = desired;
    dirty_ = false;
    if (handle == 0) ++nextHandle_;
    return actualHandle;
}

int RequestManager::release(Owner owner, int32_t handle, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    removeExpired(now);
    const auto item = requests_.find(handle);
    if (item == requests_.end()) {
        reconcile();
        return -ENOENT;
    }
    if (!(item->second.owner == owner)) {
        reconcile();
        return -EPERM;
    }
    requests_.erase(item);
    return reconcile() ? 0 : -EIO;
}

bool RequestManager::releaseOwner(Owner owner, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    removeExpired(now);
    for (auto it = requests_.begin(); it != requests_.end();) {
        if (it->second.owner == owner) it = requests_.erase(it);
        else ++it;
    }
    return reconcile();
}

bool RequestManager::expire(Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    removeExpired(now);
    return reconcile();
}

bool RequestManager::setEnabled(bool enabled, Millis now) {
    return setInhibit(Inhibit::Manual, !enabled, now);
}

bool RequestManager::setInhibit(Inhibit reason, bool blocked, Millis now) {
    std::lock_guard<std::mutex> lock(mutex_);
    removeExpired(now);
    const auto bit = static_cast<uint32_t>(reason);
    if (blocked) inhibited_ |= bit;
    else inhibited_ &= ~bit;
    enabled_ = inhibited_ == 0;
    if (!enabled_) requests_.clear();
    return reconcile();
}

Snapshot RequestManager::snapshot() const {
    std::lock_guard<std::mutex> lock(mutex_);
    Millis expiry = std::numeric_limits<Millis>::max();
    for (const auto& [handle, request] : requests_) expiry = std::min(expiry, request.expiry);
    return {requests_.size(), enabled_, dirty_, aggregate(requests_), applied_, expiry};
}

}  // namespace gold::power
