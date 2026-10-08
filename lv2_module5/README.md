# Module 5 — 비전 객체 추적 시스템 (EYE4 / 아이뻐)

RealSense D435 Color 영상에서 단일 색상 목표(파란 퍽)를 HSV·Contour로 찾고, 영상 중심 오차를 줄이도록
DYNAMIXEL 2개(Pan = 좌우, Tilt = 상하)를 P 제어하는 **Pan/Tilt 2축 추적 시스템**이다.
목표 미검출·인지 입력 중단·제어 통신 중단에서 정지하고, 신선한 목표 3프레임 연속 검출로 복귀한다.

> 팀 확정 조건: 발제문 기본(수평 1축)보다 확장된 **Pan/Tilt 2축 추적이 필수**다. `/target` 규약·안전·시험·제출 규칙은 발제문 그대로 따른다.

> **현재 상태 (2026-10-07)** — 코드·설정·시험 도구는 완성(IMPLEMENTED)되어 있고 아래 [22. 현재 미검증 항목](#22-현재-미검증-항목-hardware-verification-todo)은 실제 장비 시험 전이다.
> 이 문서의 명령 중 실제 장비에서 실행된 기록이 있는 것은 `results/logs/`에 근거가 있는 항목뿐이다.

목차: [1 목적](#1-프로젝트-목적) · [2 구조](#2-최종-시스템-구조) · [3 PC](#3-pc-환경-ssh-터미널) · [4 Pi](#4-raspberry-pi-환경-ros-2-runtime) · [5 D435](#5-realsense-d435) · [6 OpenCR](#6-opencr--dynamixel) · [7 설치](#7-설치-prerequisites-pi) · [8 빌드](#8-build-pi) · [9 P1](#9-problem-1-실행--인지) · [10 P2](#10-problem-2-dry-test--모터-출력-없음) · [11 OpenCR DRY](#11-opencr-dry-test--실제-보드-모터-출력-없음) · [12 방향](#12-실제-모터-방향-test) · [13 ROS 확인](#13-pi-ros-2-runtime-확인-ros_domain_id--rmw--topic) · [14 추적](#14-실제-tracking-실행) · [15 종료](#15-안전한-종료-방법) · [16 Kp](#16-problem-3-kp-test) · [17 P4](#17-problem-4-validation) · [18 bag 기록](#18-bag-record) · [19 bag 재생](#19-bag-replay) · [20 분석](#20-result-analysis) · [21 결과 위치](#21-results-위치) · [22 미검증](#22-현재-미검증-항목-hardware-verification-todo)

---

## 1. 프로젝트 목적

| 문제 | 내용 | 주요 산출물 |
|---|---|---|
| 1 | HSV·Contour 검출, 정규화 중심 오차 ex/ey, 면적비, 미검출 처리 | `perception_node`, 정상·없음·가림 이미지, 30/10 프레임 사람 대조 |
| 2 | `/target`(PointStamped) 인터페이스, 모터 출력 없는 7개 모의 입력 | `control_node`, `test_control_dry` |
| 3 | Pan/Tilt 2축 P 제어, 방향·속도·각도 제한·deadband, Kp A/B × 3회 | `control.yaml`, 추적 CSV·그래프 |
| 4 | IDLE/TRACKING/LOST, 미검출·입력 timeout·통신 중단 정지, 3프레임 복귀, 지표 | `tracking_logger.py`, `analyze_tracking.py`, 펌웨어 watchdog |
| 5 | bag 기록, 입력 재처리(`/target_replay`), 결과 재분석, 팀원 재현 | `recordings/README.md` |

요구사항별 구현·검증 상태: [docs/requirements_traceability.md](docs/requirements_traceability.md)

## 2. 최종 시스템 구조

**모든 ROS 2 노드는 Raspberry Pi 한 대에서 실행한다.** 사용자 PC는 SSH 터미널로 명령을 입력하는 용도이며 ROS 2 노드를 실행하지 않는다.

```text
[사용자 PC] ── SSH (명령 입력·로그 확인·파일 전송만) ──▶ [Raspberry Pi — ROS 2 runtime]

  RealSense D435 ──USB 3──▶ realsense2_camera (공식 wrapper)
                              │ /camera/camera/color/image_raw (+ aligned depth, camera_info)
                              ▼
                           perception_node ── /target  geometry_msgs/PointStamped (x=ex, y=ey, z=area_ratio)
                              ▼                 QoS best effort, depth 1
                           control_node ───── /tracking_status  std_msgs/String (IDLE/TRACKING/LOST)
                              │                 /control/pan_tilt_cmd  PanTiltCommand (rad/s, 20 Hz)
                              ▼
                           opencr_node ──USB Serial 115200──▶ OpenCR (tracking_controller_2axis)
                                                                 ├─ Pan  XM430-W350 ID 11 ┐ DYNAMIXEL
                                                                 └─ Tilt XM430-W350 ID 12 ┘ 1 Mbps, Protocol 2.0
```

노드 간 토픽은 Pi 내부 ROS 2(DDS) 통신이다. SSH는 ROS 메시지를 전달하지 않는다.

| 계층 | 파일 | 책임 |
|---|---|---|
| 인지 | `realsense_tracker/detector.py`, `perception_node.py` | HSV·Contour, ex/ey/area_ratio, 미검출 z=0, 원본 영상 시각 유지 |
| 제어 | `control_core.py`, `control_node.py` | 신선도·timeout(0.5 s), 상태, P 제어, direction(한 곳), 속도 상한, deadband, 3프레임 복귀 |
| bridge | `serial_core.py`, `opencr_node.py`, `dry_bridge.py` | ROS→시리얼, fresh 명령만 1회 전송, 명령 timeout 0.5 s; Problem2 sink 별도 |
| 펌웨어 | `firmware/opencr/tracking_controller_2axis/` | 단위 변환, 0.05 rad/s 상한, 엔코더 경계, 명령 timeout 500 ms, 모터 Bus_Watchdog 500 ms |

인터페이스·상태·timeout 상세: [docs/control_interface.md](docs/control_interface.md) · 디렉토리·담당: [directory_workflow_guide.md](directory_workflow_guide.md) · 팀 네비게이터: [팀업무_네비게이터.md](팀업무_네비게이터.md)

### 설정 파일 (Source of Truth)

| 구분 | 파일 | 읽는 주체 |
|---|---|---|
| Perception runtime | `ros2_ws/src/realsense_tracker/config/tracker.yaml` | perception_node, tools/ |
| Camera profile·topic | `ros2_ws/src/realsense_tracker/config/camera.yaml` | tracker.launch.py, perception_node, tools/ |
| Control runtime | `ros2_ws/src/realsense_tracker/config/control.yaml` | control_node (실제 추적) |
| Control DRY 시험 | `ros2_ws/src/realsense_tracker/config/control_dry.yaml` | control_dry.launch.py (고정 모의값) |
| OpenCR Serial runtime | `ros2_ws/src/realsense_tracker/config/opencr_live.yaml` | opencr_node (실제 모터) |
| Hardware record | `config/hardware.yaml` | 사람 (펌웨어 상수의 사본·근거, 노드는 읽지 않음) |
| Verification conditions | `config/test.yaml` | 사람 (시험 전 확정 조건, 노드는 읽지 않음) |

같은 값이 두 곳에 있는 경우는 펌웨어 상수(컴파일 시 고정) ↔ `config/hardware.yaml`(사본)과 `control_dry.yaml`(시험 고정값)뿐이다. 자세한 규칙: [config/README.md](config/README.md)

## 3. PC 환경 (SSH 터미널)

- 역할: Pi에 SSH 접속해 명령 입력, 결과 파일 내려받기(`scp`), 문서 작성. **ROS 2 노드를 실행하지 않는다.**
- 필요: SSH 클라이언트. ROS 2 설치 불필요.
- 그래프·이미지는 Pi에서 파일로 저장한 뒤 PC로 복사해 확인한다 (SSH에 GUI 창 불필요).
- 이미 기록된 인지 증거(2026-10-06)는 인지 담당 노트북(Ubuntu 24.04 + ROS 2 Lyrical)에서 측정한 것이다 → 조건은 [report.md 문제 1](report.md#문제-1--hsvcontour-검출-파이프라인) 참고.

## 4. Raspberry Pi 환경 (ROS 2 runtime)

| 항목 | 값 | 상태 |
|---|---|---|
| OS | Ubuntu Server 64-bit (arm64). 발제문에 24.04 / 26.04 표기가 섞여 있음 | TODO: 실제 버전 `lsb_release -a` 기록 |
| ROS 2 | Lyrical (`/opt/ros/lyrical`) | 사용 기록 있음 (`results/logs/control/*` 시험이 Pi에서 실행됨) |
| RMW | 기본값(Fast DDS) | TODO: `echo $RMW_IMPLEMENTATION` 결과 기록 |
| ROS_DOMAIN_ID | 기본값(미설정 = 0)으로 동작. 같은 네트워크의 다른 장비와 분리가 필요할 때만 설정 | TODO: 실제 사용 값 기록 |
| 연결 | D435 → Pi USB 3 포트, OpenCR → Pi USB | D435의 Pi 연결 실행 기록은 아직 없음 |

## 5. RealSense D435

`config/camera.yaml` 주석에 실측 기록이 있다 (2026-10-06, 인지 담당 노트북):
D435 (Product ID 0x0B07, IMU 없음 — D435i 아님), serial 261322071425, firmware 5.15.1.55, RealSense ROS wrapper v4.57.7 / librealsense v2.57.7,
USB 3.2, Color 640×480@30 rgb8, 정렬 Depth 640×480 16UC1, frame_id `camera_color_optical_frame`, K = [607.571, 0, 327.340; 0, 607.530, 239.493; 0, 0, 1],
wrapper 발행 QoS RELIABLE·KEEP_LAST 1.

TODO(Pi): D435를 Pi USB 3에 연결한 상태에서 USB 속도·토픽·처리 FPS를 다시 기록한다 (Pi CPU에서 FPS가 달라질 수 있음).

## 6. OpenCR / DYNAMIXEL

| 항목 | 값 | 근거 |
|---|---|---|
| 모터 | XM430-W350 × 2 (모델 1020), Protocol 2.0, 1 Mbps | `results/logs/opencr/discovery_sdk_fix_20261006_103249/scan.log` |
| ID | Pan 11, Tilt 12 | 같은 scan.log, `docs/hardware.md` |
| Operating Mode | 1 (Velocity) | `results/logs/opencr/inspect_20261006_110144/inspect.log` |
| 원시 + 방향 | Pan 좌측, Tilt 위쪽 (2026-10-07 재조립 config 기록, 폐루프 재확인 필요) | pan/tilt_commission test_notes |
| USB 시리얼 | `/dev/serial/by-id/usb-ROBOTIS_OpenCR_Virtual_ComPort_in_FS_Mode_FFFFFFFEFFFF-if00`, 115200 | `docs/hardware.md` |
| 펌웨어 | `tracking_controller_2axis` (정상 기본 실제 출력, no-output 빌드는 시험 전용) | [firmware/opencr/README.md](firmware/opencr/README.md) |
| 안전 상수 | 0.05 rad/s, 명령 timeout 500 ms, Bus_Watchdog 500 ms, 경계 ±80/±100 counts | `config/hardware.yaml` |

> ⚠ Tilt는 토크가 꺼지면 카메라 무게로 내려간다. 토크 해제(SUPPORTED_OFF)·전원 차단·reset 전에는 **항상 카메라를 손으로 지지**한다.
> 한 번에 한 프로그램만 OpenCR 포트를 사용한다 (opencr_node, miniterm, 시험 스크립트 동시 실행 금지).

## 7. 설치 prerequisites (Pi)

```bash
# ROS 2 Lyrical이 설치된 Pi에서
sudo apt install ros-lyrical-realsense2-camera python3-opencv python3-numpy python3-yaml \
                 python3-serial python3-matplotlib python3-colcon-common-extensions
# OpenCR 빌드·업로드: arduino-cli + OpenCR 보드 패키지, DynamixelWorkbench (firmware/opencr/README.md 참고)
```

- `python3-serial`: 펌웨어 시험 스크립트(`firmware/opencr/tests/*.py`)와 miniterm용. ROS bridge(`opencr_node`)는 pyserial 없이 POSIX termios를 쓴다.
- TODO(Pi): `ros-lyrical-realsense2-camera` arm64 패키지 설치 결과를 기록한다.

## 8. Build (Pi)

```bash
source /opt/ros/lyrical/setup.bash
cd ~/git/Lv2_EYE4_Assignment/lv2_module5/ros2_ws
colcon build --symlink-install --packages-select realsense_tracker_interfaces realsense_tracker
source install/setup.bash

ros2 pkg executables realsense_tracker
# 기대: perception_node, control_node, opencr_node, test_control_dry, test_serial_pty, test_serial_ros
ros2 interface show realsense_tracker_interfaces/msg/PanTiltCommand
```

`build/ install/ log/`는 Git에 올리지 않는다 (.gitignore). 이후 모든 터미널에서 위 두 `source`를 먼저 실행한다.
아래에서 `CFG=$(ros2 pkg prefix realsense_tracker)/share/realsense_tracker/config` 로 설치된 설정 폴더를 가리킨다.

## 9. 정상 실행 — Raspberry Pi에서 한 줄

초기 설치 또는 소스 변경 후 Pi에서 build/source한다. PC는 SSH 접속용이며 모든 명령은 Pi 셸에서 실행한다.

```bash
cd ~/git/Lv2_EYE4_Assignment/lv2_module5/ros2_ws
source /opt/ros/lyrical/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 launch realsense_tracker tracker.launch.py
```

기존 `camera.yaml`, `tracker.yaml`, `control.yaml`, `opencr_live.yaml`을 launch가 자동 읽는다.
RealSense wrapper → perception_node → control_node → opencr_node가 모두 자동 시작된다.
정상 실행에 mode 선택, prepare/arm/disarm 서비스, 수동 launch 인자는 필요 없다.
Firmware 업로드는 초기 준비 또는 firmware 변경 시에만 별도 수행한다: [firmware/opencr/README.md](firmware/opencr/README.md).
초기 장착·모터 설정과 중립 자세는 기존 commissioning 근거대로 준비한다. 펌웨어가 자동으로 모터를 점검하고 영속도 토크 유지로 시작한다.

문제 1 이미지는 `tools/image_capture.py --source ros`, `eval_frames.py`, `eval_score.py`로 기존처럼 저장한다.
**모터 없는 문제 1 단독 검증**에는 정상 통합 launch를 쓰지 않는다. 모터 전원 OFF/USB 출력 경로 분리 후 카메라 wrapper와 perception만 실행한다:

```bash
CFG=$(ros2 pkg prefix realsense_tracker)/share/realsense_tracker/config
# Pi 터미널 1 (모터 출력 OFF)
ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true \
  rgb_camera.color_profile:=640,480,30 depth_module.depth_profile:=640,480,30
# Pi 터미널 2
ros2 run realsense_tracker perception_node --ros-args --params-file $CFG/tracker.yaml -p camera_config:=$CFG/camera.yaml
```

HSV 조정은 기존 GUI 도구를 사용하며 ROS runtime은 Pi에서 실행한다. Depth는 선택적 거리 기록이고 기본 `enforce_depth_range: false`다.
Aligned Depth/CameraInfo/profile/encoding/D435 정보는 `camera.yaml`과 기존 기록 도구로 확인한다.

## 10. Problem 2 DRY test — 실제 모터 출력 OFF

정상 launch를 종료하고 모터 전원 OFF 및 OpenCR USB 출력 경로를 분리한다. 카메라를 먼저 지지한다.
시험은 기존 `control_node` + `dry_bridge`를 별도 프로세스로 실행한다. dry_bridge는 Serial을 열지 않는다.

```bash
export ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 run realsense_tracker test_control_dry
```

출력 디렉터리는 자동 생성한다. 기존 증빙 폴더를 명시하려면 `--output-dir <새 폴더>`만 선택적으로 추가한다.

| 시험 | 입력 | 고정 DRY 설정 기대값 |
|---|---|---|
| T1 | x=0,y=0,z>0 | TRACKING, Pan/Tilt 0 |
| T2 | x=+0.4,y=0,z>0 | Pan −0.04 rad/s |
| T3 | x=−0.4,y=0,z>0 | Pan +0.04 rad/s |
| T4 | x=0,y=+0.4,z>0 | Tilt +0.04 rad/s |
| T5 | x=0,y=−0.4,z>0 | Tilt −0.04 rad/s |
| T6 | z=0 | 즉시 LOST + STOP |
| T7 | /target 침묵 | 0.5초 후 LOST + STOP |

fresh valid target 3프레임 연속 후 TRACKING으로 복귀한다. DRY direction은 시험 고정값(−1/+1), 정상 runtime direction은 `control.yaml`(−1/−1)이며 의도적으로 분리한다.
순수 unit test는 ROS 없이도 가능하다:

```bash
cd ~/git/Lv2_EYE4_Assignment/lv2_module5
PYTHONPATH=ros2_ws/src/realsense_tracker python3 -m unittest discover -s ros2_ws/src/realsense_tracker/test -v
```

## 11. 펌웨어 검증 — 별도 시험

기존 native/PTY/보드 시험은 [firmware/opencr/README.md](firmware/opencr/README.md)를 따른다.
no-output compile 옵션은 시험 전용이며 정상 runtime에서 DRY/LIVE를 선택하지 않는다.
실제 보드 no-output 시험은 반드시 모터 전원 OFF에서 수행한다. 시험 빌드를 정상 출력 펌웨어로 오인하지 않는다.

## 12. 하드웨어 방향·범위 확인

Pan/Tilt 2축은 필수다. 정상 config는 Kp_pan/Kp_tilt=0.3, direction=−1/−1, deadband=0.03이다.
기존 firmware bench 상한에 맞춰 두 축 속도 상한을 **0.05 rad/s**로 통일한다. Kp 최종 튜닝값 또는 기구 승인값이라는 뜻은 아니다.
실제 엔코더 경계는 펌웨어만 담당한다: Pan 중립 3078, Tilt 중립 0 mod 4096, STOP 경계 ±80 counts, outer FAULT ±100 counts.
STOP 경계에서 더 바깥 명령은 STOP하고 새 안쪽 명령은 허용한다. 이 범위는 임시 bench 값이며 실제 기구 최대 회전범위는 미확정이다.
장착 방향은 `control.yaml`의 2026-10-07 재조립 기록을 유지한다. 낮은 속도·현재 경계 안에서 실제 영상 ex/ey가 줄어드는지 두 축 모두 재확인한다.

## 13. Pi ROS 2 runtime 확인

모든 Pi SSH 터미널은 같은 ROS 환경/도메인을 사용한다. PC↔Pi DDS 설정은 필요 없다.

```bash
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 node list
ros2 topic list
ros2 topic info -v /target
ros2 topic info -v /control/pan_tilt_cmd
ros2 topic hz /control/pan_tilt_cmd
```

기대 노드: RealSense wrapper(`/camera/camera`), `/perception_node`, `/control_node`, `/opencr_node`.
기대 토픽: `/camera/camera/color/image_raw`, `/camera/camera/aligned_depth_to_color/image_raw`, `/camera/camera/color/camera_info`, `/target`, `/tracking_status`, `/control/pan_tilt_cmd`.
`/target`은 PointStamped, x=ex(오른쪽+), y=ey(아래+), z=area_ratio이며 미검출 x=y=z=0이다.
원본 영상 header.stamp를 유지하며 처리한 영상마다 정상/미검출 모두 1회 발행한다. target QoS best-effort, depth 1과 제어 구독 호환을 확인한다.

## 14. 실제 Tracking 실행과 로그

9절 한 줄 launch가 정상 실행점이다. non-zero command는 TRACKING에서만 **20 Hz(0.05초)** 타이머로 발행한다.
z=0/무효 입력/LOST 전환은 타이머를 기다리지 않고 STOP을 발행한다.
target·control command·firmware command·모터 Bus_Watchdog timeout은 모두 **0.5초**다.
0.5초는 구동 시간을 제한하는 값이 아니다. 새 유효 명령이 주기적으로 들어올 때마다 timer가 갱신되며 마지막 명령 뒤 0.5초 침묵일 때만 STOP한다.
timeout 후 옛 non-zero 속도를 복원하지 않는다. 새 fresh command만 적용하고 target 소실 복귀는 3프레임 조건을 따른다.

문제 3·4 추적 CSV는 별도 Pi SSH 터미널에서 기록한다:

```bash
cd ~/git/Lv2_EYE4_Assignment/lv2_module5
python3 tools/tracking_logger.py --run-id normal_01
```

시리얼 증빙이 필요하면 실행 전 `opencr_live.yaml`의 선택적 `csv_path`에 Pi의 새 CSV 절대경로를 기록하고 build/source한다.
필수 runtime 설정은 port/baud/command_timeout_sec이며 CSV는 mode/구동 허가 flag가 아니다. 기존 CSV는 덮어쓰지 않는다.

## 15. 자동 안전정지와 종료

| 상황 | 자동 동작 |
|---|---|
| target z=0 또는 무효·오래된 target | LOST, 즉시 STOP; 이전 좌표 버림 |
| target 침묵 0.5초 | LOST + STOP |
| control command 침묵 0.5초 | bridge STOP, 다음 fresh 명령만 복구 |
| Serial 연결 실패/끊김, board 응답 0.5초 침묵 | ERROR, 가능한 STOP 후 node 종료; 자동 reconnect 없음 |
| firmware 명령 침묵 0.5초 | 두 축 영속도, 토크 유지; 새 명령만 복구 |
| firmware 정지/모터 버스 침묵 0.5초 | 모터 Bus_Watchdog 정지 |
| NaN/invalid command | 거부 + STOP, watchdog 갱신 안 함 |
| 초과 속도 | control/bridge/firmware에서 0.05 rad/s clamp |
| 엔코더 경계 바깥 명령 | STOP, outer 초과는 기존 hardware FAULT |
| Ctrl+C | 가능한 범위에서 STOP 전송; 전달 불가 시 firmware watchdog |

추적만 멈추려면 기존 선택적 `/control/enable` SetBool false를 사용할 수 있다. 안전 기능은 이 서비스와 무관하게 항상 동작한다.
정상 종료는 launch Ctrl+C. 토크 해제가 필요하면 카메라를 지지하고 포트가 닫힌 뒤 miniterm에서 `SUPPORTED_OFF`로 확인한다.
토크 OFF 시 Tilt가 낙하할 수 있다. 하드웨어 FAULT 후에는 지지·원인 점검·전원/reset 복구가 필요하며 bridge는 재연결하지 않는다.
정상 실행 때 firmware를 다시 업로드하거나 prepare/arm/disarm할 필요는 없다.

## 16. Problem 3 Kp test

사전조건: 12절의 실제 영상 오차 감소 방향 확인 완료. `config/test.yaml`의 `kp_compare` A/B 값을 **시험 전에** 기록한다 (이번 작업에서 commit하지 않음) (현재 null — TODO).

```bash
# Kp 시험 때만: control.yaml의 kp_pan/kp_tilt를 A 값으로 저장한 후 8절 build/source.
# 각 회차 정상 실행은 여전히 같은 한 줄이다. B 값도 같은 방식으로 적용한다.
ros2 launch realsense_tracker tracker.launch.py
# 별도 Pi 터미널
python3 tools/tracking_logger.py --run-id kpA_01   # kpA_01..03, kpB_01..03
```

동작 순서(매 회 동일, 바닥 표시 사용): 왼쪽 3 s → 중앙 3 s → 오른쪽 3 s → 중앙 3 s. 상하도 같은 방식으로 같은 회차에 포함한다.
분석: `python3 tools/analyze_tracking.py results/logs/verification/kpA_0*.csv results/logs/verification/kpB_0*.csv --plot --problem P3`.
모터 위치를 측정하지 않으므로 그래프의 명령값을 실제 위치로 해석하지 않는다.

## 17. Problem 4 validation

| 시험 | 횟수 | 방법 | 기록 |
|---|---|---|---|
| 정상 추적 | 30 s 이상 | 9절 실행, `tracking_logger --run-id normal_01` | FPS·RMSE·유효 추적 비율 (20절) |
| 가림 후 재등장 | 2 s × 5회 | 손으로 2 s 가렸다가 시야 안 재등장. `--run-id occlusion_01` 하나에 5회 | `recovery_trials.csv` (영상으로 재등장 시각 판정) |
| 인지 입력 중단 | 1회 이상 | 시험 때만 Pi에서 perception_node 프로세스를 SIGINT로 종료(`pkill -INT -f /perception_node`) | 0.5 s 후 LOST·stop=true, `interruption_trials.csv` |
| 제어 통신 중단 (bridge 측) | 1회 이상 | 시험 때만 control_node 프로세스를 SIGINT로 종료(`pkill -INT -f /control_node`) | bridge command timeout(0.5 s) → STOP, 시리얼 CSV |
| 제어 통신 중단 (보드 측) | 1회 이상 | `pkill -9 -f opencr_node` (bridge가 DISARM을 못 보냄) | 펌웨어 500 ms timeout → 두 축 0 (보드 측 정지 근거) |

움직이지 않는 상태(모터 출력 OFF인 DRY 시험)에서 끊김 처리를 먼저 확인한 뒤 실제 회전 시험을 낮은 속도·제한 범위에서 한다. 실패 회차도 모두 남긴다.
검출률·배경 오검출은 사람 대조 30/10 프레임(문제 1 도구)으로 따로 계산한다 — 노드의 detected 비율과 다르다.

## 18. bag record

사전조건: Pi 저장 공간 확인(`df -h`). 640×480 rgb8 30 fps 영상만 약 27.6 MB/s → 30 s ≈ 0.8 GB. 기록 중 Pi CPU 부하가 추적에 영향을 주는지 상태 로그로 확인한다.

```bash
RUN=success_01   # 소실·복귀 장면은 lost_01
ros2 bag record -o ~/bags/$RUN \
  /camera/camera/color/image_raw /camera/camera/color/camera_info \
  /target /tracking_status /control/pan_tilt_cmd /opencr/bridge_status
ros2 bag info ~/bags/$RUN        # 기간·메시지 수 → recordings/README.md 표에 기록
```

시리얼 로그는 14절 선택적 `csv_path`를 같은 `$RUN`으로 지정한다. 대용량 bag은 Git에 올리지 않고 외부 저장소 링크·체크섬을 [recordings/README.md](recordings/README.md)에 적는다.

## 19. bag replay

사전조건 — **실제 모터 출력 OFF**: ① 정상 launch를 Ctrl+C로 종료 ② 카메라를 지지한 뒤 **모터 전원 OFF 및 OpenCR USB 출력 경로 분리** ③ `ros2 node list`에 opencr_node·control_node가 없음을 확인 ④ **정상 tracker.launch.py는 실행하지 않음** ⑤ 모든 replay 터미널에 격리 도메인:
`export ROS_DOMAIN_ID=99 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` (재생된 `/control/pan_tilt_cmd`가 실제 bridge에 닿지 않게 함. 닿더라도 bridge는 오래된 시각 명령을 거부한다.)

**A. 입력 재처리** — bag 영상만 검출기에 다시 넣고 새 결과를 `/target_replay`로 분리:

```bash
# 터미널 1
ros2 run realsense_tracker perception_node --ros-args --params-file $CFG/tracker.yaml \
  -p camera_config:=$CFG/camera.yaml -p use_depth:=false -p use_sim_time:=true -p publish_debug_image:=true \
  -r /target:=/target_replay
# 터미널 2 (기록: 재처리 결과)
python3 tools/tracking_logger.py --run-id ${RUN}_reprocess --target-topic /target_replay --ros-args -p use_sim_time:=true
# 터미널 3
ros2 bag play ~/bags/$RUN --clock --topics /camera/camera/color/image_raw /camera/camera/color/camera_info
```

재처리 이미지: 터미널 2 대신 `python3 tools/eval_frames.py --scene visible --target-topic /target_replay --no-view --note "replay $RUN"`.

**B. 결과 재분석** — 저장된 `/target`·상태·명령으로 지표를 같은 코드로 다시 계산:

```bash
python3 tools/tracking_logger.py --run-id ${RUN}_reanalysis --ros-args -p use_sim_time:=true
ros2 bag play ~/bags/$RUN --clock --topics /target /tracking_status /control/pan_tilt_cmd
```

## 20. Result analysis

```bash
python3 tools/analyze_tracking.py results/logs/verification/<run_id>.csv --plot            # 화면 출력 + results/plots/<run_id>.png
python3 tools/analyze_tracking.py results/logs/verification/<run_id>.csv --append-metrics --problem P4
python3 tools/eval_score.py results/logs/perception/eval_visible_*.csv results/logs/perception/eval_empty_*.csv
```

같은 run의 실시간 CSV(`success_01.csv`)와 재분석 CSV(`success_01_reanalysis.csv`)를 같은 명령으로 계산해 차이를 report 문제 5에 적는다.

## 21. results 위치

```text
results/
├── images/detection/      정상·없음·가림 원본/마스크/검출 (문제 1, 2026-10-06)
├── images/evaluation/     사람 대조 평가 프레임 visible 30 / empty 10
├── logs/perception/       장면 log.csv, 평가 CSV, perception_node 로그(처리 FPS)
├── logs/control/          ROS 제어 DRY·시리얼 bridge 시험 로그 (2026-10-06, Pi)
├── logs/opencr/           모터 스캔·상태 조회·축별 commission·2축 LIVE 단일 명령 시험
├── logs/verification/     tracking_logger CSV, recovery_trials.csv, interruption_trials.csv (현재 템플릿만)
├── plots/                 analyze_tracking.py 그래프 (현재 없음)
└── metrics.csv            요약 지표 (실측값만, 출처 열 포함)
```

## 22. 현재 미검증 항목 (HARDWARE VERIFICATION TODO)

코드가 있다고 시험이 통과된 것은 아니다. 아래는 실제 장비 결과가 아직 없다.

| 항목 | 상태 |
|---|---|
| Pi 단일 runtime에서 D435 + 인지 + 제어 + bridge 동시 실행, Pi 처리 FPS | NOT VERIFIED |
| Pan/Tilt ID 11/12, 1 Mbps, Protocol 2.0, 시리얼 경로 | VERIFIED 2026-10-06 (scan.log, hardware.md) — 장비 교체 시 재확인 |
| 원시 명령 방향 (Pan + 좌, Tilt + 위 (현재 config; 재확인 필요)) | VERIFIED (commission·LIVE 단일 명령) |
| 폐루프 영상 오차 감소 방향 (direction −1/−1 (2026-10-07 설정)) | NOT VERIFIED |
| 실제 기구 안전 회전 범위 (현재 ±80/±100 counts bench 값) | NOT VERIFIED |
| Kp A/B 값, 속도 상한 최종값 | NOT DECIDED (test.yaml null) |
| 정상 30 s 추적, 가림 5회, /target 중단, 제어 통신 중단, 복구 시간, RMSE | NOT VERIFIED |
| opencr_node 정상 Serial 경로(ROS → 실제 모터) | IMPLEMENTED, NOT VERIFIED (기존 코드의 DRY 경로만 실제 보드 시험; 수정본은 재시험 필요) |
| bag 기록·입력 재처리·결과 재분석, 다른 팀원 재현 | NOT VERIFIED |
| 장시간 침묵 중 ROS_COMMAND_TIMEOUT 원인 (serial_usb_seven) | 원인 미확정 |
