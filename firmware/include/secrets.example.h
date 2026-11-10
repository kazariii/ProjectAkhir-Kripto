#pragma once

// Copy to secrets.h (ignored by Git). These values cannot connect to a broker.
constexpr char WIFI_SSID[] = "Wokwi-GUEST";
constexpr char WIFI_PASSWORD[] = "";
constexpr char MQTT_HOST[] = "ISI_HOSTNAME_DEPLOYMENT";
constexpr char MQTT_USERNAME[] = "esp32-meja01";
constexpr char MQTT_PASSWORD[] = "ISI_PASSWORD_HEX";
constexpr char MQTT_ROOT_CA[] = R"PEM(
-----BEGIN CERTIFICATE-----
ISI_CA_DARI_DEPLOYMENT_EMQX
-----END CERTIFICATE-----
)PEM";
