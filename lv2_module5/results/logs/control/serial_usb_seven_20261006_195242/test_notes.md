# 실제 OpenCR USB DRY 7개 입력 시험 및 장시간 소실 중 timeout

- 시험일: 2026-10-06
- 연결: Raspberry Pi ROS controller → serial bridge → 실제 OpenCR USB
- 펌웨어: MODE=DRY
- 입력: 하나의 ROS publisher에서 입력을 변경
- 실제 모터 출력: 비활성화

## 확인 결과

| 시험 | 결과 |
|---|---|
| 중심 | TRACKING, 목표 속도 0,0 |
| 오른쪽 목표 | TRACKING, 목표 속도 -2,0 |
| 왼쪽 목표 | TRACKING, 목표 속도 2,0 |
| 아래쪽 목표 | TRACKING, 목표 속도 0,2 |
| 위쪽 목표 | TRACKING, 목표 속도 0,-2 |
| 미검출 | LOST, 목표 속도 및 모의 속도 0,0 |
| target 발행 중단 | LOST, 목표 속도 및 모의 속도 0,0 확인 |
| 침묵 이후 복귀 | 기존 bridge FAULT 때문에 완료하지 못함 |
| controller 종료 시험 | 기존 FAULT와 분리하여 검증하지 못함 |
| 최종 board STATUS | DISARMED MODE=DRY, GOAL=0,0, VEL=0,0 |

## 실패 기록

target 발행 중단 약 456.6초 후 bridge에서 ROS_COMMAND_TIMEOUT이 발생했다.
right 입력 재개는 최초 fault 약 204.9초 이후였다.
따라서 입력 재개가 최초 fault를 발생시켰다고 판단하지 않는다.

fault 직전 board는 정지 완료 이벤트와 정상 영속도 STATUS를 반환했다.
마지막 STATUS 수신과 fault 사이에 약 138 ms의 로그 공백이 있었다.
bridge는 fault 발생 직후 DISARM을 전송했다.
이 전송 기록 자체는 board 수신 완료를 증명하지 않는다.
시험 종료 후 별도 STATUS에서 disarmed 및 영속도를 확인했다.

## 판정 및 한계

7개 입력의 방향·소실·정지 상태를 관찰했다.
장시간 target 침묵 중 발생한 controller-command timeout의 원인은 미확정이다.
전체 통합 시험 통과로 판정하지 않는다.
DRY 위치·속도·토크 값은 실제 모터 측정값이 아니다.

## 다음 작업

bridge timer 간격, controller 명령 수신 간격 및 timestamp 나이를 기록하여
controller, DDS 또는 bridge 실행 지연을 구분한다.
기존 timeout을 유지하고 장시간 침묵 및 복귀 시험을 다시 수행한다.
