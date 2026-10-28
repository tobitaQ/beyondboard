// The same job as RawHttps, with the library: save one value to AWS.
#include "aws_config.h"
void setup() {
  Serial.begin(115200);
  aws.begin();
  aws.save("temp.csv", 23.5);
  Serial.println(aws.lastError());
}
void loop() {}
