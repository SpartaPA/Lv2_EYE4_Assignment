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

const uint32_t USB_BAUD = 115200;
const uint32_t DXL_BAUD = 1000000;

// Session-independent pan reference for this small test window.
// Do not reuse this approach for tilt, which crosses the turn boundary.
const int32_t CENTER = 3078;
const int32_t HARD_LOW = 2978;
const int32_t HARD_HIGH = 3178;

// Stop inside the proposed outer test bounds.
const int32_t STOP_LOW = 2998;
const int32_t STOP_HIGH = 3158;

const int32_t JOG_SPEED = 2;       // Raw units: approx. 0.048 rad/s
const int32_t BUS_WATCHDOG = 10;   // 10 * 20 ms = 200 ms
const uint32_t JOG_MS = 200;
const uint32_t ARM_IDLE_MS = 10000;
const uint32_t POLL_MS = 20;
const uint32_t STOP_VERIFY_MS = 500;

enum State {
  BOOT,
  DISARMED,
  ARMED,
  JOGGING,
  STOPPING,
  FAULT
};

State state = BOOT;
bool panKnown = false;

int32_t position = 0;
int32_t velocity = 0;
int32_t previousPosition = 0;
bool havePosition = false;

uint32_t lastPoll = 0;
uint32_t sampleTime = 0;
uint32_t armTime = 0;
uint32_t jogTime = 0;
uint32_t stopTime = 0;
uint8_t quietSamples = 0;

char line[48];
size_t used = 0;
bool overflowed = false;

// One non-blocking USB transmission attempt.
// A busy/disconnected USB host must not delay motor servicing.
void reply(const char *message)
{
  uint8_t packet[160];
  size_t n = strlen(message);
  if (n > sizeof(packet) - 2) n = sizeof(packet) - 2;

  memcpy(packet, message, n);
  packet[n++] = '\r';
  packet[n++] = '\n';

  (void)CDC_Itf_Write(packet, n);
}

bool readItem(uint8_t id, const char *name, int32_t &value)
{
  const char *log = nullptr;
  return dxl.itemRead(id, name, &value, &log);
}

bool writePan(const char *name, int32_t value)
{
  const char *log = nullptr;
  return dxl.itemWrite(PAN, name, value, &log);
}

bool equalsItem(uint8_t id, const char *name, int32_t expected)
{
  int32_t value = 0;
  return readItem(id, name, value) && value == expected;
}

bool writeVerified(const char *name, int32_t value)
{
  return writePan(name, value) && equalsItem(PAN, name, value);
}

const char *stateName()
{
  switch (state) {
    case BOOT: return "BOOT";
    case DISARMED: return "DISARMED";
    case ARMED: return "ARMED";
    case JOGGING: return "JOGGING";
    case STOPPING: return "STOPPING";
    default: return "FAULT";
  }
}

// Latched fault: try stopping pan, then cease all bus traffic.
// If communication is lost, an enabled motor watchdog can expire.
// No automatic fault recovery or watchdog-error clearing here.
void fail(const char *reason)
{
  state = FAULT;

  if (panKnown) {
    (void)writePan("Goal_Velocity", 0);
    (void)writePan("Torque_Enable", 0);
  }

  char message[150];
  snprintf(message, sizeof(message), "FAULT %s; POWER_OFF_AND_INSPECT",
           reason);
  reply(message);
}

bool samplePan()
{
  int32_t p = 0;
  int32_t v = 0;
  int32_t error = 0;

  if (!readItem(PAN, "Present_Position", p) ||
      !readItem(PAN, "Present_Velocity", v) ||
      !readItem(PAN, "Hardware_Error_Status", error)) {
    fail("READ");
    return false;
  }

  if (error != 0) {
    fail("HARDWARE_ERROR");
    return false;
  }

  if (p <= HARD_LOW || p >= HARD_HIGH) {
    fail("OUTER_BOUND");
    return false;
  }

  // Much larger than expected movement between samples at this speed.
  if (havePosition &&
      (p - previousPosition > 20 || p - previousPosition < -20)) {
    fail("POSITION_JUMP");
    return false;
  }

  if (v > 5 || v < -5) {
    fail("UNEXPECTED_SPEED");
    return false;
  }

  position = p;
  velocity = v;
  previousPosition = p;
  havePosition = true;
  sampleTime = millis();
  return true;
}

