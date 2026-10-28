#include "PumpPSM.h"
#include "DigitalInput.h"
#include <array>
#include <vector>
#include <cassert>
#include <iostream>
#include <algorithm>

uint32_t clockUs=100000;
std::array<int,256> pins{};
std::array<void(*)(),256> irq{};
struct FakeTimer {esp_timer_create_args_t args;bool running=false;};
std::vector<FakeTimer*> timers;
bool timerFails=false;
uint32_t micros(){return clockUs;}
void pinMode(uint8_t,int){}
void digitalWrite(uint8_t p,int v){pins[p]=v;}
int digitalRead(uint8_t p){return pins[p];}
int digitalPinToInterrupt(uint8_t p){return p;}
void attachInterrupt(int p,void(*f)(),int){irq[p]=f;}
void detachInterrupt(int p){irq[p]=nullptr;}
esp_err_t esp_timer_create(const esp_timer_create_args_t*a,esp_timer_handle_t*h){if(timerFails)return -1;*h=new FakeTimer{*a,false};timers.push_back(*h);return ESP_OK;}
esp_err_t esp_timer_start_periodic(esp_timer_handle_t t,uint64_t us){assert(us==5000);t->running=true;return ESP_OK;}
esp_err_t esp_timer_stop(esp_timer_handle_t t){t->running=false;return ESP_OK;}
esp_err_t esp_timer_delete(esp_timer_handle_t t){timers.erase(std::remove(timers.begin(),timers.end(),t),timers.end());delete t;return ESP_OK;}
void advance(uint32_t us){while(us){auto d=std::min(us,uint32_t(5000));clockUs+=d;us-=d;for(auto*t:timers)if(t->running)t->args.callback(t->args.arg);}}
void edge(uint32_t dt=10000){advance(dt);assert(irq[21]);irq[21]();}
void qualify(uint32_t dt=10000){for(int i=0;i<5;i++)edge(dt);}
void on(PumpPSM&p){p.set(100);edge();edge();assert(pins[9]==HIGH);}
int main(){int cases=0;
 {PumpPSM p(21,9);p.beginWatchdog();assert(pins[9]==LOW&&!p.ready());qualify();assert(p.ready()&&p.getDivider()==2&&p.cps()==50);++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();qualify(20000);assert(p.ready()&&p.getDivider()==1&&p.cps()==50);++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();qualify(8333);assert(p.ready()&&p.getDivider()==2&&p.cps()==60);++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();qualify(16666);assert(p.ready()&&p.getDivider()==1&&p.cps()==60);++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();advance(2000000);assert(!p.ready()&&!p.faulted());qualify();assert(p.ready()&&p.getDivider()==2);++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();p.set(100);advance(260000);assert(p.faulted()&&pins[9]==LOW);++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();qualify();on(p);p.set(0);assert(pins[9]==LOW);advance(1000);assert(pins[9]==LOW);++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();qualify();on(p);advance(40000);assert(p.faulted()&&pins[9]==LOW);p.set(0);qualify();p.set(100);qualify();assert(p.faulted()&&pins[9]==LOW);++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();qualify();p.set(100);edge(1000);edge(9000);assert(!p.faulted());edge();assert(pins[9]==HIGH);++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();qualify();on(p);edge(20000);assert(p.faulted()&&pins[9]==LOW);++cases;}
 {clockUs=0xffff0000U;PumpPSM p(21,9);p.beginWatchdog();qualify();on(p);advance(40000);assert(p.faulted()&&pins[9]==LOW);clockUs=100000;++cases;}
 {PumpPSM p(21,9);p.beginWatchdog();qualify();p.set(50);int onCycles=0;for(int i=0;i<20;i++){edge();int a=pins[9];edge();onCycles+=pins[9]==HIGH;if(i)assert(a==((i-1)%2?HIGH:LOW));}assert(onCycles==10);++cases;}
 {PumpPSM p(21,9);timerFails=true;assert(!p.beginWatchdog());p.set(100);qualify();assert(p.faulted()&&pins[9]==LOW);timerFails=false;++cases;}
 {std::vector<bool> events;DigitalInput input(38,[&](bool x){events.push_back(x);});input.setup();auto poll=[&](int state,int count){pins[38]=state;while(count--)input.loop();};poll(HIGH,4);assert(events.size()==1&&!events[0]);poll(LOW,1);poll(HIGH,4);assert(events.size()==1);poll(LOW,3);poll(HIGH,4);assert(events.size()==1);poll(LOW,4);poll(LOW,100);assert(events.size()==2&&events.back());poll(HIGH,4);assert(events.size()==3&&!events.back());++cases;}
 assert(timers.empty());std::cout<<"PASS "<<cases<<" host scenarios: live ZC acquisition, divider 50/60/100/120 Hz, immediate stop, loss latch, rollover, glitches, 50% density, timer failure, button debounce.\n";
}
