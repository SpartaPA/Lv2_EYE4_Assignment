#include <Arduino.h>

#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif

#include <DynamixelWorkbench.h>
#include <stdio.h>
#include <string.h>

extern "C" {
#include "usbd_cdc_interface.h"
}

DynamixelWorkbench dxl;

const uint8_t PAN = 11;
const uint8_t TILT = 12;
const int32_t WATCHDOG = 10;  // 200 ms
const uint32_t POLL_MS = 20;
const uint32_t TEST_MS = 10000;

enum State {
  BOOT,
  READY,
  HOLDING,
  TESTING,
  DONE,
  FAULT,
  OFF
};

State state = BOOT;
bool tiltKnown = false;
bool baselineValid = false;

int32_t position = 0;
int32_t velocity = 0;
int32_t currentRaw = 0;
int32_t temperature = 0;
int32_t torque = 0;

int32_t startPosition = 0;
int32_t previousPosition = 0;
int32_t drift = 0;
int32_t peakDrift = 0;

uint32_t lastPoll = 0;
uint32_t lastReport = 0;
uint32_t testStarted = 0;
uint32_t sampleTime = 0;

char input[48];
size_t used = 0;
bool invalidLine = false;

void reply(const char *text)
{
  uint8_t packet[192];
  size_t n = strlen(text);
  if (n > sizeof(packet) - 2) n = sizeof(packet) - 2;
  memcpy(packet, text, n);
  packet[n++] = '\r';
  packet[n++] = '\n';
  (void)CDC_Itf_Write(packet, n);
}

bool readItem(uint8_t id, const char *name, int32_t &value)
{
  const char *log = nullptr;
  return dxl.itemRead(id, name, &value, &log);
}

bool equalsItem(uint8_t id, const char *name, int32_t expected)
{
  int32_t value = 0;
  return readItem(id, name, value) && value == expected;
}

// All writes in this sketch target TILT only.
bool writeTilt(const char *name, int32_t value)
{
  const char *log = nullptr;
  return dxl.itemWrite(TILT, name, value, &log);
}

bool writeVerified(const char *name, int32_t value)
{
  return writeTilt(name, value) && equalsItem(TILT, name, value);
}

bool active()
{
  return state == HOLDING || state == TESTING || state == DONE;
}

const char *stateName()
{
  switch (state) {
    case BOOT: return "BOOT";
    case READY: return "READY";
    case HOLDING: return "HOLDING";
    case TESTING: return "TESTING";
    case DONE: return "DONE";
    case OFF: return "OFF";
    default: return "FAULT";
  }
}

// No automatic torque-off: the camera is gravity-loaded.
// After a fault, cease periodic bus traffic so the motor watchdog
// can expire if needed. Physical support remains essential.
void fail(const char *reason)
{
  state = FAULT;

  if (tiltKnown) {
    (void)writeTilt("Goal_Velocity", 0);
  }

  char text[180];
  snprintf(text, sizeof(text),
           "FAULT %s; SUPPORT_CAMERA; TORQUE_STATE_NOT_GUARANTEED",
           reason);
  reply(text);
}

bool identify(uint8_t id)
{
  const char *log = nullptr;
  uint16_t model = 0;
  return dxl.ping(id, &model, &log) &&
         model == 1020 &&
         dxl.getProtocolVersion() == 2.0f;
}

// Use modulo ONLY to recognize the manually verified neutral pose.
// During torque-on operation, monitor continuous raw positions.
// This is not a general multi-turn homing solution.
int32_t neutralOffset(int32_t raw)
{
  int32_t p = raw % 4096;
  if (p < 0) p += 4096;
  if (p >= 2048) p -= 4096;
  return p;
}