bool identify(uint8_t id)
{
  const char *log = nullptr;
  uint16_t model = 0;

  return dxl.ping(id, &model, &log) &&
         model == 1020 &&
         dxl.getProtocolVersion() == 2.0f;
}

void checkHardware()
{
  if (state != BOOT) {
    reply("ERR CHECK_ONLY_AT_BOOT");
    return;
  }

  const char *log = nullptr;
  if (!dxl.init("", DXL_BAUD, &log)) {
    fail("INIT");
    return;
  }

  if (!identify(PAN)) {
    fail("PAN_ID_MODEL_PROTOCOL");
    return;
  }
  panKnown = true;

  if (!identify(TILT)) {
    fail("TILT_ID_MODEL_PROTOCOL");
    return;
  }

  int32_t firmware = 0;
  if (!readItem(PAN, "Firmware_Version", firmware) || firmware < 38) {
    fail("PAN_FIRMWARE_REQUIRES_38_OR_LATER");
    return;
  }

  if (!equalsItem(PAN, "Torque_Enable", 0) ||
      !equalsItem(TILT, "Torque_Enable", 0) ||
      !equalsItem(TILT, "Hardware_Error_Status", 0) ||
      !equalsItem(PAN, "Operating_Mode", 1) ||
      !equalsItem(PAN, "Drive_Mode", 0) ||
      !equalsItem(PAN, "Homing_Offset", 0) ||
      !equalsItem(PAN, "Status_Return_Level", 2) ||
      !equalsItem(PAN, "Bus_Watchdog", 0)) {
    fail("PRECHECK_SETTINGS");
    return;
  }

  havePosition = false;
  if (!samplePan()) return;

  if (position < CENTER - 20 || position > CENTER + 20 ||
      velocity != 0) {
    fail("START_NEAR_3078_AND_STATIONARY");
    return;
  }

  // RAM writes only; no EEPROM mode, ID, baud or limit changes.
  if (!writeVerified("Goal_Velocity", 0) ||
      !writeVerified("Profile_Acceleration", 1)) {
    fail("CONFIGURE");
    return;
  }

  state = DISARMED;
  reply("CHECK_OK DISARMED; TILT_TORQUE_OFF");
}

void beginStop(const char *reason)
{
  if (state != ARMED && state != JOGGING) return;

  state = STOPPING;
  stopTime = millis();
  quietSamples = 0;

  if (!writeVerified("Goal_Velocity", 0)) {
    fail("ZERO_COMMAND");
    return;
  }

  reply(reason);
}

void armPan()
{
  if (state != DISARMED) {
    reply("ERR NOT_DISARMED");
    return;
  }

  // Manual movement while disarmed is allowed; take a new baseline.
  havePosition = false;
  if (!samplePan()) return;

  if (position <= STOP_LOW || position >= STOP_HIGH ||
      velocity != 0) {
    reply("ERR ARM_POSITION_OR_VELOCITY");
    return;
  }

  if (!equalsItem(PAN, "Torque_Enable", 0) ||
      !equalsItem(TILT, "Torque_Enable", 0) ||
      !equalsItem(PAN, "Operating_Mode", 1) ||
      !equalsItem(PAN, "Drive_Mode", 0) ||
      !equalsItem(PAN, "Bus_Watchdog", 0)) {
    fail("ARM_PRECHECK");
    return;
  }

  // Clear the goal BEFORE enabling torque.
  if (!writeVerified("Goal_Velocity", 0) ||
      !writeVerified("Bus_Watchdog", BUS_WATCHDOG) ||
      !writeVerified("Torque_Enable", 1)) {
    fail("ARM_WRITE");
    return;
  }

  state = ARMED;
  armTime = millis();
  lastPoll = millis();
  reply("ACK ARM; ONE_JOG_READY");
}

void startJog(int32_t direction)
{
  if (state != ARMED) {
    reply("ERR ARM_REQUIRED");
    return;
  }

  if (!samplePan()) return;

  // Leave additional starting margin to the stop thresholds.
  if (position <= STOP_LOW + 10 || position >= STOP_HIGH - 10) {
    beginStop("EVENT START_TOO_CLOSE_TO_LIMIT");
    return;
  }

  // Start timing before the write, so write latency counts.
  jogTime = millis();
  state = JOGGING;

  if (!writeVerified("Goal_Velocity", direction * JOG_SPEED)) {
    fail("JOG_WRITE");
    return;
  }

  reply(direction > 0 ? "ACK JOG +" : "ACK JOG -");
}

