# OpenCR 펌웨어 개발 및 시험

## 1. 역할

OpenCR는 Raspberry Pi에서 USB 시리얼로 받은 명령을 처리하고, 최종적으로 Pan/Tilt DYNAMIXEL 두 축을 제어한다.

제어 담당 범위:

- 시리얼 명령 파서
- 모터 식별 및 통신
- 축별 속도·각도 제한
- 실제 모터 정지
- 보드 측 명령 타임아웃
- 펌웨어 빌드·업로드 및 시험

## 2. 현재 구현 상태

현재 `tracking_controller/tracking_controller.ino`는 **단일 속도 파서 기준 버전**이다.

구현 및 검증 완료:

- ARM, VEL, STOP, DISARM, STATUS 처리
- 입력값 및 길이 검증
- 300 ms 소프트웨어 명령 워치독
- 기본 및 확장 파서 시험

아직 구현하지 않은 항목:

- Pan/Tilt 2축 명령
- DYNAMIXEL 제어 및 위치 피드백
- 물리적 속도·각도 제한
- 실제 모터 정지와 오류 처리

현재 펌웨어는 모터 명령을 보내지 않는다. `ARM`은 내부 상태만 변경하며 모터 토크를 활성화하지 않는다.

## 3. 관련 문서

- [제어 인터페이스](../../docs/control_interface.md)
- [제어 시험 계획 및 결과](../../docs/control_test_plan.md)
- [프로젝트 README](../../README.md)
- [파서 기준 버전 시험 증빙](../../results/logs/opencr/parser_baseline/)

문서 링크는 이 README가 있는 `firmware/opencr/`를 기준으로 작성한다.

## 4. 파일 구성

| 경로 | 용도 |
|---|---|
| `tracking_controller/tracking_controller.ino` | 현재 펌웨어 |
| `tests/test_parser.py` | 기본 파서 시험 |
| `tests/test_parser_extended.py` | 확장 파서 시험 |
| `opencr_source_commit.txt` | 시험에 사용한 OpenCR 소스 리비전 |
| `../../results/logs/opencr/parser_baseline/` | 기존 시험 원본 로그 |

기존 기준 버전의 코드와 증빙은 커밋 `efce660`에서 확인할 수 있다. 해당 커밋은 디렉토리 변경 전 경로를 사용한다.

## 5. 실행 위치

| 장치 | 실행 항목 |
|---|---|
| PC | D435 ROS wrapper, perception_node, control_node |
| Raspberry Pi | opencr_node, 펌웨어 빌드·업로드, 시리얼 시험 |
| OpenCR | 명령 처리, 최종 모터 제어 및 보드 타임아웃 |

SSH 접속과 PC–Pi ROS 2 DDS 통신은 별도로 확인한다.

D435는 PC에 연결하며, Raspberry Pi와 OpenCR는 USB 시리얼로 연결한다.

## 6. Raspberry Pi 준비

아래 명령은 Raspberry Pi에 저장소가 다음 위치로 준비되어 있다고 가정한다.

```bash
~/git/Lv2_EYE4_Assignment
```

기존에 확인한 도구:

- Arduino CLI 1.5.1
- ARM GCC 14.2.1
- opencr_ld 1.0.4
- Python 및 pyserial

확인 명령:

```bash
command -v arduino-cli
command -v arm-none-eabi-g++
command -v opencr_ld
python3 -c "import serial; print('pyserial OK')"
arduino-cli board listall OpenCR
ls -l /dev/serial/by-id/
```

수동 등록한 OpenCR 보드 식별자:

```text
OpenCR:OpenCR:OpenCR
```

도구가 없거나 보드가 검색되지 않으면 기존 환경 설정을 먼저 확인한다.

## 7. 기준 버전 빌드

Raspberry Pi에서 실행한다.

```bash
cd ~/git/Lv2_EYE4_Assignment

REPO_ROOT="$PWD"
BUILD_DIR="$HOME/pa-opencr-build/build/tracking_controller"
RUN_ID="parser_$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$REPO_ROOT/lv2_module5/results/logs/opencr/$RUN_ID"

mkdir -p "$BUILD_DIR" "$LOG_DIR"
git rev-parse HEAD > "$LOG_DIR/repository_commit.txt"
git status --short > "$LOG_DIR/working_tree_status.txt"

set -o pipefail

arduino-cli compile \
  --fqbn OpenCR:OpenCR:OpenCR \
  --build-path "$BUILD_DIR" \
  "$REPO_ROOT/lv2_module5/firmware/opencr/tracking_controller" \
  2>&1 | tee "$LOG_DIR/build.log"
```

