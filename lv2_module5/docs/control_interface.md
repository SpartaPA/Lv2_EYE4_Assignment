# Pan/Tilt 제어 인터페이스

## 1. 목적 및 구현 상태

담당: 조민혁 — 제어

팀 개발 가이드에 따라 RealSense D435를 장착한 Pan/Tilt 2축 추적 시스템의 입력, 출력, 상태 및 정지 규칙을 정의한다.

이 문서는 다음을 구분한다.

| 구분 | 상태 |
|---|---|
| 팀 가이드의 ROS 2 인터페이스 | 구현 기준 |
| 기존 단일 속도 OpenCR 파서 | 구현 및 시험 완료 |
| 2축 시리얼 프로토콜 | tracking_controller_2axis 구현 및 초기 DRY/LIVE 시험 완료 |
| 실제 DYNAMIXEL 제어·피드백 | 중립 부근 6개 초기 LIVE 시험 통과, 전체 고장 시험 미완료 |
| 실제 정지·각도·속도 제한 | 미검증 |
| ROS 제어 및 dry bridge | 본 후보 구현 추가, repository 별도 프로세스 시험 대기 |
| 전체 2축 카메라 추적 | 미검증 |

검증하지 않은 하드웨어 값은 임의로 확정하지 않는다.

## 2. 시스템 구성과 책임

| 구성 요소 | 실행 위치 | 책임 |
|---|---|---|
| realsense2_camera | PC | Color, Depth, CameraInfo 발행 |
| perception_node | PC | 검출, 정규화 오차, 미검출 정보 발행 |
| control_node | PC | 입력 신선도, 상태 전이, 2축 P 제어, 정지 판단 |
| opencr_node | Raspberry Pi | ROS 2 명령 수신, 시리얼 변환, 통신 오류 처리 |
| OpenCR 펌웨어 | OpenCR | 명령 검사, 단위 변환, 모터 제어, 제한, 보드 타임아웃 |
| DYNAMIXEL | Pan/Tilt 기구 | 실제 구동 및 피드백 |

ROS 노드는 `realsense_tracker` 패키지에 구현한다.

- 제어: `control_node.py`
- 시리얼 연결: `opencr_node.py`
- 메시지: `realsense_tracker_interfaces/msg/PanTiltCommand`

launch, package 의존성, 메시지 생성 설정은 통합 담당과 조율한다.

## 3. ROS 2 입력: /target

메시지 형식: `geometry_msgs/msg/PointStamped`

| 필드 | 의미 |
|---|---|
| header.stamp | 원본 영상 시각 |
| header.frame_id | 영상 좌표계 식별자 |
| point.x | 정규화 수평 중심 오차 ex |
| point.y | 정규화 수직 중심 오차 ey |
| point.z | 컨투어 면적 / 영상 면적 |
| point.z=0 | 미검출 |

정규화:

```text
ex = (cx - W/2) / (W/2)
ey = (cy - H/2) / (H/2)
area_ratio = contour_area / (W × H)
```

- 오른쪽 오차는 양수다.
- 아래쪽 오차는 양수다.
- x/y/z는 실제 3차원 위치가 아니다.
- point.z에 거리 값을 넣지 않는다.
- Depth는 거리 유효성 확인과 기록에 사용하며 별도 규약으로 구분한다.

인지 노드는 처리한 영상마다 발행하며, 정상 영상에서 미검출인 경우에도 z=0을 발행한다. 이전 검출 좌표를 새로운 검출 결과로 재사용하지 않는다.

촬영 시각을 알 수 없어 영상 수신 시각을 사용하면 그 사실을 문서에 기록한다.

입력 QoS:

- Reliability: best effort
- History: keep last
- Depth: 1
- Durability: volatile

## 4. 입력 유효성 및 신선도

유효 검출 조건:

- x, y, z가 모두 유한한 값이다.
- x와 y는 [-1, 1] 범위다.
- z는 (0, 1] 범위다.
- 원본 시각이 신선하며 중복 또는 역순 프레임이 아니다.

z=0은 정상적인 미검출 신호다. 이때 x/y로 추적 명령을 계산하지 않는다.

잘못된 값, 오래된 입력 또는 미검출 입력을 받으면 두 축 정지를 요청하고 복구 프레임 수를 초기화한다.

호스트의 수신 경과 시간은 단조 시계로 측정한다. 마지막 유효하고 신선한 입력을 기준으로 기본 0.5초의 입력 타임아웃을 적용한다.

메시지가 계속 도착하더라도 오래된 영상을 반복한 경우 정상 입력으로 취급하지 않는다. 원본 시각 검증의 최대 허용 지연과 미래 시각 허용 범위는 통합 전에 설정으로 확정한다.

