#include <pgmspace.h>

#define SECRET
#define THINGNAME "esp32-sensor"

const char WIFI_SSID[] = "wifi-name";
const char WIFI_PASSWORD[] = "wifi-password";
const char AWS_IOT_ENDPOINT[] = "xxxxxxxxxxxxxx-ats.iot.ap-northeast-1.amazonaws.com";

// Amazon Root CA 1 (paste the whole PEM, about 20 lines)
static const char AWS_CERT_CA[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
)EOF";

// Device Certificate (paste the whole PEM, about 20 lines)
static const char AWS_CERT_CRT[] PROGMEM = R"KEY(
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
)KEY";

// Device Private Key (paste the whole PEM, about 27 lines)
static const char AWS_CERT_PRIVATE[] PROGMEM = R"KEY(
-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----
)KEY";
