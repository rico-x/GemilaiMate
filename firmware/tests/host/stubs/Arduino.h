#pragma once
#include <cstdint>
#include <functional>
#include <algorithm>
#include <mutex>
using std::min;
using std::max;
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define FALLING 3
#define ARDUINO_ISR_ATTR
#define ESP_LOGI(...)
#define portTICK_PERIOD_MS 1
#define configMINIMAL_STACK_SIZE 128
using portMUX_TYPE = std::recursive_mutex;
#define portMUX_INITIALIZER_UNLOCKED {}
#define portENTER_CRITICAL(p) ((p)->lock())
#define portEXIT_CRITICAL(p) ((p)->unlock())
#define portENTER_CRITICAL_ISR(p) ((p)->lock())
#define portEXIT_CRITICAL_ISR(p) ((p)->unlock())
using xTaskHandle=void *;
uint32_t micros();
void pinMode(uint8_t,int);
void digitalWrite(uint8_t,int);
int digitalRead(uint8_t);
int digitalPinToInterrupt(uint8_t);
void attachInterrupt(int,void(*)(),int);
void detachInterrupt(int);
inline void xTaskCreate(void(*)(void*),const char*,int,void*,int,void**) {}
inline void vTaskDelay(int) {}
