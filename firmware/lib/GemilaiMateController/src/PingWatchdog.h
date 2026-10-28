#pragma once
#include <atomic>
#include <cstdint>

namespace gm {
// Sample the shared timestamp BEFORE the clock. Reversing these reads can
// turn a concurrent ping one millisecond in the future into a 2^32-1 timeout.
// Keep 32-bit arithmetic on the host too, matching ESP32 millis() rollover.
template <typename Clock>
bool pingTimedOut(const std::atomic<uint32_t> &lastPingTime, uint32_t timeoutMs, Clock clock) {
    const uint32_t last = lastPingTime.load(std::memory_order_acquire);
    const uint32_t now = static_cast<uint32_t>(clock());
    if (uint32_t(now - last) < timeoutMs) return false;
    // A ping arriving during the sample invalidates the expired snapshot.
    // A ping after this final check belongs to the next controller iteration.
    return lastPingTime.load(std::memory_order_acquire) == last;
}
} // namespace gm
