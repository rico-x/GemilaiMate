#ifndef WEBUIPLUGIN_H
#define WEBUIPLUGIN_H

#define ELEGANTOTA_USE_ASYNC_WEBSERVER 1

#include <DNSServer.h>

#include <ArduinoJson.h>
#include <ESPAsyncWebServer.h>
#include <display/core/Plugin.h>
#include <display/plugins/WebSocketHandler.h>
#include <display/util/PsramAllocator.h>

constexpr size_t DNS_PERIOD = 50;

const String LOCAL_URL = "http://4.4.4.1/";

class ProfileManager;

class WebUIPlugin : public Plugin {
  public:
    WebUIPlugin();
    void setup(Controller *controller, PluginManager *pluginManager) override;
    void loop() override;

  private:
    void setupServer();
    void start();
    void stop();

    // Compatibility request handlers report that this release uses manual USB updates.
    void handleOTASettings(JsonDocument &request);
    void handleOTAStart(JsonDocument &request);

    // HTTP handlers
    // Serves the web UI from the firmware-embedded, memory-mapped flash blob
    // (catch-all for any path not claimed by an explicit route). [GM-106]
    void serveWebAsset(AsyncWebServerRequest *request);
    void handleSettings(AsyncWebServerRequest *request) const;
    void handleBLEScaleList(AsyncWebServerRequest *request);
    void handleBLEScaleScan(AsyncWebServerRequest *request);
    void handleBLEScaleConnect(AsyncWebServerRequest *request);
    void handleBLEScaleInfo(AsyncWebServerRequest *request);
    void updateOTAStatus(const String &version);
    void updateOTAProgress(uint8_t phase, int progress);

    // Core dump download
    void handleCoreDumpDownload(AsyncWebServerRequest *request);

    AsyncWebServer server;
    WebSocketHandler wsHandler;
    Controller *controller = nullptr;
    PluginManager *pluginManager = nullptr;
    DNSServer *dnsServer = nullptr;
    ProfileManager *profileManager = nullptr;

    long lastUpdateCheck = 0;
    long lastDns = 0;
    bool updating = false;
    bool apMode = false;
    bool serverRunning = false;
    String updateComponent = "";
};

#endif // WEBUIPLUGIN_H