서로 다른 장치의 시각을 비교하는 경우 시계 동기화를 확인한다. bag 재현에서는 실제 모터 출력을 끄고 재생 시계 정책을 별도로 적용한다.

## 5. 제어 계산

출력 물리량: 각 축의 목표 각속도, 단위 rad/s

```text
pan_velocity =
  clamp(pan_direction × kp_pan × ex,
        -pan_speed_limit,
        +pan_speed_limit)

tilt_velocity =
  clamp(tilt_direction × kp_tilt × ey,
        -tilt_speed_limit,
        +tilt_speed_limit)
```

- direction은 각 축마다 +1 또는 -1이다.
- 실제 영상 오차가 감소하는 방향을 제한된 움직임으로 검증한다.
- 정규화 오차는 무차원이므로 Kp의 단위는 rad/s이다.
- 축별 데드밴드 안에서는 해당 축의 명령을 0으로 한다.
- 속도 제한과 각도 제한을 축별로 적용한다.
- 각도 경계에서 바깥 방향의 명령을 허용하지 않는다.
- 유효한 위치 피드백이 없으면 움직임을 허용하지 않는다.

영상 오차에서 모터 방향으로의 부호 변환은 control_node에서 한 번만 적용하는 것을 제안한다. opencr_node와 펌웨어에서 같은 부호를 다시 곱하지 않는다.

설정 파일에 direction 정보가 중복되는 경우 기준 설정과 참조 관계를 통합 담당과 확정한다.

## 6. 추적 상태

토픽: `/tracking_status`

메시지 형식: `std_msgs/msg/String`

| 상태 | 조건 및 동작 |
|---|---|
| IDLE | 시작 또는 명시적 추적 중지. 두 축 정지 요청 |
| TRACKING | 신선한 검출 입력으로 제한된 추적 명령 계산 |
| LOST | 미검출, 잘못된 입력 또는 입력 타임아웃. 두 축 정지 요청 |

- 미검출 첫 프레임부터 두 축 정지를 요청한다.
- 신선한 검출 프레임 3개가 연속 확인되면 TRACKING으로 진입 또는 복귀한다.
- 복구 횟수는 제어 타이머 호출이 아니라 새 영상 메시지를 기준으로 센다.
- 미검출, 무효 입력 또는 타임아웃이 발생하면 복구 횟수를 초기화한다.
- 명시적으로 추적을 중지한 상태에서는 검출만으로 자동 재개하지 않는다.

추적 상태와 하드웨어 활성화 상태는 별도로 관리한다. TRACKING 상태라도 하드웨어가 비활성화되어 있으면 실제로 움직이지 않는다.

## 7. ROS 2 출력: /control/pan_tilt_cmd

메시지 형식:

```text
realsense_tracker_interfaces/msg/PanTiltCommand
```

필드:

```text
std_msgs/Header header
bool stop
float32 pan_velocity_rad_s
float32 tilt_velocity_rad_s
```

| 필드 | 의미 |
|---|---|
| header.stamp | 명령 생성 시각 |
| header.frame_id | 명령 기준에 대한 팀 규약. 기준 미정 시 임의의 TF 프레임을 지정하지 않음 |
| stop | true이면 두 축 정지 |
| pan_velocity_rad_s | Pan 목표 각속도 |
| tilt_velocity_rad_s | Tilt 목표 각속도 |

규칙:

- Velocity Mode를 기준으로 한다.
- stop=true이면 두 속도 필드 값과 관계없이 두 축을 정지시킨다.
- stop=false인 경우에도 비활성화 상태에서는 움직임을 허용하지 않는다.
- 두 속도는 유한한 값이어야 한다.
- 명령 한 건의 두 축 값을 함께 처리한다.
- 명령값과 실측 속도·위치는 구분한다.

초기 발행 주기 제안: 20 Hz. 실제 구현값과 변경 이유를 기록한다.

명령 토픽의 QoS와 허용 명령 나이는 통합 담당과 확정하고 PC–Pi 실제 전달 시험으로 확인한다. 오래된 명령이 큐에 쌓여 뒤늦게 실행되지 않도록 한다.

## 8. 활성화 및 정지

현재 PanTiltCommand에는 ARM 필드가 없다. 따라서 stop=false를 활성화 요청으로 해석하지 않는다.

하드웨어 활성화 경로는 별도의 명시적 조작으로 제공하며, ROS 서비스 또는 운용 명령 등 구체적인 방식은 통합 전에 합의한다.

| 상황 | 동작 |
|---|---|
| 시작 | 요청 속도 0, 비활성화 |
| 명시적 ARM | 조건 확인 후 속도 0으로 활성화 |
| 정상 목표 소실 | 두 축 정지, 3프레임 복구 조건 적용 |
| STOP | 두 축 속도 0, 논리적 활성화 상태 유지 |
| DISARM | 두 축 정지 후 논리적 비활성화 |
| 보드 명령 타임아웃 | 두 축 정지 및 비활성화 |
| 통신·피드백 오류 | 정지 요청 및 오류 상태, 자동 재활성화 금지 |

