#ifndef CONTROLLERCONFIG_H
#define CONTROLLERCONFIG_H
#include <string>

struct Capabilities {
    bool dimming;
    bool pressure;
    bool ssrPump;
    bool ledControls;
    bool tof;
};

struct ControllerConfig {
    std::string name;

    // The autodetect value that is measured through a PCB voltage divider.
    // The detected value in milli volts is divided by 100 and rounded.
    uint16_t autodetectValue;

    uint8_t heaterPin;
    uint8_t pumpPin;
    uint8_t pumpSensePin = 0;
    uint8_t pumpOn;
    uint8_t valvePin;
    uint8_t valveOn;
    uint8_t altPin;
    uint8_t altOn;

    uint8_t pressureScl = 0;
    uint8_t pressureSda = 0;

    uint8_t maxSckPin;
    uint8_t maxCsPin;
    uint8_t maxMisoPin;

    uint8_t brewButtonPin;
    uint8_t steamButtonPin;

    uint8_t scaleSclPin;
    uint8_t scaleSdaPin;
    uint8_t scaleSda1Pin;

    uint8_t sunriseSclPin;
    uint8_t sunriseSdaPin;

    uint8_t ext1Pin;
    uint8_t ext2Pin;
    uint8_t ext3Pin;
    uint8_t ext4Pin;
    uint8_t ext5Pin;

    Capabilities capabilites;
};

// ID=3 is deliberately shared with upstream GM_PRO_LEGO. It cannot identify
// the old DevKit wiring versus the compact WROOM board: select the target at
// build time, never probe GPIO43/44 on a legacy board with a UART bridge.
#ifdef GEMILAIMATE_COMPACT
static constexpr const char *GEMILAI_BOARD_NAME = "GemilaiMate Compact Shield";
static constexpr uint8_t GEMILAI_PERIPHERAL_SCL = 44;
static constexpr uint8_t GEMILAI_PERIPHERAL_SDA = 43;
#else
static constexpr const char *GEMILAI_BOARD_NAME = "GemilaiMate Gemilai 3007Z";
static constexpr uint8_t GEMILAI_PERIPHERAL_SCL = 16;
static constexpr uint8_t GEMILAI_PERIPHERAL_SDA = 15;
#endif

const ControllerConfig GEMILAI_3007Z = {.name = GEMILAI_BOARD_NAME,
                                      .autodetectValue = 3,
                                      .heaterPin = 14,
                                      .pumpPin = 9,
                                      .pumpSensePin = 21,
                                      .pumpOn = 1,
                                      .valvePin = 10,
                                      .valveOn = 1,
                                      .altPin = 47,
                                      .altOn = 1,
                                      .pressureScl = 41,
                                      .pressureSda = 42,
                                      .maxSckPin = 6,
                                      .maxCsPin = 7,
                                      .maxMisoPin = 4,
                                      .brewButtonPin = 38,
                                      .steamButtonPin = 48,
                                      .scaleSclPin = 17,
                                      .scaleSdaPin = 18,
                                      .scaleSda1Pin = 39,
                                      // Compact: upstream Alba 43/44. Legacy carrier/shield: hand-wired 15/16;
                                      // their 43/44 are occupied by the DevKit USB-UART bridge.
                                      .sunriseSclPin = GEMILAI_PERIPHERAL_SCL,
                                      .sunriseSdaPin = GEMILAI_PERIPHERAL_SDA,
                                      .ext1Pin = 1,
                                      .ext2Pin = 2,
                                      .ext3Pin = 8,
                                      .ext4Pin = 12,
                                      .ext5Pin = 13,
                                      .capabilites = {
                                          .dimming = true,
                                          .pressure = true,
                                          .ssrPump = false,
                                          .ledControls = false,
                                          .tof = false,
                                      }};

#endif // CONTROLLERCONFIG_H
