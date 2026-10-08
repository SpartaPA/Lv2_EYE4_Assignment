# OpenCR 펌웨어 (담당: 제어, 빌드·업로드는 통합과 공동)

모든 빌드·업로드·시리얼 작업은 OpenCR가 USB로 연결된 **Raspberry Pi**에서 SSH로 수행한다.
한 번에 한 프로그램만 포트를 연다 (opencr_node, miniterm, 시험 스크립트 동시 사용 금지).

## 1. 파일 분류

| 경로 | 분류 | 역할 |
|---|---|---|
| `tracking_controller_2axis/` | **runtime** | 최종 Pan/Tilt 펌웨어. 기본 실제 출력, no-output은 시험 전용 compile 옵션 |
| `tests/test_2axis_dry.py` | test | 실제 보드 no-output 시험 (TEST_STATUS 확인, 모터 전원 OFF) |
| `tests/bench_2axis_once.py` | commissioning | 실제 단일 VEL 1회 후 침묵 → 500 ms timeout 관찰 (`--execute-live` 필수) |
| `tests/test_integrated_native.cpp`, `tests/native_stubs/` | test | 실제 .ino를 PC/Pi host에서 컴파일한 시나리오 시험 (가짜 Arduino/Workbench) |
| `tests/native_pty.cpp` | test | DRY 펌웨어를 PTY에 연결하는 host 실행기 (ROS `test_serial_pty`, `test_serial_ros`가 사용) |
| `commissioning/dxl_discovery/` | commissioning | 모터 ID·baud·프로토콜 스캔 (레지스터 쓰기 없음) |
| `commissioning/dxl_inspect/` | commissioning | 모드·토크·위치 등 상태 조회 |
| `commissioning/pan_commission/`, `tilt_hold_test/`, `tilt_commission/` | commissioning | 축별 첫 구동·Tilt 부하 유지 시험 (2026-10-06 기록의 원본 펌웨어) |
| `legacy/tracking_controller/`, `legacy/tests/test_parser*.py` | legacy | 단일 속도 파서 기준 버전과 그 시험. **2축 runtime에 사용하지 않음** (`parser_baseline` 로그 근거로 보존) |
| `patches/` | build | ARM GCC 14의 Arduino min/max 매크로 충돌 패치 (DynamixelWorkbench, OpenCR SDK) |
| `opencr_source_commit.txt` | build | 패치를 적용한 OpenCR 보드 패키지 source commit |

Arduino는 스케치 디렉터리 하나만 빌드한다. `native_stubs`는 Arduino 라이브러리로 설치하지 않는다.
상수(ID·baud·한계·timeout)의 근거와 사본: [`../../config/hardware.yaml`](../../config/hardware.yaml) — 상수를 바꾸면 같은 commit에서 함께 고친다.
시리얼 프로토콜·안전 계층: [`../../docs/control_interface.md`](../../docs/control_interface.md)

## 2. 초기 준비 또는 firmware 변경 시 업로드 (Pi)

정상 runtime 펌웨어는 기본 실제 출력이다. 실행마다 재업로드하거나 모드를 바꾸지 않는다.
처음 설치/firmware 변경 때만 업로드한다. 기존 commissioning에서 확인한 Velocity Mode/ID/baud/중립 자세를 유지한다.
카메라를 지지하고 시작한다. setup이 자동 점검 후 두 축 영속도·토크 유지·Bus_Watchdog을 설정한다.

```bash
REPO=$HOME/git/Lv2_EYE4_Assignment
PORT=/dev/serial/by-id/usb-ROBOTIS_OpenCR_Virtual_ComPort_in_FS_Mode_FFFFFFFEFFFF-if00
BUILD=$HOME/pa-opencr-build/build/tracking_controller_2axis
mkdir -p "$BUILD"
arduino-cli compile --clean --fqbn OpenCR:OpenCR:OpenCR --build-path "$BUILD" \
  "$REPO/lv2_module5/firmware/opencr/tracking_controller_2axis"
# compile 성공 후에만
opencr_ld "$PORT" 115200 "$BUILD/tracking_controller_2axis.ino.bin" 1
```

