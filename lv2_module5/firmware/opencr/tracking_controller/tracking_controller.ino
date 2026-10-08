#include <Arduino.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <errno.h>

extern "C" {
#include "usbd_cdc_interface.h"
}

// Parser-test settings. Not approved physical motor limits.
constexpr uint32_t TIMEOUT_MS = 300;
constexpr float MAX_VELOCITY = 0.10f;  // rad/s

bool armed = false;
float requested_velocity = 0.0f;
uint32_t last_command_ms = 0;

char line_buffer[64];
size_t line_length = 0;
bool discard_line = false;

// OpenCR-specific, best-effort diagnostic output.
// Drop the message if USB cannot accept it immediately.
// Call only from normal sketch code, not an interrupt handler.
void reply(const char *message)
{
  uint8_t packet[96];
  const size_t length = strlen(message);

  if (length >= sizeof(packet)) {
    return;
  }

  memcpy(packet, message, length);
  packet[length] = '\n';

  // One attempt; deliberately do not wait or retry.
  (void)CDC_Itf_Write(packet, (uint32_t)(length + 1));
}

void stopAndDisarm()
{
  requested_velocity = 0.0f;
  armed = false;

  // Parser-only test: no motor commands are sent.
  // Physical motor stopping must be implemented separately.
}

void checkWatchdog()
{
  const uint32_t now_ms = millis();

  // Unsigned subtraction handles millis() rollover.
  if (armed &&
      (uint32_t)(now_ms - last_command_ms) >= TIMEOUT_MS) {
    stopAndDisarm();
    reply("EVENT TIMEOUT DISARMED");
  }
}

void processCommand(const char *line)
{
  // Check expiry before accepting another command.
  checkWatchdog();

  if (strcmp(line, "DISARM") == 0) {
    stopAndDisarm();
    reply("ACK DISARM");
    return;
  }

  if (strcmp(line, "STOP") == 0) {
    requested_velocity = 0.0f;

    if (armed) {
      last_command_ms = millis();
    }

    reply("ACK STOP");
    return;
  }

  if (strcmp(line, "ARM") == 0) {
    requested_velocity = 0.0f;
    armed = true;
    last_command_ms = millis();

    reply("ACK ARM");
    return;
  }

  if (strcmp(line, "STATUS") == 0) {
    if (!armed) {
      reply("STATE DISARMED ZERO");
    } else if (requested_velocity == 0.0f) {
      reply("STATE ARMED ZERO");
    } else {
      reply("STATE ARMED NONZERO");
    }

    // STATUS deliberately does not refresh the watchdog.
    return;
  }

  if (strncmp(line, "VEL ", 4) == 0) {
    const char *start = line + 4;
    char *end = nullptr;

    errno = 0;
    const float value = strtof(start, &end);

    // Reject missing numbers, trailing characters,
    // conversion overflow/underflow, NaN, and infinity.
    if (end == start ||
        *end != '\0' ||
        errno == ERANGE ||
        !isfinite(value)) {
      reply("ERR VALUE");
      return;
    }

    if (fabsf(value) > MAX_VELOCITY) {
      reply("ERR RANGE");
      return;
    }

    if (!armed) {
      reply("ERR DISARMED");
      return;
    }

    requested_velocity = value;
    last_command_ms = millis();

    reply("ACK VEL");
    return;
  }

  // Rejected commands do not refresh the watchdog.
  reply("ERR COMMAND");
}

void setup()
{
  Serial.begin(115200);
  stopAndDisarm();

  // Do not wait for a serial monitor to connect.
  // This message may be dropped if USB is not ready.
  reply("READY DISARMED");
}

void loop()
{
  checkWatchdog();

  // Process at most 32 received bytes per loop.
  // Never wait for the rest of a command to arrive.
  for (int count = 0;
       count < 32 && Serial.available() > 0;
       ++count) {
    checkWatchdog();

    const int received = Serial.read();

    if (received < 0) {
      break;
    }

    const char c = (char)received;

    // Ignore CR so both LF and CRLF endings work.
    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      if (discard_line) {
        reply("ERR LINE");
      } else if (line_length > 0) {
        line_buffer[line_length] = '\0';
        processCommand(line_buffer);
      }

      line_length = 0;
      discard_line = false;
      continue;
    }

    if (discard_line) {
      continue;
    }

    // Reject nonprintable/non-ASCII input and oversized lines.
    // Discard everything through the next newline.
    if (received < 32 ||
        received > 126 ||
        line_length >= sizeof(line_buffer) - 1) {
      discard_line = true;
      continue;
    }

    line_buffer[line_length++] = c;
  }

  checkWatchdog();
}
