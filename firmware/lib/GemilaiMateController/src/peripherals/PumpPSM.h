#pragma once
#include <Arduino.h>
#include <esp_timer.h>

// Local controller-only replacement for the interrupt-only upstream PSM.
// Faults are latched until reset: new commands or returning ZC cannot restart it.
class PumpPSM {
public:
    static constexpr uint32_t EDGE_TIMEOUT_US = 30000;
    static constexpr uint32_t START_TIMEOUT_US = 250000;
    PumpPSM(uint8_t sensePin, uint8_t controlPin);
    ~PumpPSM();
    bool beginWatchdog();
    void set(unsigned int value);
    void service();
    bool faulted();
    bool ready();
    unsigned int cps();
    unsigned char getDivider();
    long getCounter();
    void resetCounter();
private:
    uint8_t _sensePin, _controlPin;
    portMUX_TYPE _mux = portMUX_INITIALIZER_UNLOCKED;
    esp_timer_handle_t _timer = nullptr;
    uint32_t _lastEdge = 0, _requestStart = 0;
    unsigned int _value = 0, _accumulator = 0, _edgeHz = 0;
    unsigned char _divider = 2, _phase = 0, _candidate = 0, _stableEdges = 0;
    bool _seenEdge = false, _armed = false, _fault = false;
    long _counter = 0;
    static PumpPSM *_instance;
    static void ARDUINO_ISR_ATTR onInterrupt();
    static void timerCallback(void *arg);
    void ARDUINO_ISR_ATTR edgeLocked(uint32_t now);
    void ARDUINO_ISR_ATTR stopLocked();
    void ARDUINO_ISR_ATTR latchFaultLocked();
};