정상 Serial 명령은 VEL/STOP/STATUS다. CHECK/HOLD/ARM/DISARM이나 MODE handshake를 호출하지 않는다.
STATUS의 GOAL/POS/VEL/TORQUE로 동작을 확인한다. hardware FAULT는 원인 점검 후 복구하며 통신 timeout은 새 명령만 재개한다.
종료 후 토크 해제는 카메라 지지 → 포트 소유 프로그램 종료 → miniterm `SUPPORTED_OFF` → 확인 순서다.

## 3. 별도 no-output/commissioning 시험

Problem2는 firmware 업로드 없이 `ros2 run realsense_tracker test_control_dry`로 Serial을 열지 않는다.
기존 보드 parser 시험만 수행할 때는 **모터 전원 OFF**, 아래 옵션으로 별도 no-output 테스트 빌드를 사용한다.

```bash
arduino-cli compile --clean --fqbn OpenCR:OpenCR:OpenCR \
  --build-property 'compiler.cpp.extra_flags=-DENABLE_MOTOR_OUTPUT=0' \
  --build-path "$HOME/pa-opencr-build/build/2axis_no_output" \
  "$REPO/lv2_module5/firmware/opencr/tracking_controller_2axis"
# 위 시험 빌드를 보드에 올린 경우에만 (모터 전원 OFF)
python3 firmware/opencr/tests/test_2axis_dry.py --port "$PORT"
```

시험 전용 TEST_STATUS 응답으로 no-output build를 확인한다. 정상 runtime은 이 명령/응답을 사용하지 않는다.
실제 단일 명령 방향 시험은 초기 자동 점검 완료 뒤 기존 `bench_2axis_once.py --execute-live --case ...`를 사용한다.
이 옵션 이름은 commissioning 도구의 명시적 실제 구동 허가이며 정상 launch의 mode 선택이 아니다.
정상 direction은 2026-10-07 재조립 설정(Pan −1/Tilt −1)을 따른다. 실제 ex/ey 감소 방향은 재확인해야 한다.

## 4. Host-side 시험 (보드·모터 없음)

```bash
cd "$REPO/lv2_module5/firmware/opencr/tests"
g++ -std=c++17 -Wall -Wextra -Werror -DENABLE_MOTOR_OUTPUT=0 -I native_stubs test_integrated_native.cpp -o /tmp/native-dry
/tmp/native-dry
g++ -std=c++17 -Wall -Wextra -Werror -I native_stubs test_integrated_native.cpp -o /tmp/native-hardware-stub
/tmp/native-hardware-stub
# Linux PTY용 (실제 모터 접근 없는 compile)
g++ -std=c++17 -Wall -Wextra -DENABLE_MOTOR_OUTPUT=0 -I native_stubs native_pty.cpp -o /tmp/opencr-no-output-pty
ros2 run realsense_tracker test_serial_pty --firmware-executable /tmp/opencr-no-output-pty --output-dir <새폴더>/pty --cycles 20 --tick-sec 0.01
ros2 run realsense_tracker test_serial_ros --firmware-executable /tmp/opencr-no-output-pty --output-dir <새폴더>/ros
```

기대: PASS native controller safety scenarios NO_MOTOR_OUTPUT/HARDWARE_STUB.
기존 테스트 파일을 갱신해 validation STOP, clamp, 20 Hz 지속 갱신, 정확히 500 ms timeout, 새 command 복구,
옛 속도 복원 금지, STOP, parser 오류, millis rollover, 양축 쓰기/읽기 실패, 양축 encoder boundary를 검사한다.
host stub PASS는 실제 USB/모터 부하/정지거리/ARM toolchain PASS를 의미하지 않는다.
과거 results의 DRY/LIVE/ARM 로그는 구형 구현 증거로 보존하고 현재 runtime 시험 결과와 섞지 않는다.

## 5. 아직 하지 않은 하드웨어 시험

위치 경계 정지, 실제 정지 지연(마지막 명령 → 0 쓰기 → 속도 0 피드백), 모터 버스 통신 단절, 보드 멈춤 시 Bus_Watchdog, 피드백 실패.
모터 케이블을 뽑거나 한계까지 반복 jog하는 즉흥 시험은 하지 않는다. 별도 절차를 설계한 뒤 수행한다.
