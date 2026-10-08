# Repository ROS 두 축 제어 및 dry bridge 시험

- 시험일: 2026-10-06
- 환경: Raspberry Pi, ROS 2 Lyrical
- 대상: realsense_tracker의 control_node 및 opencr_node
- 실행: 제어 노드, dry bridge, 시험 노드를 별도 프로세스로 실행
- 모터 출력: 비활성화, 시리얼 포트 열지 않음

## 결과

- 제어 로직 단위 시험 5개 통과
- realsense_tracker_interfaces 및 realsense_tracker 빌드 성공
- repository install 경로에서 패키지 실행 확인
- 모의 입력 7개 모두 통과
- 신선한 검출 3프레임 이후 TRACKING 복귀 확인
- 실제 제어 프로세스 종료 후 dry bridge 타임아웃 및 영속도 확인
- dry_run=false 실행 거부 확인
- 최종 결과: ALL REPOSITORY SEPARATE-PROCESS DRY CHECKS PASSED

## 검증 범위

동일 Pi에서 별도 프로세스 간 ROS 토픽 통신과 제어·모의 bridge를 검증했다.
dry bridge 출력은 실제 모터 피드백이 아니다.
PC–Pi 통신, 실제 시리얼 bridge, 모터 구동 및 카메라 추적은 아직 미검증이다.
hardware_mode_rejected.log의 오류는 의도한 하드웨어 모드 거부 시험 결과다.
