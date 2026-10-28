#include "PingWatchdog.h"
#include <cassert>
#include <iostream>

int main() {
    constexpr uint32_t timeout = 20000;
    std::atomic<uint32_t> last{1000};
    int cases = 0;
    // Concurrent heartbeat regression: the clock captures 1000, then BLE publishes 1001 before
    // the clock call returns. Old clock-first subtraction underflows.
    auto interleavedClock = [&]() { last.store(1001); return 1000u; };
    const uint32_t oldNow = interleavedClock();
    assert(uint32_t(oldNow - last.load()) >= timeout);
    last.store(1000);
    assert(!gm::pingTimedOut(last, timeout, interleavedClock));
    ++cases;
    // True deadline, without suppressing a real 20-second timeout.
    last.store(1000);
    assert(!gm::pingTimedOut(last, timeout, [] { return 20999u; }));
    assert(gm::pingTimedOut(last, timeout, [] { return 21000u; }));
    assert(gm::pingTimedOut(last, timeout, [] { return 21001u; }));
    ++cases;
    // millis wraparound remains valid on a 64-bit host.
    const uint32_t beforeWrap = 0xfffffff0u;
    last.store(beforeWrap);
    assert(!gm::pingTimedOut(last, timeout, [] { return 16u; }));
    assert(!gm::pingTimedOut(last, timeout, [=] { return uint32_t(beforeWrap + timeout - 1); }));
    assert(gm::pingTimedOut(last, timeout, [=] { return uint32_t(beforeWrap + timeout); }));
    ++cases;
    // Refresh at the old deadline invalidates the stale snapshot.
    last.store(1000);
    assert(!gm::pingTimedOut(last, timeout, [&] { last.store(21000); return 21000u; }));
    ++cases;
    // 24-hour simulated exchange, crossing rollover, then a genuine outage.
    uint32_t now = 0xffff0000u;
    last.store(now);
    for (uint32_t elapsed = 250; elapsed <= 86400000; elapsed += 250) {
        now += 250;
        if (elapsed % 1000 == 0) last.store(now);
        assert(!gm::pingTimedOut(last, timeout, [&] { return now; }));
    }
    now += timeout;
    assert(gm::pingTimedOut(last, timeout, [&] { return now; }));
    ++cases;
    assert(cases == 5);
    std::cout << "PASS 5 ping-watchdog scenarios: concurrent sampling, concurrent refresh, deadline, 32-bit rollover, 24-hour simulated exchange then outage.\n";
}