컴파일 성공 후에만 업로드한다. 생성된 바이너리를 소스 파일과 혼동하지 않는다.

빌드 후 작업 트리에 변경이 있다면 커밋 번호만으로 시험 소스를 완전히 특정할 수 없으므로 변경 내용도 기록한다.

## 8. 기준 버전 업로드

앞 절의 변수가 설정된 동일한 터미널에서 실행한다.

모터 전원을 끄고, OpenCR 포트를 사용하는 시리얼 모니터·시험 프로그램·opencr_node를 종료한다.

현재 확인된 장치 경로:

```bash
OPENCR_PORT="/dev/serial/by-id/usb-ROBOTIS_OpenCR_Virtual_ComPort_in_FS_Mode_FFFFFFFEFFFF-if00"

opencr_ld "$OPENCR_PORT" 115200 \
  "$BUILD_DIR/tracking_controller.ino.bin" \
  1 \
  2>&1 | tee "$LOG_DIR/upload.log"
```

`CRC OK`와 `[OK] Download`를 확인한다.

업로드는 OpenCR의 기존 응용 펌웨어를 교체한다. 장치를 바꾼 경우 실제 `/dev/serial/by-id/` 경로를 다시 확인한다.

## 9. 파서 시험

모터 전원을 끈 상태로 실행한다.

### 기본 시험

```bash
python3 -u \
  "$REPO_ROOT/lv2_module5/firmware/opencr/tests/test_parser.py" \
  2>&1 | tee "$LOG_DIR/parser_test.log"
```

### 확장 시험

OpenCR를 재시작한 뒤, 다른 프로그램에서 ARM 또는 DISARM을 보내지 않고 실행한다. 재시작과 펌웨어 기동을 확인한 후 시험한다.

```bash
python3 -u \
  "$REPO_ROOT/lv2_module5/firmware/opencr/tests/test_parser_extended.py" \
  2>&1 | tee "$LOG_DIR/parser_extended_test.log"
```

기대 최종 출력:

```text
ALL FIVE EXTENDED CHECKS PASSED
```

두 스크립트에는 시험 당시의 장치 경로가 포함되어 있다. 장치를 변경하면 해당 경로를 확인하고 수정한다.

기존 시험은 단일 값 형식인 `VEL <value>`를 사용한다. 2축 프로토콜로 변경한 뒤에는 시험 스크립트도 함께 수정해야 한다.

## 10. 로그 출력과 워치독

현재 기준 버전은 OpenCR 전용 `CDC_Itf_Write()`를 사용하여 진단 출력을 한 번 시도한다.

송신할 수 없는 경우 메시지를 버리고 대기하거나 재시도하지 않는다. 따라서 ACK나 이벤트 메시지가 항상 호스트에 전달된다고 가정하지 않는다.

현재 소프트웨어 워치독은 펌웨어 루프가 실행되는 동안 동작한다. 펌웨어 정지와 실제 모터의 정지 성능까지 검증한 것은 아니다.

## 11. 2축 구현 시 적용할 원칙

- 모터 ID와 baud rate를 실제 장비에서 확인한다.
- Pan/Tilt ID를 명확히 구분한다.
- USB baud rate와 DYNAMIXEL bus baud rate를 별도로 기록한다.
- rad/s에서 모터 단위로의 변환 위치를 명시한다.
- 두 축 명령을 함께 검증하고 반영한다.
- 정지 및 통신 타임아웃을 두 축 모두에 적용한다.
- 위치 피드백으로 각도 한계의 바깥 방향 명령을 차단한다.
- 타임아웃 후 자동 재활성화를 금지한다.
- Tilt 축의 중력 영향을 고려하여 정지와 토크 해제를 구분한다.
- 실제 정지 방식과 자세 유지 여부를 시험으로 확인한다.

2축 구현과 시험 결과는 기존 `parser_baseline/` 로그를 덮어쓰지 않고 별도의 실행 디렉토리에 보관한다.