DISARM은 논리적 제어 비활성화를 뜻한다. 모터의 Torque Enable을 무조건 끄는 것과 동일하지 않다.

특히 Tilt 축은 토크 해제 시 카메라가 중력으로 내려갈 수 있으므로 실제 정지, 자세 유지, 토크 해제 정책을 구분하여 시험한다.

## 9. 타임아웃 계층

| 계층 | 감시 대상 | 기준 |
|---|---|---|
| control_node | 신선한 /target 입력 | 기본 0.5초 |
| opencr_node | 신선한 PC 명령 | 별도 임계값 확정 필요 |
| OpenCR | 수락한 시리얼 제어 명령 | 기존 기준 버전 0.3초 |

opencr_node는 PC 명령이 끊겼을 때 마지막 비영 속도를 반복 전송하여 보드 워치독을 계속 갱신하면 안 된다.

오래된 명령, 중복 명령 및 통신 복구 후 지연 도착한 명령의 처리 정책을 정한다. 통신 장애 후에는 자동 ARM을 보내지 않는다.

보드 타임아웃은 마지막으로 수락한 제어 명령부터의 경과 시간을 기준으로 한다. 잘못된 명령과 상태 조회는 타이머를 갱신하지 않는다.

## 10. USB 시리얼 연결

연결: Raspberry Pi ↔ OpenCR USB

설정: 115200 baud, 8 data bits, no parity, 1 stop bit

현재 확인된 장치:

```text
/dev/serial/by-id/usb-ROBOTIS_OpenCR_Virtual_ComPort_in_FS_Mode_FFFFFFFEFFFF-if00
```

장치 교체 시 실제 경로를 다시 확인한다. 한 번에 하나의 프로그램만 포트를 사용한다.

USB 시리얼 baud rate와 DYNAMIXEL bus baud rate는 다른 설정이다.

## 11. 보존된 과거 단일 속도 프로토콜

기존 시험 코드의 명령:

| 명령 | 동작 |
|---|---|
| ARM | 내부 속도 0으로 활성화 |
| VEL <value> | 활성화 상태에서 내부 요청 속도 설정 |
| STOP | 내부 속도 0, 활성화 상태 유지 |
| DISARM | 내부 속도 0 및 비활성화 |
| STATUS | 내부 상태 조회 |

현재 이 명령들은 모터를 제어하지 않는다.

기존 파서의 응답:

```text
ACK ARM
ACK VEL
ACK STOP
ACK DISARM
ERR VALUE
ERR RANGE
ERR DISARMED
ERR COMMAND
ERR LINE
READY DISARMED
STATE DISARMED ZERO
STATE ARMED ZERO
STATE ARMED NONZERO
EVENT TIMEOUT DISARMED
```

## 12. 구현된 2축 펌웨어 프로토콜

대상: tracking_controller_2axis. 초기 DRY 및 6개 LIVE 시험 통과 기록은
integration_dry_20261006_140439와 integration_live_20261006_141057에 있다.
ROS opencr_node의 실제 시리얼 연결은 아직 구현하지 않았다.

| 명령 | 동작 |
|---|---|
| CHECK | reset 후 모델/모드/토크 OFF/중립 확인 |
| HOLD | 영속도 및 watchdog 설정 후 토크 ON, 정지 확인 대기 |
| ARM | HOLD 완료 및 정지 상태에서 1회 구동 허가 |
| VEL p t | 모터 부호를 적용한 두 축 rad/s, 각 ±0.05 이내 |
| STOP | 두 축 영속도 요청, 구동 허가 유지 |
| DISARM | 두 축 영속도 요청, 구동 허가 해제, 토크 유지 |
| STATUS | 캐시된 상태와 피드백 조회 |
| SUPPORTED_OFF | 기계적 지지 확인 후 토크 해제, reset 필요 |

LF 종료 ASCII, CRLF 허용, 최대 63자다. 두 값을 모두 검사한 후 순차 쓰기한다.
형식/범위 오류 또는 거부된 명령은 유효 명령 타이머를 갱신하지 않는다.
ARM은 타이머를 시작하며 이미 ARM 상태에서 반복 ARM은 거부한다.
수락한 VEL과 ARM 상태의 STOP은 타이머를 갱신한다. STATUS는 갱신하지 않는다.
보드 명령 타임아웃은 300 ms이며 두 축 영속도와 DISARM을 요청하고 토크를 유지한다.
모터 bus watchdog은 200 ms이며 모든 instruction packet이 갱신하므로 별도 보호다.
ACK는 정지 요청이고 EVENT STOPPED TORQUE_RETAINED는 정지 피드백 확인 이벤트다.
FAULT 후 STATUS 피드백은 오래된 캐시일 수 있다. GOAL=0,0은 실제 정지 증명이 아니다.
FAULT/timeout 후 호스트가 자동 ARM을 전송하지 않는다.

