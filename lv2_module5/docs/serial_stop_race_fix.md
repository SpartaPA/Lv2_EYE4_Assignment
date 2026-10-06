# Serial bridge STOP 복귀 경쟁 조건 수정

## 발견한 문제

serial ROS 시험에서 target silence 이후 검출 복귀 시 `BOARD_ERR STOPPING`이 발생했다.
bridge는 정상 STOP 이후 논리적 ARM 상태를 유지하지만, 이전 STOP의 완료 이벤트가
새 STOP 전송과 겹치면 새 정지 동작이 완료되기 전에 VEL을 전송할 수 있었다.
펌웨어의 `ERR STOPPING` 거부 및 bridge의 FAULT 래치는 정상 보호 동작이다.

## 수정

- EVENT STOPPED만으로 새 VEL 전송을 허용하지 않는다.
- 정지 중에는 새 STOP을 반복하지 않고 STATUS 응답으로 완료를 확인한다.
- 정지 중 STATUS 조회 주기는 20 ms이다. 그 외에는 기존 100 ms를 유지한다.
- 조회한 STATUS가 ARMED, GOAL=0,0 및 VEL=0,0일 때 정지 완료를 확인한다.
- 이후 신선한 ROS 명령으로만 VEL을 전송한다.
- ARM 자동 재시도, 자동 재연결 및 LIVE 모드 지원을 추가하지 않는다.
- 펌웨어와 watchdog 제한은 변경하지 않는다.

## 검증

- 두 가지 회귀 시험: 이전 STOPPED 이벤트가 새 STOP을 해제하지 않는지,
  조회한 STATUS 확인 전 VEL을 거부하는지 검사한다.
- serial 단위 시험 15개와 기존 control 단위 시험 5개: 총 20개.
- 실제 DRY 펌웨어를 실행하는 PTY에서 10 ms bridge tick으로 STOP/복귀를 20회 반복한다.
- Raspberry Pi에서 별도 프로세스 ROS 시험을 다시 실행해야 최종 판정할 수 있다.

## 증거 관리

이전 실패 로그를 보존한다. 재시험은 새로운 실행 디렉터리에 저장한다.
이 시험은 native DRY 펌웨어 대상이며 실제 OpenCR 또는 모터 검증이 아니다.
