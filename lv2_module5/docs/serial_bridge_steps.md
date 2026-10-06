# DRY 펌웨어 전용 시리얼 bridge 시험

## 범위와 모드

기준 checkpoint: 02bb34d. 기존 ROS dry bridge와 제어 시험은 보존한다.
본 변경은 가상 시리얼/DRY OpenCR만 지원하며 LIVE motor output을 승인하지 않는다.

| 설정 | 동작 |
|---|---|
| dry_run=true, serial_mode=false | 기존 dry sink, 포트를 열지 않음 |
| dry_run=true, serial_mode=true | 시리얼 연결, MODE=DRY board만 허용 |
| dry_run=false | 실행 거부 |
| expected_board_mode=LIVE | 실행 거부 |

DRY 펌웨어는 모터 bus를 초기화하거나 읽고 쓰지 않는다. 실제 USB DRY 시험은
가상 시험 통과 후 별도 수행한다. 이 단계에서는 OpenCR USB를 분리해 둔다.

## 제어 규칙

- 연결 후 STATUS만 전송한다. 기존 session을 인수하거나 자동 CHECK/HOLD/ARM하지 않는다.
- /opencr/prepare (std_srvs/Trigger): CHECK/HOLD 요청. success는 요청 수락이며 완료 증명이 아니다.
- /opencr/arm: 신선한 stop=false 명령과 READY 상태에서 명시적으로 ARM 요청.
- /opencr/disarm: 영속도 및 논리적 비활성화 요청, firmware 토크 유지.
- /opencr/bridge_status: String(JSON), bridge phase, 최초 오류, board 캐시와 수신 나이.
- 정상 표적 소실의 stop=true는 STOP이다. 반복되는 신선한 STOP으로 명령 타이머를 유지한다.
- 정상 소실 후 새 표적은 제어 노드의 3프레임 복귀를 거쳐 다시 VEL을 보낸다.
- ROS 명령 0.15초 중단, board timeout/FAULT, 응답 실패는 bridge FAULT 고정이다.
- FAULT 이후 새 표적이나 재연결로 자동 ARM하지 않는다. 원인 확인과 명시적 새 세션이 필요하다.
- ACK 대기 초기값 0.20초, STATUS 주기 0.10초, STATUS 수신 최대 나이 0.40초.
- 시리얼 오류 시 DISARM을 best-effort로 시도한다. 실제 정지나 자세 유지를 보장하지 않는다.
- SUPPORTED_OFF 자동 전송 없음. 토크 해제는 기계적 지지 확인 후 별도 절차다.
- USB 115200 8N1. DYNAMIXEL bus 1000000은 firmware 측 설정으로 별개다.
- POSIX transport 사용: Linux/Pi 전용, pyserial 추가 설치 불필요.
- board MODE=DRY 확인 전 CHECK/HOLD/ARM/VEL을 전송하지 않는다.

## 1. 테스트 디렉터리와 논리 시험

새 SSH 터미널에서 이전 mock overlay를 source하지 않는다.

```bash
source /opt/ros/lyrical/setup.bash
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_LOCALHOST_ONLY=1

REPO_ROOT="$HOME/git/Lv2_EYE4_Assignment"
WS="$REPO_ROOT/lv2_module5/ros2_ws"
FW_DIR="$REPO_ROOT/lv2_module5/firmware/opencr"
NATIVE_DIR="$HOME/pa-opencr-build/build/native_bridge"
RUN_ID="serial_bridge_dry_$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$REPO_ROOT/lv2_module5/results/logs/ros/$RUN_ID"
mkdir -p "$LOG_DIR"
set -o pipefail
cd "$WS"

PYTHONPATH="$WS/src/realsense_tracker" \
  python3 -m unittest discover -s src/realsense_tracker/test -v \
  2>&1 | tee "$LOG_DIR/core_tests.log"
```

기대: 기존 5개 + 시리얼 13개 = 총 18개 통과.

## 2. 실제 firmware 코드와 PTY 통신

