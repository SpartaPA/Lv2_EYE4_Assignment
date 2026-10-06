// Tilt jog commissioning; derived from tested tilt_hold_test.
// STOP/DISARM retain torque. Support before SUPPORTED_OFF.

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
  ARMED,
  JOGGING,
  STOPPING,
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

const uint32_t JOG_MS = 200;
const uint32_t ARM_IDLE_MS = 10000;
const int32_t JOG_SPEED = 2;
const int32_t STOP_COUNTS = 80;

uint32_t jogStarted = 0;
uint32_t armStarted = 0;
uint32_t stopStarted = 0;
uint8_t quietSamples = 0;
int32_t holdAnchor = 0;

void beginStop(const char *reason);

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
  return state == HOLDING || state == ARMED ||
         state == JOGGING || state == STOPPING || state == DONE;
}

const char *stateName()
{
  switch (state) {
    case BOOT: return "BOOT";
    case READY: return "READY";
    case HOLDING: return "HOLDING";
    case ARMED: return "ARMED";
    case JOGGING: return "JOGGING";
    case STOPPING: return "STOPPING";
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

    if (displacement > 100 || displacement < -100) {
      fail("OUTER_BOUND_100_COUNTS");
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


  if (active() && baselineValid) {
    // Detect excessive drift while supposedly holding still.
    const int64_t holdDrift =
        (int64_t)position - (int64_t)holdAnchor;

    if ((state == HOLDING || state == ARMED || state == DONE) &&
        (holdDrift > 20 || holdDrift < -20)) {
      fail("HOLD_DRIFT_OVER_20_COUNTS");
      return false;
    }

    if ((state == ARMED || state == JOGGING) &&
        (drift <= -STOP_COUNTS || drift >= STOP_COUNTS)) {
      beginStop("EVENT POSITION_LIMIT");
      if (state == FAULT) return false;
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

  holdAnchor = position;
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


void beginStop(const char *reason)
{
  if (!active() || state == STOPPING) return;

  state = STOPPING;
  stopStarted = millis();
  quietSamples = 0;

  if (!writeVerified("Goal_Velocity", 0)) {
    fail("ZERO_COMMAND");
    return;
  }

  reply(reason);
}

void armJog()
{
  if (state != HOLDING && state != DONE) {
    reply("ERR HOLD_FIRST");
    return;
  }

  if (!sample()) return;

  if (velocity != 0 ||
      drift <= -(STOP_COUNTS - 10) ||
      drift >= (STOP_COUNTS - 10)) {
    reply("ERR NOT_STATIONARY_OR_TOO_CLOSE_TO_LIMIT");
    return;
  }

  if (!equalsItem(TILT, "Goal_Velocity", 0)) {
    fail("NONZERO_GOAL_BEFORE_ARM");
    return;
  }

  state = ARMED;
  armStarted = millis();
  reply("ACK ARM; ONE_JOG_READY");
}

void startJog(int32_t direction)
{
  if (state != ARMED) {
    reply("ERR ARM_REQUIRED");
    return;
  }

  if (!sample() || state != ARMED) return;

  if (velocity != 0 ||
      drift <= -(STOP_COUNTS - 10) ||
      drift >= (STOP_COUNTS - 10)) {
    beginStop("EVENT JOG_START_REJECTED");
    return;
  }

  jogStarted = millis();
  state = JOGGING;

  if (!writeVerified("Goal_Velocity", direction * JOG_SPEED)) {
    fail("JOG_WRITE");
    return;
  }

  reply(direction > 0 ? "ACK JOG +" : "ACK JOG -");
}

void service()
{
  if (!active()) return;

  uint32_t now = millis();

  if (state == JOGGING && now - jogStarted >= JOG_MS) {
    beginStop("EVENT JOG_TIMEOUT");
  }

  if (state == ARMED && now - armStarted >= ARM_IDLE_MS) {
    beginStop("EVENT ARM_IDLE_TIMEOUT");
  }

  if (!active()) return;

  now = millis();
  if (now - lastPoll < POLL_MS) return;
  lastPoll = now;

  if (!sample()) return;

  // Include bus transaction time in the jog deadline.
  if (state == JOGGING && millis() - jogStarted >= JOG_MS) {
    beginStop("EVENT JOG_TIMEOUT");
  }

  if (state == STOPPING) {
    if (velocity == 0) {
      if (quietSamples < 3) ++quietSamples;
    } else {
      quietSamples = 0;
    }

    if (millis() - stopStarted >= 100 && quietSamples >= 3) {
      holdAnchor = position;
      state = HOLDING;
      reply("EVENT STOPPED HOLDING; TORQUE_REMAINS_ON");
      report();
    } else if (millis() - stopStarted >= 500) {
      fail("STOP_NOT_CONFIRMED");
      return;
    }
  }

  if (!active()) return;

  now = millis();
  if (now - lastReport >= 1000) {
    lastReport = now;
    report();
  }
}


void command(const char *text)
{
  if (strcmp(text, "STATUS") == 0) {
    if (state == READY && !sample()) return;
    report();
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
  } else if (strcmp(text, "ARM") == 0) {
    armJog();
  } else if (strcmp(text, "JOG +") == 0) {
    startJog(1);
  } else if (strcmp(text, "JOG -") == 0) {
    startJog(-1);
  } else if (strcmp(text, "STOP") == 0 ||
             strcmp(text, "DISARM") == 0) {
    if (active()) {
      beginStop("ACK STOP_REQUEST");
    } else {
      reply("ACK NO_ACTIVE_MOTION");
    }
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
