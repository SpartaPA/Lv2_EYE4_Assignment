#include <Arduino.h>

#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif

#include <DynamixelWorkbench.h>

DynamixelWorkbench dxl;
bool busReady = false;

const uint32_t USB_BAUD = 115200;
const uint32_t DXL_BAUD = 1000000;

const char *const fields[] = {
  "Operating_Mode",
  "Drive_Mode",
  "Torque_Enable",
  "Homing_Offset",
  "Min_Position_Limit",
  "Max_Position_Limit",
  "Velocity_Limit",
  "Present_Position",
  "Present_Velocity",
  "Present_Input_Voltage",
  "Present_Temperature",
  "Hardware_Error_Status"
};

void inspectMotor(uint8_t id, const char *axis)
{
  const char *log = nullptr;
  uint16_t model = 0;

  Serial.print("MOTOR AXIS=");
  Serial.print(axis);
  Serial.print(" ID=");
  Serial.println(id);

  if (!dxl.ping(id, &model, &log)) {
    Serial.print("PING_ERROR ");
    Serial.println(log ? log : "No details");
    return;
  }

  Serial.print("MODEL_NUMBER=");
  Serial.println(model);
  Serial.print("PROTOCOL=");
  Serial.println(dxl.getProtocolVersion(), 1);

  if (model != 1020 || dxl.getProtocolVersion() != 2.0f) {
    Serial.println("UNEXPECTED_MODEL_OR_PROTOCOL: skipping reads");
    return;
  }

  bool allRead = true;

  for (size_t i = 0; i < sizeof(fields) / sizeof(fields[0]); ++i) {
    int32_t value = 0;
    log = nullptr;

    Serial.print(fields[i]);
    Serial.print("=");

    if (dxl.itemRead(id, fields[i], &value, &log)) {
      Serial.println(value);
    } else {
      allRead = false;
      Serial.print("READ_ERROR ");
      Serial.println(log ? log : "No details");
    }
  }

  Serial.println(allRead ? "READS_COMPLETE" : "READS_INCOMPLETE");
}

void inspectAll()
{
  Serial.println("INSPECT START");

  if (!busReady) {
    const char *log = nullptr;

    if (!dxl.init("", DXL_BAUD, &log)) {
      Serial.print("INIT_ERROR ");
      Serial.println(log ? log : "No details");
      return;
    }

    busReady = true;
  }

  inspectMotor(11, "PAN");
  inspectMotor(12, "TILT");

  Serial.println("INSPECT COMPLETE");
  Serial.println("No motor control registers were written.");
}

void setup()
{
  Serial.begin(USB_BAUD);
}

void loop()
{
  if (Serial.available() > 0) {
    const char command = Serial.read();

    if (command == 'r' || command == 'R') {
      inspectAll();
    }
  }
}
