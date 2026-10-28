#ifndef NANOPBCOMM_PROTOCOL_H
#define NANOPBCOMM_PROTOCOL_H

#include "Messages.h"
#include <cstdint>

// Shared protocol UUIDs and helpers used by both ends.
namespace gm_proto {

// BLE service + chars: one TX/RX pair carries framed nanopb datagrams; the identifiers are scoped to this project.
static constexpr const char *SERVICE_UUID = "97aa4f3f-498a-519a-9810-7f75a1ed00a4";
// Controller (server) -> display (client) notifications.
static constexpr const char *TX_CHAR_UUID = "ad38b858-bfc6-593b-a70d-30983c3fed89";
// Display (client) -> controller (server) writes.
static constexpr const char *RX_CHAR_UUID = "b330d58f-ee80-5b7a-a1cf-df3fb3fc7a98";
// Legacy read-only system-info characteristic (JSON), kept for external readers.
static constexpr const char *INFO_CHAR_UUID = "b2a628d0-a050-575e-9412-0cbc6f070708";
// Legacy error characteristic; displays <= v1.8.1 dereference it unchecked, so the server keeps an inert stub (GM-221).
static constexpr const char *LEGACY_ERROR_CHAR_UUID = "3261f297-5e5b-54dc-ab3c-cc884f42674b";

// Bump on any breaking gemilaimate.proto change; carried in SystemInfo.protocol_version for mismatch detection.
static constexpr uint32_t PROTOCOL_VERSION = 5;

// Outbound priorities (higher wins in the queue).
enum Priority : uint8_t {
    PRIO_LOW = 50,      // telemetry: sensor / volumetric / tof
    PRIO_NORMAL = 100,  // settings, system info, tare, led, autotune
    PRIO_CONTROL = 150, // boiler / pump / valve / alt output control
    PRIO_HIGH = 200,    // ping, error
};

// Per-family device-index space for the coalescing key; keeps keys dense so the queue's reverse-lookup stays small.
static constexpr uint16_t MAX_DEVICES = 8;

// Coalescing key (family, device index): repeated updates for one component collapse to the latest value.
inline uint16_t coalescingKey(const gm::Payload &p) {
    uint16_t index = 0;
    switch (p.which_content) {
    case gemilaimate_Payload_boiler_tag:
        index = p.content.boiler.index;
        break;
    case gemilaimate_Payload_pump_tag:
        index = p.content.pump.index;
        break;
    case gemilaimate_Payload_relay_tag:
        index = p.content.relay.index;
        break;
    case gemilaimate_Payload_button_tag:
        index = p.content.button.index;
        break;
    default:
        index = 0;
        break;
    }
    if (index >= MAX_DEVICES)
        index = MAX_DEVICES - 1;
    return static_cast<uint16_t>(p.which_content) * MAX_DEVICES + index;
}

inline uint8_t defaultPriority(pb_size_t which) {
    switch (which) {
    case gemilaimate_Payload_ping_tag:
    case gemilaimate_Payload_error_tag:
        return PRIO_HIGH;
    case gemilaimate_Payload_boiler_tag:
    case gemilaimate_Payload_pump_tag:
    case gemilaimate_Payload_relay_tag:
        return PRIO_CONTROL;
    case gemilaimate_Payload_sensor_tag:
    case gemilaimate_Payload_volumetric_tag:
    case gemilaimate_Payload_tof_tag:
        return PRIO_LOW;
    default:
        return PRIO_NORMAL;
    }
}

} // namespace gm_proto

#endif // NANOPBCOMM_PROTOCOL_H