void serviceMotion()
{
  uint32_t now = millis();

  if (state == JOGGING && now - jogTime >= JOG_MS) {
    beginStop("EVENT JOG_TIMEOUT");
  }

  if (state == ARMED && now - armTime >= ARM_IDLE_MS) {
    beginStop("EVENT ARM_IDLE_TIMEOUT");
  }

  if (state != ARMED && state != JOGGING && state != STOPPING) return;

  now = millis();
  if (now - lastPoll < POLL_MS) return;
  lastPoll = now;

  if (!samplePan()) return;

  if (!equalsItem(PAN, "Torque_Enable", 1) ||
      !equalsItem(PAN, "Bus_Watchdog", BUS_WATCHDOG)) {
    fail("TORQUE_OR_BUS_WATCHDOG");
    return;
  }

  if ((state == ARMED || state == JOGGING) &&
      (position <= STOP_LOW || position >= STOP_HIGH)) {
    beginStop("EVENT POSITION_LIMIT");
  }

  // Recheck the deadline after potentially blocking bus transactions.
  if (state == JOGGING && millis() - jogTime >= JOG_MS) {
    beginStop("EVENT JOG_TIMEOUT");
  }

  if (state != STOPPING) return;

  if (velocity == 0) {
    if (quietSamples < 3) ++quietSamples;
  } else {
    quietSamples = 0;
  }

  if (millis() - stopTime >= 100 && quietSamples >= 3) {
    if (!writeVerified("Torque_Enable", 0) ||
        !writeVerified("Bus_Watchdog", 0)) {
      fail("DISARM_WRITE");
      return;
    }

    state = DISARMED;
    reply("EVENT STOPPED DISARMED");
    return;
  }

  if (millis() - stopTime >= STOP_VERIFY_MS) {
    fail("STOP_NOT_CONFIRMED");
  }
}

void status()
{
  if (state == DISARMED) {
    havePosition = false;
    if (!samplePan()) return;
  }

  char message[150];
  snprintf(message, sizeof(message),
           "STATE %s POS=%ld VEL=%ld SAMPLE_AGE_MS=%lu",
           stateName(), (long)position, (long)velocity,
           (unsigned long)(millis() - sampleTime));
  reply(message);
}

void handleCommand(const char *command)
{
  if (strcmp(command, "STATUS") == 0) {
    status();
    return;
  }

  if (state == FAULT) {
    reply("ERR FAULT_LATCHED; POWER_OFF_AND_INSPECT");
    return;
  }

  if (strcmp(command, "CHECK") == 0) {
    checkHardware();
  } else if (strcmp(command, "ARM") == 0) {
    armPan();
  } else if (strcmp(command, "JOG +") == 0) {
    startJog(1);
  } else if (strcmp(command, "JOG -") == 0) {
    startJog(-1);
  } else if (strcmp(command, "STOP") == 0 ||
             strcmp(command, "DISARM") == 0) {
    if (state == ARMED || state == JOGGING) {
      beginStop("ACK STOP_REQUEST");
    } else {
      reply("ACK NO_NEW_MOTION");
    }
  } else {
    reply("ERR COMMAND");
  }
}

void setup()
{
  Serial.begin(USB_BAUD);
  // No motor initialization or torque enabling until CHECK.
}

void loop()
{
  serviceMotion();

  // Bounded input processing: serial floods cannot monopolize the loop.
  for (uint8_t i = 0; i < 16 && Serial.available() > 0; ++i) {
    serviceMotion();

    char c = (char)Serial.read();

    if (c == '\r' || c == '\n') {
      if (overflowed) {
        reply("ERR LINE");
      } else if (used > 0) {
        line[used] = '\0';
        handleCommand(line);
      }

      used = 0;
      overflowed = false;
    } else if (!overflowed) {
      // Reject embedded control characters and oversized commands.
      if (c < 32 || c > 126 || used >= sizeof(line) - 1) {
        overflowed = true;
      } else {
        line[used++] = c;
      }
    }
  }
}