이전 native_bridge/opencr_dry_pty는 ENABLE_MOTOR_OUTPUT=0으로 컴파일했다.
그 실행 파일을 사용한다. 테스트는 자체 PTY를 생성하므로 실제 port를 지정하지 않는다.

```bash
PYTHONPATH="$WS/src/realsense_tracker" \
  python3 -m realsense_tracker.test_serial_pty \
  --firmware-executable "$NATIVE_DIR/opencr_dry_pty" \
  --output-dir "$LOG_DIR/pty" \
  2>&1 | tee "$LOG_DIR/pty_tests.log"
```

기대:
ALL SERIAL PTY CORE CHECKS PASSED; FIRMWARE_MODE=DRY

실제 DRY firmware 상태 기계와 PTY를 통해 준비/ARM/2축 VEL/STOP/타임아웃을 검사한다.
DRY feedback의 위치/속도/토크는 모의 값이며 실제 모터 측정이 아니다.
잘못된 MODE, 응답 유실, malformed/fragmented status, disconnect, board 오류는
논리 시험의 scripted transport로 검사한다. 모든 고장 주입이 실제 PTY 시험인 것은 아니다.

## 3. 빌드와 기존 ROS dry 회귀 시험

```bash
colcon build --symlink-install \
  --base-paths src/realsense_tracker src/realsense_tracker_interfaces \
  --packages-select realsense_tracker_interfaces realsense_tracker \
  2>&1 | tee "$LOG_DIR/build.log"
```

성공 후:

```bash
source "$WS/install/setup.bash"
ros2 pkg prefix realsense_tracker
ros2 pkg prefix realsense_tracker_interfaces
mkdir -p "$LOG_DIR/dry_regression"
ros2 run realsense_tracker test_control_dry \
  --output-dir "$LOG_DIR/dry_regression" \
  2>&1 | tee "$LOG_DIR/dry_regression.log"
```

기대: ALL REPOSITORY SEPARATE-PROCESS DRY CHECKS PASSED; SERIAL_OPENED=FALSE

## 4. ROS → 실제 시리얼 bridge → DRY firmware

```bash
ros2 run realsense_tracker test_serial_ros \
  --firmware-executable "$NATIVE_DIR/opencr_dry_pty" \
  --output-dir "$LOG_DIR/serial_ros" \
  2>&1 | tee "$LOG_DIR/serial_ros_tests.log"
```

runner가 controller, serial bridge, DRY firmware를 별도 process로 시작한다.
준비와 ARM service를 명시적으로 호출하며, 7개 입력과 정상 소실 복귀를 확인한다.
제어 process 종료 시 bridge의 ROS_COMMAND_TIMEOUT 및 DISARM 전송 시도를 확인한다.
시리얼 로그의 ARM은 정확히 1회여야 한다. 마지막 fresh target으로 자동 재ARM하지 않는다.

기대: ALL SERIAL ROS PTY CHECKS PASSED; FIRMWARE_MODE=DRY

성공/실패 후 자식 process는 정리한다. 로그/CSV는 덮어쓰지 않으므로 재시도는
새 RUN_ID 및 LOG_DIR로 수행한다. 서비스 success 응답과 이후 상태 확인을 구분한다.

## 증거와 다음 gate

core_tests.log, pty_tests.log, pty/serial_pty.csv, build.log,
dry_regression.log, serial_ros_tests.log, serial_ros/*.log/serial_ros.csv를 보존한다.
working tree 기반 시험이므로 기준 commit과 수정 source를 함께 기록한다.
모든 시험을 통과한 뒤 선택적으로 stage/commit한다. 오래된 untracked 시험은 추가하지 않는다.

그 다음은 실제 OpenCR에 ENABLE_MOTOR_OUTPUT=0 firmware를 올려 USB serial DRY
시험을 수행하는 단계다. 본 patch에는 LIVE bridge나 새 firmware upload 명령을 포함하지 않는다.
ROS 2가 없는 제작 환경에서는 ROS runner를 실행하지 못했다. Pi에서 별도 확인해야 한다.

## API 참고

- https://docs.python.org/3/library/termios.html
- https://docs.python.org/3/library/tty.html
- https://docs.python.org/3/library/pty.html
