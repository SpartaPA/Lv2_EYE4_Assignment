# Pan/Tilt 제어 인터페이스

## 상태와 적용 범위

2026-10-06 통합 후보 버전. `tracking_controller_2axis`는 새 구현이며 아직
실제 OpenCR 빌드 및 2축 구동 시험을 통과하지 않았다. 기존 단일 축 파서와
각 축 commissioning 결과를 통합 펌웨어의 통과 결과로 간주하지 않는다.

## 시스템과 ROS 연결

- PC: D435, perception_node, control_node.
- Raspberry Pi: opencr_node, USB 전송 및 피드백 수신.
- OpenCR: 두 축 검증, 속도 변환, 위치 감시, 명령 타임아웃.
- 개발 대상 ROS 패키지: `realsense_tracker`; 기존 `tracking_control`은 기준 버전.
- 본 변경은 ROS 노드 또는 메시지 패키지를 구현하지 않는다.

입력 `/target`: `geometry_msgs/msg/PointStamped`.
`point.x=ex`(오른쪽 양수), `point.y=ey`(아래쪽 양수),
`point.z=면적 비율`(0이면 미검출). 공간 XYZ나 depth가 아니다.
유효 검출은 유한한 x,y∈[-1,1], z∈(0,1]이다.
원본 영상 시각과 수신 단조 시각을 함께 검사한다.
중복/역순/오래된 프레임은 복귀 카운터를 갱신하지 않는다.

제어 상태: IDLE/TRACKING/LOST, 최신 연속 검출 3프레임으로 복귀.
표적 타임아웃 초기값 0.5초, 제어 주기 20 Hz.
표적 소실 시 0 명령을 보내며, 보드 타임아웃/FAULT 이후 자동 ARM 금지.

명령 토픽 `/control/pan_tilt_cmd`의 제안/가이드 타입:
`realsense_tracker_interfaces/msg/PanTiltCommand`

```text
std_msgs/Header header
bool stop
float32 pan_velocity_rad_s
float32 tilt_velocity_rad_s
```

상태 토픽 `/tracking_status`: `std_msgs/msg/String`.
이 메시지 패키지의 실제 구현 여부는 이 아카이브로 확인되지 않았다.
bridge는 오래된 마지막 명령을 반복 전송하지 않아야 한다.
ROS bag 재생은 `dry_run=true`, 시리얼 포트를 열지 않는 방식으로 시행한다.

## 부호와 단위

방향은 카메라 뒤에서 정면을 보는 기준이다.

| 축 | ID | 모터 양의 명령 | 영상 오차에 대한 계수 |
|---|---:|---|---:|
| Pan | 11 | 좌측 | -1 |
| Tilt | 12 | 아래쪽 | +1 |

control_node에서 `pan=-kp_pan*ex`, `tilt=+kp_tilt*ey`를 계산한다.
ROS 명령과 USB VEL은 **이미 모터 부호를 적용한 rad/s**다.
bridge와 OpenCR는 부호를 다시 반전하지 않는다.
데드밴드, 최신성, 속도 제한은 제어 노드에서 적용하고 보드에서도 제한한다.

OpenCR에서만 rad/s를 원시 Goal_Velocity 단위로 변환한다.
1 단위 = 0.229 rpm ≈ 0.0239808 rad/s.
최근접 정수로 반올림하므로 작은 비영 속도도 0으로 양자화될 수 있다.
통합 후보 입력 한계는 축별 ±0.05 rad/s, 최종 출력은 최대 ±2 단위다.
이는 좁은 범위의 시험 설정이며 최종 추적용 속도 승인이 아니다.

## 통신과 실행 모드

- USB: 115200 baud, 8N1.
- DYNAMIXEL: 1000000 baud, Protocol 2.0.
- 모델: 두 축 XM430-W350, 모델 번호 1020.
- `ENABLE_MOTOR_OUTPUT=0` 기본값: MODE=DRY, 모터 버스를 초기화/읽기/쓰기하지 않는다.
- `ENABLE_MOTOR_OUTPUT=1`: MODE=LIVE, 실제 모터에 접근한다.
- YAML은 호스트용 설정이며 펌웨어가 읽지 않는다. 펌웨어 상수와 일치 여부를 검토해야 한다.

## ASCII 명령

대소문자 구분, LF 종료, CRLF 허용. 최대 길이 63바이트.
비ASCII/제어문자(줄 종료 제외) 또는 과대 입력은 다음 LF까지 버린다.