bool sample()
{
  int32_t error = 0;
  int32_t currentValue = 0;

  if (!readItem(TILT, "Present_Position", position) ||
      !readItem(TILT, "Present_Velocity", velocity) ||
      !readItem(TILT, "Present_Current", currentValue) ||
      !readItem(TILT, "Present_Temperature", temperature) ||
      !readItem(TILT, "Torque_Enable", torque) ||
      !readItem(TILT, "Hardware_Error_Status", error)) {
    fail("READ");
    return false;
  }

  // Present Current is a signed 16-bit register.
  currentRaw = (int16_t)(uint16_t)currentValue;
  sampleTime = millis();

  if (error != 0) {
    fail("HARDWARE_ERROR");
    return false;
  }

  if (active() && baselineValid) {
    const int64_t step =
        (int64_t)position - (int64_t)previousPosition;
    const int64_t displacement =
        (int64_t)position - (int64_t)startPosition;

    // Do not silently accept a reboot/reset as encoder wrapping.
    if (step > 20 || step < -20) {
      fail("POSITION_JUMP");
      return false;
    }

    if (displacement > 20 || displacement < -20) {
      fail("DRIFT_OVER_20_COUNTS");
      return false;
    }

    drift = (int32_t)displacement;
    const int32_t magnitude = drift < 0 ? -drift : drift;
    if (magnitude > peakDrift) peakDrift = magnitude;

    if (velocity > 5 || velocity < -5) {
      fail("UNEXPECTED_SPEED");
      return false;
    }

    if (torque != 1 ||
        !equalsItem(TILT, "Bus_Watchdog", WATCHDOG) ||
        !equalsItem(PAN, "Torque_Enable", 0)) {
      fail("TORQUE_OR_WATCHDOG");
      return false;
    }
  }

  previousPosition = position;
  return true;
}

void report()
{
  char text[190];
  snprintf(text, sizeof(text),
           "STATE %s POS=%ld DRIFT=%ld PEAK=%ld VEL=%ld "
           "I_RAW=%ld TEMP=%ld TORQUE=%ld AGE_MS=%lu",
           stateName(), (long)position, (long)drift,
           (long)peakDrift, (long)velocity, (long)currentRaw,
           (long)temperature, (long)torque,
           (unsigned long)(millis() - sampleTime));
  reply(text);
}

void checkHardware()
{
  if (state != BOOT) {
    reply("ERR CHECK_ONLY_AT_BOOT");
    return;
  }

  const char *log = nullptr;
  if (!dxl.init("", 1000000, &log)) {
    fail("INIT");
    return;
  }

  if (!identify(TILT)) {
    fail("TILT_ID_MODEL_PROTOCOL");
    return;
  }
  tiltKnown = true;

  if (!identify(PAN)) {
    fail("PAN_ID_MODEL_PROTOCOL");
    return;
  }

  int32_t firmware = 0;
  if (!readItem(TILT, "Firmware_Version", firmware) ||
      firmware < 38) {
    fail("TILT_FIRMWARE_REQUIRES_38_OR_LATER");
    return;
  }

  if (!equalsItem(PAN, "Torque_Enable", 0) ||
      !equalsItem(TILT, "Torque_Enable", 0) ||
      !equalsItem(TILT, "Operating_Mode", 1) ||
      !equalsItem(TILT, "Drive_Mode", 0) ||
      !equalsItem(TILT, "Homing_Offset", 0) ||
      !equalsItem(TILT, "Status_Return_Level", 2) ||
      !equalsItem(TILT, "Bus_Watchdog", 0)) {
    fail("PRECHECK_SETTINGS");
    return;
  }

  if (!sample()) return;

  const int32_t offset = neutralOffset(position);
  if (offset < -20 || offset > 20 || velocity != 0) {
    fail("SUPPORT_AT_NEUTRAL_FIRST");
    return;
  }

  if (!writeVerified("Goal_Velocity", 0) ||
      !writeVerified("Profile_Acceleration", 1)) {
    fail("CONFIGURE");
    return;
  }

  state = READY;
  reply("CHECK_OK READY; BOTH_TORQUES_OFF");
  report();
}

