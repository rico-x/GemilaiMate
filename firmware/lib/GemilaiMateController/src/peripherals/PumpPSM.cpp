#include "PumpPSM.h"

PumpPSM *PumpPSM::_instance = nullptr;
PumpPSM::PumpPSM(uint8_t sensePin, uint8_t controlPin) : _sensePin(sensePin), _controlPin(controlPin) {
    digitalWrite(_controlPin, LOW);
    pinMode(_controlPin, OUTPUT);
    pinMode(_sensePin, INPUT_PULLUP);
    _instance = this;
    attachInterrupt(digitalPinToInterrupt(_sensePin), onInterrupt, FALLING);
}
PumpPSM::~PumpPSM() {
    detachInterrupt(digitalPinToInterrupt(_sensePin));
    if (_timer) { esp_timer_stop(_timer); esp_timer_delete(_timer); }
    if (_instance == this) _instance = nullptr;
}
bool PumpPSM::beginWatchdog() {
    esp_timer_create_args_t args = {};
    args.callback = timerCallback; args.arg = this; args.dispatch_method = ESP_TIMER_TASK; args.name = "pump-zc-guard";
    if (esp_timer_create(&args, &_timer) != ESP_OK || esp_timer_start_periodic(_timer, 5000) != ESP_OK) {
        portENTER_CRITICAL(&_mux); latchFaultLocked(); portEXIT_CRITICAL(&_mux); return false;
    }
    return true;
}
void PumpPSM::timerCallback(void *arg) { static_cast<PumpPSM *>(arg)->service(); }
void ARDUINO_ISR_ATTR PumpPSM::onInterrupt() {
    auto *p = _instance;
    if (!p) return;
    portENTER_CRITICAL_ISR(&p->_mux); p->edgeLocked(micros()); portEXIT_CRITICAL_ISR(&p->_mux);
}
void ARDUINO_ISR_ATTR PumpPSM::stopLocked() { _value = 0; _accumulator = 0; _phase = 0; digitalWrite(_controlPin, LOW); }
void ARDUINO_ISR_ATTR PumpPSM::latchFaultLocked() { _fault = true; _armed = false; _stableEdges = 0; stopLocked(); }
void PumpPSM::set(unsigned int value) {
    portENTER_CRITICAL(&_mux);
    if (value == 0 || _fault) stopLocked();
    else {
        if (_value == 0) _requestStart = micros();
        _value = value > 100 ? 100 : value;
        if (!_armed) digitalWrite(_controlPin, LOW);
    }
    portEXIT_CRITICAL(&_mux);
}
void PumpPSM::service() {
    portENTER_CRITICAL(&_mux);
    const uint32_t now = micros();
    if (_fault) stopLocked();
    else if (_armed && _seenEdge && uint32_t(now - _lastEdge) > EDGE_TIMEOUT_US) {
        if (_value > 0) latchFaultLocked();
        else { _armed = false; _stableEdges = 0; _seenEdge = false; digitalWrite(_controlPin, LOW); }
    } else if (!_armed && _value > 0 && uint32_t(now - _requestStart) > START_TIMEOUT_US) latchFaultLocked();
    portEXIT_CRITICAL(&_mux);
}
void ARDUINO_ISR_ATTR PumpPSM::edgeLocked(uint32_t now) {
    if (_fault) { digitalWrite(_controlPin, LOW); return; }
    if (!_seenEdge) { _seenEdge = true; _lastEdge = now; return; }
    const uint32_t dt = uint32_t(now - _lastEdge);
    if (dt < 4000) return; // Ignore contact/opto ringing, never advance the phase.
    _lastEdge = now;
    const unsigned char band = dt >= 6000 && dt <= 13000 ? 2 : (dt >= 15000 && dt <= 24000 ? 1 : 0);
    if (!band || (_armed && band != _divider)) {
        if (_value > 0 && _armed) latchFaultLocked();
        else { _armed = false; _stableEdges = 0; _candidate = 0; digitalWrite(_controlPin, LOW); }
        return;
    }
    if (!_armed) {
        if (band != _candidate) { _candidate = band; _stableEdges = 1; }
        else if (_stableEdges < 4) ++_stableEdges;
        if (_stableEdges < 4) return;
        _divider = band; _phase = 0; _accumulator = 0; _armed = true;
    }
    _edgeHz = 1000000UL / dt;
    if (_value == 0) { digitalWrite(_controlPin, LOW); return; }
    if (++_phase < _divider) return;
    _phase = 0;
    _accumulator += _value;
    const bool on = _accumulator >= 100;
    if (on) { _accumulator -= 100; ++_counter; }
    digitalWrite(_controlPin, on ? HIGH : LOW);
}
bool PumpPSM::faulted() { portENTER_CRITICAL(&_mux); const bool x = _fault; portEXIT_CRITICAL(&_mux); return x; }
bool PumpPSM::ready() { portENTER_CRITICAL(&_mux); const bool x = _armed && !_fault; portEXIT_CRITICAL(&_mux); return x; }
unsigned int PumpPSM::cps() { portENTER_CRITICAL(&_mux); const unsigned int x = _edgeHz / _divider; portEXIT_CRITICAL(&_mux); return x; }
unsigned char PumpPSM::getDivider() { portENTER_CRITICAL(&_mux); const auto x = _divider; portEXIT_CRITICAL(&_mux); return x; }
long PumpPSM::getCounter() { portENTER_CRITICAL(&_mux); const long x = _counter; portEXIT_CRITICAL(&_mux); return x; }
void PumpPSM::resetCounter() { portENTER_CRITICAL(&_mux); _counter = 0; portEXIT_CRITICAL(&_mux); }
