# Serial bridge STOP 복귀 수정 및 ROS PTY 시험

- 시험일: 2026-10-06
- 환경: Raspberry Pi, ROS 2 Lyrical
- 대상: 제어 노드 → serial bridge → native DRY 펌웨어
- 원본 결과: [serial_ros_tests.log](serial_ros_tests.log)
- 실제 OpenCR 및 모터 출력은 사용하지 않았다.

## 확인 결과

- 중심 및 Pan/Tilt 방향 입력 시험 통과
- 미검출 시 STOP 및 논리적 ARM 유지 확인
- 신선한 검출 3프레임 후 추가 ARM 없이 VEL 복귀 확인
- 검출 publisher 침묵 시 LOST 및 STOP 확인
- 침묵 이후 복귀 시 기존 ERR STOPPING 문제 재발 없음
- 제어 프로세스 종료 시 DISARM 시도 및 명령 timeout 래치 확인
- timeout 이후 자동 재ARM 없음
- 최종 결과: ALL SERIAL ROS PTY CHECKS PASSED; FIRMWARE_MODE=DRY

재ARM 요청의 SERVICE 거부 메시지는 의도한 보호 동작이다.

## 검증 범위

가상 시리얼 PTY를 통한 별도 프로세스 통합 시험을 통과했다.
실제 USB 통신, OpenCR의 DRY 실행, LIVE bridge 모터 출력,
PC–Pi 통신 및 실제 카메라 추적은 이 시험으로 검증하지 않았다.
