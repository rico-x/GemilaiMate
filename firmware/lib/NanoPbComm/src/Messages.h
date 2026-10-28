#ifndef NANOPBCOMM_MESSAGES_H
#define NANOPBCOMM_MESSAGES_H

// NanoPbComm-internal aliases for nanopb types (gm::Payload vs gemilaimate_Payload); firmware never sees nanopb structs.
// The gemilaimate_*_tag/_msg/_init_zero macros are not types, so they keep their full names.

#include "gemilaimate.pb.h"

namespace gm {

using Frame = gemilaimate_Frame;
using Payload = gemilaimate_Payload;

using Ping = gemilaimate_Ping;
using BoilerControl = gemilaimate_BoilerControl;
using PumpControl = gemilaimate_PumpControl;
using RelayControl = gemilaimate_RelayControl;
using PidSettings = gemilaimate_PidSettings;
using PumpSettings = gemilaimate_PumpSettings;
using AutotuneRequest = gemilaimate_AutotuneRequest;
using PressureScale = gemilaimate_PressureScale;
using Tare = gemilaimate_Tare;
using LedChannel = gemilaimate_LedChannel;
using LedControl = gemilaimate_LedControl;

using DeviceCapabilities = gemilaimate_Capabilities;
using Addon = gemilaimate_Addon;
using SystemInfo = gemilaimate_SystemInfo;
using SensorData = gemilaimate_SensorData;
using BoilerReading = gemilaimate_BoilerReading;
using ButtonState = gemilaimate_ButtonState;
using AutotuneResult = gemilaimate_AutotuneResult;
using VolumetricMeasurement = gemilaimate_VolumetricMeasurement;
using TofMeasurement = gemilaimate_TofMeasurement;
using Error = gemilaimate_Error;

using PumpMode = gemilaimate_PumpMode;
using BoilerMode = gemilaimate_BoilerMode;
using ErrorCode = gemilaimate_ErrorCode;

} // namespace gm

#endif // NANOPBCOMM_MESSAGES_H
