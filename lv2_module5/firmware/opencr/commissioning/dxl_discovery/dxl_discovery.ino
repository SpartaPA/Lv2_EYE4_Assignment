#include <Arduino.h>

// Remove Arduino macros before including the C++ standard library
// through DynamixelWorkbench.
#ifdef min
#undef min
#endif

#ifdef max
#undef max
#endif

#include <DynamixelWorkbench.h>

DynamixelWorkbench dxl;

const uint32_t BAUD_RATES[] = {
  57600,
  1000000,
  115200,
  9600,
  2000000,
  3000000,
  4000000,
  4500000
};

bool initialized = false;

void discoverMotor()
{
  const char *log = nullptr;

  if (!initialized) {
    // OpenCR uses an empty device name.
    // Initialization enables the DYNAMIXEL power output.
    if (!dxl.init("", BAUD_RATES[0], &log)) {
      Serial.println("ERROR INIT");
      if (log != nullptr) {
        Serial.println(log);
      }
      return;
    }

    initialized = true;
  }

  Serial.println("SCAN START");
  Serial.println("Only one motor should be connected.");

  for (size_t i = 0;
       i < sizeof(BAUD_RATES) / sizeof(BAUD_RATES[0]);
       ++i) {
    const uint32_t baud = BAUD_RATES[i];

    log = nullptr;

    if (!dxl.setBaudrate(baud, &log)) {
      Serial.print("SKIP BAUD ");
      Serial.println(baud);
      if (log != nullptr) {
        Serial.println(log);
      }
      continue;
    }

    Serial.print("SCANNING BAUD ");
    Serial.println(baud);

    uint8_t ids[254] = {};
    uint8_t count = 0;

    // Workbench checks Protocol 1.0, then Protocol 2.0
    // if no device was found with Protocol 1.0.
    // Search IDs 0 through 253.
    const bool ok = dxl.scan(ids, &count, 253, &log);

    if (!ok) {
      Serial.println("SCAN ERROR");
      if (log != nullptr) {
        Serial.println(log);
      }
      continue;
    }

    if (count == 0) {
      Serial.println("NO RESPONSE");
      continue;
    }

    for (uint8_t index = 0; index < count; ++index) {
      const uint8_t id = ids[index];
      const char *model = dxl.getModelName(id);

      Serial.print("FOUND ID=");
      Serial.print(id);

      Serial.print(" BAUD=");
      Serial.print(baud);

      Serial.print(" PROTOCOL=");
      Serial.print(dxl.getProtocolVersion(), 1);

      Serial.print(" MODEL_NUMBER=");
      Serial.print(dxl.getModelNumber(id));

      Serial.print(" MODEL=");
      Serial.println(model != nullptr ? model : "UNKNOWN");
    }

    Serial.println("SCAN COMPLETE");
    Serial.println("No motor control registers were written.");
    return;
  }

  Serial.println("NOT FOUND AT TESTED BAUD RATES");
  Serial.println("Check power, cable, connector, and motor settings.");
}

void setup()
{
  Serial.begin(115200);
}

void loop()
{
  if (Serial.available() > 0) {
    const int input = Serial.read();

    if (input == 's' || input == 'S') {
      discoverMotor();
    }
  }
}
