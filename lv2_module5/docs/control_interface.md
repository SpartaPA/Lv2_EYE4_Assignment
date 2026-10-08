# 제어·Serial 인터페이스 — 수정본

모든 ROS 노드는 Raspberry Pi에서 실행한다. PC는 SSH 접속용이다.

| 계층 | 책임 |
|---|---|
| perception | HSV/Contour, 원본 영상 header.stamp, 영상 처리마다 /target 1회 |
| control_core/control_node | Kp, direction, deadband, 속도 clamp, IDLE/TRACKING/LOST, target timeout, 3프레임 복귀 |
| opencr_node/serial_core | port/baud 연결, 명령 신선도 검사, 1회 전송, command timeout STOP, Serial 오류 종료 |
| OpenCR | 실제 encoder 경계, 속도 clamp, 명령 watchdog, 모터 Bus_Watchdog, 하드웨어 오류 STOP |

## /target

geometry_msgs/msg/PointStamped. x=ex=(cx−W/2)/(W/2), y=ey=(cy−H/2)/(H/2), z=area_ratio.
오른쪽 ex+, 아래 ey+. Depth는 z에 넣지 않는다. 미검출 정상 영상도 x=y=z=0으로 발행한다.
영상 원본 stamp 유지, QoS best-effort/depth 1 및 control 구독 호환 유지.
z=0/invalid/stale/duplicate 입력이면 LOST+STOP, 이전 좌표 재사용 금지.
LOST/IDLE에서 fresh valid target 3프레임 연속 후 TRACKING. TRACKING만 non-zero command를 발행한다.

## command 및 값

`/control/pan_tilt_cmd`: 기존 PanTiltCommand, header=생성 시각, stop=true이면 두 축 0, 단위 rad/s.
정상 발행은 단일 20 Hz(0.05초) 타이머이며 LOST 전환은 즉시 STOP을 추가 발행할 수 있다.
정상 Kp=0.3/0.3, direction=−1/−1(재조립 기록), deadband=0.03/0.03, clamp=0.05/0.05 rad/s.
방향은 control에서만 적용한다. dry 테스트는 고정 Kp=0.1, direction=−1/+1, clamp=0.05를 사용한다.
Kp 2종 × 각 3회 변경·비교 가능. runtime 값은 config/control.yaml을 따른다.

## Serial

기존 config/opencr_live.yaml 이름 유지. 필수 설정 port=/dev/serial/by-id/..., baud=115200, command_timeout_sec=0.5.
csv_path는 선택적 증빙이며 mode/enable flag가 아니다.
프로토콜은 `VEL p t`, `STOP`, `STATUS`; 토크 해제용 `SUPPORTED_OFF`는 카메라 지지 후 종료·정비 절차에서만 사용한다.
펌웨어는 초기 모터 점검/영속도 토크 유지를 자동 수행한다. runtime DRY/LIVE handshake, CHECK/HOLD/ARM/DISARM 명령 및 서비스 없음.
STATE는 BOOT/READY/STOPPING/FAULT, 실제 GOAL/POS/VEL/TORQUE/AGE_MS/T_MS를 제공한다.
ACK/STATE/EVENT를 구동 허가 state machine으로 사용하지 않는다. STATUS는 firmware 명령 timer를 갱신하지 않는다.
시작 중 입력 명령은 저장하지 않는다. 준비된 후의 fresh 메시지만 한번 보낸다.
Serial 오류/보드 응답 침묵/실제 hardware FAULT는 가능한 STOP 후 ERROR 종료하고 재연결하지 않는다.

## 자동 안전정지

| 계층 | timer 갱신 | timeout | 동작 |
|---|---|---|---|
| control | fresh target | 0.5초 | LOST+STOP |
| bridge | fresh control command | 0.5초 | STOP, 새 명령만 복구 |
| firmware | 유효 VEL/STOP | 500 ms | 영속도·토크 유지, 새 명령만 복구 |
| 모터 Bus_Watchdog | 모터 bus packet | 25×20 ms=500 ms | 모터 자체 정지 |

0.5초는 모터를 0.5초만 구동한다는 뜻이 아니다. 20 Hz 명령은 0.05초마다 timer를 갱신한다.
NaN/Inf/invalid/오래된/역순 명령은 거부하고 STOP, invalid 입력은 watchdog을 갱신하지 않는다.
종료 때 가능한 STOP. Serial 전달 불가 시 firmware watchdog이 정지한다. 과거 non-zero 재송신/복원 없음.
bridge STATUS 조회는 0.1초, tick은 0.01초이다. 초기 모터 확인 대기 3초는 기존 약1.25초 초기화 실측의 여유이며 안전정지 timeout과 별개다.
펌웨어 엔코더 중립: Pan=3078, Tilt=0 mod 4096. ±80 counts에서 바깥 명령 STOP, 안쪽 fresh 명령 허용, ±100 counts부터 FAULT.
모두 기존 bench 값이며 기구 승인 최대각도가 아니다. 위치 급변/버스 오류/정지 미확인은 기존 하드웨어 FAULT를 유지한다.

## 모터 없는 시험

Problem2는 기존 test_control_dry + dry_bridge이며 Serial 포트를 열지 않는다.
Problem5는 정상 tracker.launch를 사용하지 않고 모터 전원 OFF·OpenCR USB 분리 후 perception/logger/bag만 실행한다.
기존 commissioning/legacy와 results 증거는 보존한다. 과거 DRY/LIVE/ARM 기록은 구형 구현에 대한 기록이다.
