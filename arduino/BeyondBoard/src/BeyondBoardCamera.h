// Camera for BeyondBoard: take a photo in one line, then save it or ask about it.
//
//   #include "aws_config.h"
//   #include <BeyondBoardCamera.h>
//
//   camera.begin(CAMERA_FREENOVE_ESP32S3);
//   Photo p = camera.capture();
//   aws.save("door.jpg", p);
//   String what = aws.ask("What is in this picture?", p);
//
// Only sketches that include this file build in the camera driver.
// The pin numbers follow the boards' CameraWebServer examples.
#pragma once

#if !defined(ESP32)
#error "BeyondBoardCamera needs an ESP32 board with a camera."
#endif

#include <esp_camera.h>

#include "BeyondBoard.h"

enum CameraBoard {
  CAMERA_FREENOVE_ESP32S3,  // Freenove ESP32-S3-WROOM CAM (same pins as ESP32-S3-EYE)
  CAMERA_ESP32S3_EYE,
  CAMERA_AI_THINKER,        // AI-Thinker ESP32-CAM
  CAMERA_XIAO_ESP32S3,      // Seeed XIAO ESP32S3 Sense (not yet tried on hardware)
};

// A JPEG photo. It is given back to the camera when it goes out of scope.
class Photo : public CloudBytes {
 public:
  Photo() {}
  explicit Photo(camera_fb_t* fb) : CloudBytes(fb ? fb->buf : nullptr, fb ? fb->len : 0), _fb(fb) {}
  Photo(Photo&& other) noexcept : CloudBytes(other.data, other.length), _fb(other._fb) {
    other._fb = nullptr;
  }
  Photo& operator=(Photo&& other) noexcept {
    if (this != &other) {
      release();
      data = other.data;
      length = other.length;
      _fb = other._fb;
      other._fb = nullptr;
    }
    return *this;
  }
  Photo(const Photo&) = delete;
  Photo& operator=(const Photo&) = delete;
  ~Photo() { release(); }

  bool ok() const { return _fb != nullptr; }

 private:
  void release() {
    if (_fb) esp_camera_fb_return(_fb);
    _fb = nullptr;
    data = nullptr;
    length = 0;
  }
  camera_fb_t* _fb = nullptr;
};

class CloudCamera {
 public:
  // Starts the camera. size: FRAMESIZE_QVGA (320x240) ... FRAMESIZE_UXGA; quality: 10 (best) .. 63.
  bool begin(CameraBoard board, framesize_t size = FRAMESIZE_VGA, int quality = 12) {
    camera_config_t c = {};
    int pins[16];  // pwdn, reset, xclk, sda, scl, d7..d0, vsync, href, pclk
    switch (board) {
      case CAMERA_FREENOVE_ESP32S3:
      case CAMERA_ESP32S3_EYE: {
        int p[] = {-1, -1, 15, 4, 5, 16, 17, 18, 12, 10, 8, 9, 11, 6, 7, 13};
        memcpy(pins, p, sizeof(pins));
        break;
      }
      case CAMERA_AI_THINKER: {
        int p[] = {32, -1, 0, 26, 27, 35, 34, 39, 36, 21, 19, 18, 5, 25, 23, 22};
        memcpy(pins, p, sizeof(pins));
        break;
      }
      case CAMERA_XIAO_ESP32S3: {
        int p[] = {-1, -1, 10, 40, 39, 48, 11, 12, 14, 16, 18, 17, 15, 38, 47, 13};
        memcpy(pins, p, sizeof(pins));
        break;
      }
    }
    c.pin_pwdn = pins[0];
    c.pin_reset = pins[1];
    c.pin_xclk = pins[2];
    c.pin_sccb_sda = pins[3];
    c.pin_sccb_scl = pins[4];
    c.pin_d7 = pins[5];
    c.pin_d6 = pins[6];
    c.pin_d5 = pins[7];
    c.pin_d4 = pins[8];
    c.pin_d3 = pins[9];
    c.pin_d2 = pins[10];
    c.pin_d1 = pins[11];
    c.pin_d0 = pins[12];
    c.pin_vsync = pins[13];
    c.pin_href = pins[14];
    c.pin_pclk = pins[15];
    c.xclk_freq_hz = 20000000;
    c.ledc_timer = LEDC_TIMER_0;
    c.ledc_channel = LEDC_CHANNEL_0;
    c.pixel_format = PIXFORMAT_JPEG;
    c.frame_size = size;
    c.jpeg_quality = quality;
    c.fb_count = psramFound() ? 2 : 1;
    c.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
    c.grab_mode = CAMERA_GRAB_LATEST;
    if (!psramFound() && size > FRAMESIZE_QVGA) c.frame_size = FRAMESIZE_QVGA;

    esp_err_t err = esp_camera_init(&c);
    if (err != ESP_OK) {
      _error = String(F("The camera did not start (error 0x")) + String(err, HEX) +
               F("). Check the board name in camera.begin(), and that PSRAM is enabled in Tools.");
      return false;
    }
    _error = "";
    return true;
  }

  // Takes one JPEG photo. Check photo.ok().
  Photo capture() {
    Photo p(esp_camera_fb_get());
    _error = p.ok() ? String() : String(F("Could not take a photo."));
    return p;
  }

  String lastError() const { return _error; }

 private:
  String _error;
};

inline CloudCamera camera;