## 13. 모터 피드백 및 오류

모터 제어 전에 다음 항목의 전달 형식과 갱신 주기를 합의한다.

- Pan/Tilt 실측 위치와 속도
- 피드백 유효성 및 수신 시각
- 활성화 상태
- 모터 통신 오류
- 보드 타임아웃
- 각도 제한 도달
- 하드웨어 오류

명령 수락 ACK와 실제 모터 동작 확인은 구분한다.

진단 출력이 누락될 수 있으므로 단일 ACK의 존재만으로 정상 상태를 판단하지 않는다. 상태와 피드백의 신선도를 별도로 확인한다.

## 14. 설정 파일

| 파일 | 주요 내용 |
|---|---|
| `config/control.yaml` | 축별 Kp, 속도·각도 제한, 데드밴드, 방향, 입력 타임아웃, 복구 프레임 수 |
| `config/opencr.yaml` | 포트, USB baud, DYNAMIXEL baud·프로토콜, 두 모터 ID, 보드 타임아웃 |
| `config/test.yaml` | 시험 시간, 가림 횟수, Kp 반복 횟수, 복구 판정 기준 |

실제 설정 키와 ROS 파라미터 로딩 방식은 통합 담당과 일치시킨다.

확인된 하드웨어(카메라 뒤에서 정면을 보는 기준):

| 축 | 모델 | ID | 모터 양의 방향 |
|---|---|---:|---|
| Pan | XM430-W350-T | 11 | 좌측 |
| Tilt | XM430-W350-T | 12 | 아래쪽 |

DYNAMIXEL bus는 1000000 baud, Protocol 2.0이다. USB는 115200 baud다.
Pan 기준은 3078, Tilt 중립은 0 modulo 4096이다. 수동 측정 위치는 기구적 최대 한계가 아니다.
Tilt 토크 해제 시 카메라가 내려가므로 토크 해제 전에 기계적으로 지지한다.
정상 정지는 영속도와 토크 유지다. 통신/전원/모터 고장 시 자세 유지는 보장하지 않는다.
전체 경계/정지 지연/통신 고장 시험과 실제 영상 오차 감소 검증은 아직 미완료다.

## 15. 검증 기준

- 모터 출력 없이 ROS 2 모의 입력 7개를 확인한다.
- 두 축의 실제 영상 오차 감소 방향을 검증한다.
- 미검출 및 입력 타임아웃 시 두 축 정지를 검증한다.
- PC 명령 중단, Pi 제어 프로그램 종료 및 보드 타임아웃에 대한 실제 정지를 확인한다.
- 신선한 검출 3프레임 후 정상 목표 소실에서 복구한다.
- 통신 장애 후에는 명시적 재활성화를 요구한다.
- Kp_pan/Kp_tilt 세트 A/B를 사전에 정하고 각 3회 비교한다.
- 수평·수직 오차, 상태, 두 축 명령과 단위를 기록한다.
- bag 재현 시 실제 하드웨어 출력을 비활성화한다.

세부 시험과 증거는 [제어 시험 계획](control_test_plan.md), 빌드·업로드 절차는 [OpenCR README](../firmware/opencr/README.md)를 참고한다.
## 2026-10-06 ROS dry 구현 단계

`realsense_tracker`의 control_node 및 opencr_node를 구현 후보로 추가했다.
control_node는 영상 오차에 모터 방향을 한 번 적용한다(Pan -1, Tilt +1).
opencr_node는 현재 dry_run=true 전용이며 시리얼 포트를 열지 않는다.
dry_run=false이면 시작을 거부한다. 시리얼 변환·ARM·피드백 처리는 아직 미구현이다.
`/opencr/dry_status`의 String(JSON)은 모의 명령 처리 상태이며 모터 피드백이 아니다.
ROS parameter 설정은 패키지의 `config/control_dry.yaml`을 사용한다.
기존 `lv2_module5/config/opencr.yaml`은 plain host 계약이며 자동 로드하지 않는다.
표적 시각 검증: 최대 지연 0.5초, 미래 시각 허용 0초. 단조 수신 시간도 검사한다.
dry bridge 명령 신선도/수신 타임아웃은 0.15초다.
현재 mock 기본 Kp는 양 축 0.1, deadband 0.03, 속도 상한 0.05 rad/s다.
이는 A/B 게인 실험 완료나 실제 추적용 승인 설정을 의미하지 않는다.
독립 workspace 모의 시험 통과와 본 repository 시험 통과를 구분한다.
검증 절차: [ROS dry 통합 시험](ros_control_dry_steps.md).