void beginHold()
{
  if (state != READY) {
    reply("ERR NOT_READY");
    return;
  }

  if (!sample()) return;

  const int32_t offset = neutralOffset(position);
  if (offset < -20 || offset > 20 || velocity != 0 ||
      torque != 0 || !equalsItem(PAN, "Torque_Enable", 0)) {
    fail("HOLD_PRECHECK");
    return;
  }

  startPosition = position;
  previousPosition = position;
  drift = 0;
  peakDrift = 0;
  baselineValid = true;

  if (!writeVerified("Goal_Velocity", 0) ||
      !writeVerified("Bus_Watchdog", WATCHDOG) ||
      !writeVerified("Torque_Enable", 1)) {
    fail("HOLD_WRITE");
    return;
  }

  state = HOLDING;
  lastPoll = millis();
  lastReport = millis();

  reply("ACK HOLD; ZERO_VELOCITY; TORQUE_ON");
}

void supportedOff()
{
  if (!tiltKnown || state == BOOT) {
    reply("ERR NOT_INITIALIZED");
    return;
  }

  // User must physically support the camera BEFORE this command.
  // Torque-off remains writable even after a bus watchdog error.
  const bool offConfirmed = writeVerified("Torque_Enable", 0);

  if (!offConfirmed) {
    fail("TORQUE_OFF_NOT_CONFIRMED");
    return;
  }

  if (!writeVerified("Bus_Watchdog", 0) ||
      !writeVerified("Goal_Velocity", 0)) {
    state = FAULT;
    reply("FAULT CLEANUP; TORQUE_OFF_CONFIRMED; POWER_OFF");
    return;
  }

  torque = 0;
  state = OFF;
  reply("ACK SUPPORTED_OFF; TORQUE_OFF_CONFIRMED");
}

void service()
{
  if (!active()) return;

  uint32_t now = millis();
  if (now - lastPoll < POLL_MS) return;
  lastPoll = now;

  if (!sample()) return;

  now = millis();
  if (state == TESTING && now - testStarted >= TEST_MS) {
    state = DONE;
    reply("EVENT OBSERVATION_COMPLETE; TORQUE_REMAINS_ON");
    report();
  }

  if (now - lastReport >= 1000) {
    lastReport = now;
    report();
  }
}

void command(const char *text)
{
  if (strcmp(text, "STATUS") == 0) {
    if (state == READY && !sample()) return;
    report();  // Cached feedback while active or faulted.
    return;
  }

  if (strcmp(text, "SUPPORTED_OFF") == 0) {
    supportedOff();
    return;
  }

  if (state == FAULT || state == OFF) {
    reply("ERR SESSION_FINISHED");
    return;
  }

  if (strcmp(text, "CHECK") == 0) {
    checkHardware();
  } else if (strcmp(text, "HOLD") == 0) {
    beginHold();
  } else if (strcmp(text, "TEST") == 0) {
    if (state != HOLDING) {
      reply("ERR HOLD_FIRST");
      return;
    }
    testStarted = millis();
    state = TESTING;
    reply("ACK TEST; OBSERVE_10_SECONDS");
  } else if (strcmp(text, "STOP") == 0 ||
             strcmp(text, "DISARM") == 0) {
    if (!active()) {
      reply("ACK NO_ACTIVE_HOLD");
      return;
    }
    if (!writeVerified("Goal_Velocity", 0)) {
      fail("ZERO_WRITE");
      return;
    }
    state = HOLDING;
    reply("ACK ZERO_VELOCITY; TORQUE_REMAINS_ON");
  } else {
    reply("ERR COMMAND");
  }
}

void setup()
{
  Serial.begin(115200);
}

void loop()
{
  service();

  for (uint8_t i = 0; i < 16 && Serial.available() > 0; ++i) {
    service();
    const char c = (char)Serial.read();

    if (c == '\r' || c == '\n') {
      if (invalidLine) {
        reply("ERR LINE");
      } else if (used > 0) {
        input[used] = '\0';
        command(input);
      }
      used = 0;
      invalidLine = false;
    } else if (!invalidLine) {
      if (c < 32 || c > 126 || used >= sizeof(input) - 1) {
        invalidLine = true;
      } else {
        input[used++] = c;
      }
    }
  }
}
