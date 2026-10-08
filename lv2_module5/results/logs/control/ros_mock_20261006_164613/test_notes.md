# ROS Pan/Tilt 모의 입력 시험

- 시험일: 2026-10-06
- 실행 환경: Raspberry Pi, ROS 2 Lyrical
- 대상: 독립 workspace의 control_mock_validation 후보 구현
- 모터 출력: 비활성화, 시리얼 포트 열지 않음

## 결과

7개 모의 입력 시험을 모두 통과했다.
중심, 수평 ±0.4, 수직 ±0.4 입력의 두 축 속도와 부호를 확인했다.
미검출 및 표적 입력 0.5초 중단 시 LOST와 영속도 명령을 확인했다.
신선한 검출 3프레임 이후 TRACKING 복귀를 확인했다.
제어 출력 중단 시 dry sink의 명령 타임아웃과 영속도를 확인했다.

## 검증 범위

동일 executor 내 ROS 토픽 통신과 후보 제어 로직을 검증했다.
기존 realsense_tracker 패키지, 별도 프로세스 실행,
PC–Pi 통신, 실제 OpenCR bridge 및 모터 구동은 아직 검증하지 않았다.
