#pragma once
#include <cstdint>
using esp_err_t=int;
constexpr int ESP_OK=0;
constexpr int ESP_TIMER_TASK=0;
struct esp_timer_create_args_t {void(*callback)(void*)=nullptr;void*arg=nullptr;int dispatch_method=0;const char*name=nullptr;};
struct FakeTimer;
using esp_timer_handle_t=FakeTimer*;
esp_err_t esp_timer_create(const esp_timer_create_args_t*,esp_timer_handle_t*);
esp_err_t esp_timer_start_periodic(esp_timer_handle_t,uint64_t);
esp_err_t esp_timer_stop(esp_timer_handle_t);
esp_err_t esp_timer_delete(esp_timer_handle_t);
