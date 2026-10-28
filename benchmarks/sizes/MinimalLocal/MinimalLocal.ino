// Save one value on this computer over USB, with the library.
#include <BeyondBoard.h>
void setup() {
  local.begin();
  local.save("temp.csv", 23.5);
  Serial.println(local.lastError());
}
void loop() {}
