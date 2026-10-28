#include "main.h"
#include "ControllerConfig.h"
#include "GemilaiMateController.h"

GemilaiMateController controller(BUILD_PROJECT_VERSION);

void setup() {
    Serial.begin(115200);
    controller.setup();
}

void loop() { controller.loop(); }
