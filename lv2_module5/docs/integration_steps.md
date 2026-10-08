# Two-axis integration: staged bench procedure

This candidate is derived from the uploaded archive at checkpoint 3494464.
Keep all baseline and commissioning sketches. Do not run legacy test_parser.py
on this controller. Do not connect the ROS bridge yet.

## 1. Install the reviewed bundle

Transfer control_integration_v1.tar.gz to the Pi, then:

```bash
mkdir -p "$HOME/pa-opencr-build/integration_v1"
tar --no-same-owner -xzf "$HOME/control_integration_v1.tar.gz" \
  -C "$HOME/pa-opencr-build/integration_v1"
python3 "$HOME/pa-opencr-build/integration_v1/install.py" \
  "$HOME/git/Lv2_EYE4_Assignment"
cd "$HOME/git/Lv2_EYE4_Assignment"
git diff --stat
git status --short
```

The installer refuses to overwrite changed source documents or existing differing
new files. It installs only the bundle's listed files, not your evidence logs.
The old single-axis parser and commissioning sketches remain untouched.

## 2. Build DRY first

Camera supported; motor power off. Close miniterm/opencr_node/other serial owners.

```bash
REPO_ROOT="$HOME/git/Lv2_EYE4_Assignment"
BUILD_DIR="$HOME/pa-opencr-build/build/tracking_controller_2axis_dry"
LOG_DIR="$REPO_ROOT/lv2_module5/results/logs/opencr/integration_dry_$(date +%Y%m%d_%H%M%S)"
OPENCR_PORT="/dev/serial/by-id/usb-ROBOTIS_OpenCR_Virtual_ComPort_in_FS_Mode_FFFFFFFEFFFF-if00"
mkdir -p "$BUILD_DIR" "$LOG_DIR"
set -o pipefail
arduino-cli compile --clean --fqbn OpenCR:OpenCR:OpenCR \
  --build-path "$BUILD_DIR" \
  "$REPO_ROOT/lv2_module5/firmware/opencr/tracking_controller_2axis" \
  2>&1 | tee "$LOG_DIR/build.log"
```

Only after success:

```bash
opencr_ld "$OPENCR_PORT" 115200 \
  "$BUILD_DIR/tracking_controller_2axis.ino.bin" 1 \
  2>&1 | tee "$LOG_DIR/upload.log"
```

After successful upload, reset OpenCR (motor power remains off) and run:

```bash
python3 -u "$REPO_ROOT/lv2_module5/firmware/opencr/tests/test_2axis_dry.py" \
  --port "$OPENCR_PORT" 2>&1 | tee "$LOG_DIR/parser_2axis.log"
```

Expected: ALL TWO-AXIS DRY CHECKS PASSED. The script refuses MODE=LIVE.
Keep the entire failure output if anything fails. Do not enable motor output yet.

## 3. LIVE candidate, only after board DRY checks pass

Support the camera, retain the close catch, position both axes near the measured
neutral pose. Firmware startup tolerances are pan 3078±20 and tilt 0 modulo4096±20.
Power/reset may release torque; support throughout. Do not change DYNAMIXEL modes.
Use a new build/log directory; do not reuse a DRY binary filename blindly.

```bash
BUILD_DIR="$HOME/pa-opencr-build/build/tracking_controller_2axis_live"
LOG_DIR="$REPO_ROOT/lv2_module5/results/logs/opencr/integration_live_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BUILD_DIR" "$LOG_DIR"
arduino-cli compile --clean --fqbn OpenCR:OpenCR:OpenCR \
  --build-property 'compiler.cpp.extra_flags=-DENABLE_MOTOR_OUTPUT=1' \
  --build-path "$BUILD_DIR" \
  "$REPO_ROOT/lv2_module5/firmware/opencr/tracking_controller_2axis" \
  2>&1 | tee "$LOG_DIR/build.log"
```

Only after successful compile, upload as above using this BUILD_DIR. If the local
platform does not consume compiler.cpp.extra_flags, STATUS will still say DRY:
stop and inspect the verbose build rather than assuming live mode.

Open miniterm (log with a fresh name). Send STATUS: verify MODE=LIVE. Then CHECK,
HOLD. Wait for EVENT STOPPED TORQUE_RETAINED. STATUS must say DISARMED,
GOAL=0,0, VEL=0,0, TORQUE=1,1. Gradually transfer the camera load while keeping
catch clear but close. Check no sag/oscillation. Close miniterm with Ctrl+].
Torque remains ON while the port is closed; do not leave the rig unattended.

## 4. Single commands, zero before motion

Run one case at a time; review the actual movement/stop before the next.
The script starts only from LIVE DISARMED holding state. It explicitly ARMs,
sends ONE VEL, then sends nothing for 1 second to exercise command timeout.
Each nonzero component is only ±0.024 rad/s (one motor raw unit).

```bash
python3 -u "$REPO_ROOT/lv2_module5/firmware/opencr/tests/bench_2axis_once.py" \
  --port "$OPENCR_PORT" --execute-live --case zero \
  2>&1 | tee "$LOG_DIR/zero.log"
```

Following successful zero test, replace the case and log name in order:

| Case | Expected physical direction |
|---|---|
| pan-left | pan left, tilt holds |
| pan-right | pan right, tilt holds |
| tilt-up | tilt up, pan holds |
| tilt-down | tilt down, pan holds |
| both | pan right + tilt down |

Directions are from behind the camera looking forward. Stop if a direction is
wrong, if either axis sags/oscillates, or on any FAULT. Software PASS is only
reported feedback, not proof of the physical result. ACK/event messages can drop.

After each session, support the camera and reconnect miniterm. Send
SUPPORTED_OFF and require TORQUE_OFF_CONFIRMED before leaving it. Next session
requires reset and CHECK/HOLD again. Never automatically re-arm after a fault.

## 5. Remaining gates

No full camera tracking yet. Separate procedures are needed for position-limit
stopping, stopping latency, DYNAMIXEL communication loss, board stall, feedback
failure, and source-command freshness through the ROS bridge. Do not hot-unplug
motor cables or repeatedly drive toward physical stops as an improvised test.

Save source hashes, build/upload/serial logs, and physical observations. Then:

```bash
git add lv2_module5/docs/control_interface.md lv2_module5/docs/control_test_plan.md \
  lv2_module5/docs/integration_steps.md lv2_module5/docs/integration_validation.md \
  lv2_module5/config/opencr.yaml lv2_module5/firmware/opencr/README.md \
  lv2_module5/firmware/opencr/tracking_controller_2axis \
  lv2_module5/firmware/opencr/tests/test_2axis_dry.py \
  lv2_module5/firmware/opencr/tests/bench_2axis_once.py \
  lv2_module5/firmware/opencr/tests/test_integrated_native.cpp \
  lv2_module5/firmware/opencr/tests/native_stubs \
  lv2_module5/firmware/opencr/tests/native_pty.cpp
# Add only the intended run logs separately after review.
git diff --cached --check -- . ':(exclude)*.log'
```