| 명령 | 동작 |
|---|---|
| CHECK | 초기 1회: 모델, 모드, firmware≥38, 두 축 토크 OFF, watchdog=0, 중립 검사 |
| HOLD | 두 축 목표속도 0 선기록, bus watchdog 설정 후 토크 ON; 정지 확인 후 DISARMED |
| ARM | HOLD 완료 상태에서만 구동 허가, 300 ms 타이머 시작 |
| VEL p t | 두 값 모두 형식/범위 검사 후 적용. 유효하게 수락한 경우만 타이머 갱신 |
| STOP | 두 축 목표속도 0, ARM 유지, ARM 상태라면 명령 타이머 갱신 |
| DISARM | 두 축 목표속도 0, 구동 허가 해제, 토크 유지 |
| STATUS | 캐시된 상태/피드백, 타이머와 모터 버스에 영향 없음 |
| SUPPORTED_OFF | 사용자가 기계적 지지를 확인한 뒤 두 축 토크 OFF. 다음 세션은 reset/CHECK 필요 |

반복 ARM은 거부하며 heartbeat로 사용할 수 없다.
STOPPING 동안 VEL은 거부하며 타이머를 갱신하지 않는다.
HOLD/STOP/DISARM의 ACK는 정지 **요청**이다.
실제 저속 피드백을 확인하면 `EVENT STOPPED TORQUE_RETAINED`를 보고한다.
이 이벤트도 물리적 정지 지연 측정이나 안전 인증을 뜻하지 않는다.

## 위치와 제한

CHECK 때 수동으로 검증된 중립 자세에 놓아야 한다.
Pan 기준 3078±20, Tilt 기준 0(modulo 4096)±20, 속도 0을 요구한다.
Tilt의 modulo는 시작 자세 확인에만 사용한다. 운전 중 원시 위치가 불연속적으로
바뀌면 reset으로 의심하고 FAULT를 유지한다. 다회전 homing을 제공하지 않는다.

세션 위치 기준은 Pan=3078, Tilt=CHECK 당시 가장 가까운 4096 경계다.
양 축 경계: ±80 counts에서 바깥 방향 명령을 정지하고 DISARM.
±100 counts에 도달하면 FAULT. ±70 counts 바깥에서는 ARM 거부.
정지 중이 아닌 영속도 축이 hold 기준에서 20 counts 넘게 변하면 FAULT.
이 수치는 작은 bench 시험 범위이며 기구적 전체 가동 범위가 아니다.
현재 펌웨어는 경계/FAULT에서 자동 복귀 운동을 하지 않는다.

## 타임아웃과 오류

- 보드 유효 명령 타임아웃 300 ms: 두 축 0 요청, DISARM, 토크 유지.
- 모터 bus watchdog 200 ms: 모든 instruction packet이 갱신하므로 명령 최신성을 대신하지 않는다.
- 피드백은 약 20 ms마다 읽으며 실제 주기는 SDK 통신 시간에 영향을 받는다.
- 두 값을 함께 검증하지만 두 모터 쓰기는 순차적이다. 물리적 원자 실행을 보장하지 않는다.
- 한 쓰기라도 실패하면 두 축 0을 각각 시도하고 FAULT를 고정한다.
- FAULT 이후 자동 버스 polling을 중단하여 watchdog 만료를 방해하지 않는다.
- 중력 부하 때문에 일반 오류 경로에서 자동 토크 OFF를 하지 않는다.
- 통신/전원/모터 자체 고장 시 정지 또는 토크 유지를 보장할 수 없다. catch가 필요하다.
- 두 축 정지 피드백이 500 ms 안에 확인되지 않으면 FAULT.
- SUPPORTED_OFF 후 reset까지 재구동 불가. 포트 재연결이나 노드 재시작으로 자동 ARM 금지.

## 상태 응답

```text
STATE DISARMED MODE=LIVE ARMED=0 GOAL=0,0 POS=3078,4096 VEL=0,0 TORQUE=1,1 AGE_MS=3 T_MS=1234
```

GOAL/VEL은 원시 속도 단위, POS는 원시 encoder, AGE_MS는 캐시 나이,
T_MS는 보드 millis다. MODE=DRY 값은 모의 값이다.
FAULT 응답 후 캐시 값은 현재 토크/정지 증명이 아니다.
USB 출력은 best-effort이므로 ACK/이벤트가 유실될 수 있다.
ARM/비영 VEL을 ACK 유실 때문에 자동 재전송하지 않는다.

## 과거 기준 버전

`tracking_controller` 및 기존 test_parser*.py는 단일 값 VEL 기준이다.
그대로 보존하며 새 통합 펌웨어에는 `test_2axis_dry.py`를 사용한다.
