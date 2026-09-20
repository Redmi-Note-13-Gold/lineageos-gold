// SPDX-License-Identifier: Apache-2.0
#pragma once

#include "RequestManager.h"

#include <array>
#include <string>

namespace gold::power {

constexpr int32_t kCpu0Min = 0x00400000;
constexpr int32_t kCpu0Max = 0x00404000;
constexpr int32_t kCpu1Min = 0x00400100;
constexpr int32_t kCpu1Max = 0x00404100;
constexpr int32_t kTopAppUclamp = 0x01408300;
constexpr int32_t kTopAppPreferIdle = 0x01404300;
constexpr int32_t kDisplayIdleTime = 0x0240C000;

struct NodeIo {
    virtual ~NodeIo() = default;
    virtual bool read(const std::string& path, std::string* value) = 0;
    virtual bool write(const std::string& path, const std::string& value) = 0;
};

class PosixNodeIo final : public NodeIo {
  public:
    bool read(const std::string& path, std::string* value) override;
    bool write(const std::string& path, const std::string& value) override;
};

// Owns only the PERFSERV PPM client and the three reviewed scheduler/display
// nodes. PPM merges its votes with THERMAL/DLPT and the other sysboost users.
// No global cpufreq max, core_ctl, thermal or governor configuration is changed.
class NodeBackend final : public Backend {
  public:
    explicit NodeBackend(NodeIo& io);
    bool discover();
    std::vector<Resource> resources() const;
    bool apply(const Values& values) override;
    const Values& effective() const { return applied_; }
    const std::string& error() const { return error_; }
    static constexpr const char* kPpm = "/proc/ppm/policy/sysboost_cluster_freq_limit";
    static constexpr const char* kUclamp = "/dev/cpuctl/top-app/cpu.uclamp.min";
    static constexpr const char* kPreferIdle = "/dev/cpuctl/top-app/cpu.uclamp.latency_sensitive";
    static constexpr const char* kIdleTime = "/proc/displowpower/idletime";

  private:
    bool writeState(const Values& values, bool force);
    bool verify(const Values& values);
    bool normalize(const Values& values, Values* effective) const;
    int index(unsigned cluster, int frequency) const;
    NodeIo& io_;
    std::array<std::vector<int>, 2> frequencies_;
    Values applied_;
    bool ready_ = false;
    bool uncertain_ = true;
    std::string error_;
};

}  // namespace gold::power
