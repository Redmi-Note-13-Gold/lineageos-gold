// SPDX-License-Identifier: Apache-2.0
#include "NodeBackend.h"

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <fcntl.h>
#include <sstream>
#include <unistd.h>

namespace gold::power {
namespace {
constexpr std::array<int, 2> kMin{kCpu0Min, kCpu1Min};
constexpr std::array<int, 2> kMax{kCpu0Max, kCpu1Max};
const std::map<int, std::string> kScalarNodes{{kTopAppUclamp, NodeBackend::kUclamp},
        {kTopAppPreferIdle, NodeBackend::kPreferIdle}};
bool scalar(NodeIo& io, const std::string& path, int expected) {
    std::string text;
    if (!io.read(path, &text)) return false;
    std::istringstream stream(text);
    double value;
    return (stream >> value) && std::isfinite(value) && value == expected && (stream >> std::ws).eof();
}
}  // namespace

bool PosixNodeIo::read(const std::string& path, std::string* value) {
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return false;
    value->clear();
    char buffer[4096];
    ssize_t count;
    do {
        count = ::read(fd, buffer, sizeof(buffer));
        if (count > 0) value->append(buffer, count);
    } while ((count > 0 || (count < 0 && errno == EINTR)) && value->size() < 65536);
    close(fd);
    return count == 0;
}

bool PosixNodeIo::write(const std::string& path, const std::string& value) {
    int fd = open(path.c_str(), O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return false;
    ssize_t count;
    // One procfs/sysfs request must be one write. Never retry a partial write as
    // another command, and never create an absent node or truncate a filesystem.
    do { count = ::write(fd, value.data(), value.size()); } while (count < 0 && errno == EINTR);
    int closed = close(fd);
    return count == static_cast<ssize_t>(value.size()) && closed == 0;
}

NodeBackend::NodeBackend(NodeIo& io) : io_(io) {}

bool NodeBackend::discover() {
    ready_ = false;
    for (unsigned c = 0; c < 2; ++c) {
        std::string text;
        std::string path = "/sys/devices/system/cpu/cpufreq/policy" + std::string(c ? "6" : "0") +
                "/scaling_available_frequencies";
        if (!io_.read(path, &text)) { error_ = "Missing cpufreq table: " + path; return false; }
        std::istringstream stream(text);
        auto& table = frequencies_[c];
        table.clear();
        int frequency;
        while (stream >> frequency) {
            if (frequency <= 0 || frequency > 4000000) return false;
            table.push_back(frequency);
        }
        if (!stream.eof() || table.empty() || table.size() > 64 ||
                !std::is_sorted(table.begin(), table.end(), std::greater<int>()) ||
                std::adjacent_find(table.begin(), table.end()) != table.end()) {
            error_ = "Invalid or unordered cpufreq table";
            return false;
        }
    }
    std::string ppm, policies;
    if (!io_.read(kPpm, &ppm) || ppm.find("[2] PERFSERV:") == std::string::npos ||
            !io_.read("/proc/ppm/policy_status", &policies) ||
            policies.find("PPM_POLICY_THERMAL: enabled") == std::string::npos ||
            policies.find("PPM_POLICY_DLPT: enabled") == std::string::npos ||
            policies.find("PPM_POLICY_SYS_BOOST: enabled") == std::string::npos) {
        error_ = "Missing PPM client or thermal/DLPT arbitration";
        return false;
    }
    // Confirm the scalar nodes exist; apply() then resets our owned votes.
    for (const auto& [id, path] : kScalarNodes) {
        std::string text;
        if (!io_.read(path, &text)) { error_ = "Missing resource: " + path; return false; }
    }
    ready_ = true;
    uncertain_ = true;
    return true;
}

std::vector<Resource> NodeBackend::resources() const {
    if (!ready_) return {};
    return {{kCpu0Min, -1, frequencies_[0].front(), -1, true},
            {kCpu0Max, -1, frequencies_[0].front(), -1, false},
            {kCpu1Min, -1, frequencies_[1].front(), -1, true},
            {kCpu1Max, -1, frequencies_[1].front(), -1, false},
            {kTopAppUclamp, 0, 100, 0, true},
            {kTopAppPreferIdle, 0, 1, 0, true, true}};
}

int NodeBackend::index(unsigned cluster, int frequency) const {
    if (frequency == -1) return -1;
    const auto& table = frequencies_[cluster];
    auto it = std::find(table.begin(), table.end(), frequency);
    return it == table.end() ? -2 : static_cast<int>(it - table.begin());
}

bool NodeBackend::normalize(const Values& values, Values* effective) const {
    if (!ready_ || values.size() != resources().size()) return false;
    for (const auto& resource : resources()) {
        auto it = values.find(resource.id);
        if (it == values.end() || it->second < resource.minimum || it->second > resource.maximum) return false;
    }
    *effective = values;
    for (unsigned c = 0; c < 2; ++c) {
        int low = values.at(kMin[c]);
        int high = values.at(kMax[c]);
        const auto& table = frequencies_[c];
        if ((low != -1 && low < table.back()) || (high != -1 && high < table.back())) return false;
        // Choose available OPPs. Maximum constraints win when votes conflict.
        if (low != -1) {
            for (int freq : table) if (freq >= low) (*effective)[kMin[c]] = freq;
        }
        if (high != -1) {
            for (int freq : table) if (freq <= high) { (*effective)[kMax[c]] = freq; break; }
        }
        low = effective->at(kMin[c]);
        high = effective->at(kMax[c]);
        if (high != -1 && low > high) (*effective)[kMin[c]] = high;
    }
    return true;
}

bool NodeBackend::writeState(const Values& values, bool force) {
    for (unsigned c = 0; c < 2; ++c) {
        if (force || applied_.at(kMin[c]) != values.at(kMin[c]) ||
                applied_.at(kMax[c]) != values.at(kMax[c])) {
            std::string command = "2 " + std::to_string(c) + " " + std::to_string(values.at(kMin[c])) +
                    " " + std::to_string(values.at(kMax[c])) + "\n";
            if (!io_.write(kPpm, command)) { error_ = "PPM write failed"; return false; }
        }
    }
    for (const auto& [id, path] : kScalarNodes) {
        if ((force || applied_.at(id) != values.at(id)) &&
                !io_.write(path, std::to_string(values.at(id)) + "\n")) {
            error_ = "Resource write failed: " + path;
            return false;
        }
    }
    return verify(values);
}

bool NodeBackend::verify(const Values& values) {
    std::string text;
    if (!io_.read(kPpm, &text)) { error_ = "PPM readback failed"; return false; }
    auto start = text.find("[2] PERFSERV:");
    if (start == std::string::npos) { error_ = "PPM client disappeared"; return false; }
    auto line = text.substr(start, text.find('\n', start) - start);
    int unused, indices[4], consumed = 0;
    if (sscanf(line.c_str(), "[2] PERFSERV: %d (%d)(%d)(%d)(%d)%n", &unused,
               &indices[0], &indices[1], &indices[2], &indices[3], &consumed) != 5 || unused != 0 ||
            line.find_first_not_of(" \t\r", consumed) != std::string::npos) {
        error_ = "Unexpected PPM readback format";
        return false;
    }
    for (unsigned c = 0; c < 2; ++c) {
        if (indices[c * 2] != index(c, values.at(kMin[c])) ||
                indices[c * 2 + 1] != index(c, values.at(kMax[c]))) {
            error_ = "PPM vote not applied";
            return false;
        }
    }
    for (const auto& [id, path] : kScalarNodes) {
        if (!scalar(io_, path, values.at(id))) { error_ = "Resource readback differs: " + path; return false; }
    }
    return true;
}

bool NodeBackend::apply(const Values& values) {
    Values effective;
    if (!normalize(values, &effective)) { error_ = "Invalid resource values"; return false; }
    if (!uncertain_ && effective == applied_) {
        if (verify(effective)) { error_.clear(); return true; }
        // A cached aggregate does not prove the kernel still has our vote.
        // Force the owned resources back to that aggregate before acknowledging
        // an unchanged request or a successful timeout/release.
        uncertain_ = true;
    }
    if (writeState(effective, uncertain_ || applied_.empty())) {
        applied_ = std::move(effective);
        uncertain_ = false;
        error_.clear();
        return true;
    }
    // Restore every previously authoritative node after a partial failure.
    // A failed rollback stays uncertain; the manager must continue retrying.
    std::string failure = error_;
    uncertain_ = true;
    if (!applied_.empty()) writeState(applied_, true);
    error_ = failure;
    return false;
}

}  // namespace gold::power
