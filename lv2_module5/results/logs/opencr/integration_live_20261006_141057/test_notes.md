# Pan/Tilt 통합 LIVE 초기 시험

- 시험일: 2026-10-06
- 펌웨어: tracking_controller_2axis
- 실행 모드: ENABLE_MOTOR_OUTPUT=1 / MODE=LIVE
- 담당자 확인: 아래 6개 시험 모두 성공

| 시험 | 확인 결과 |
|---|---|
| zero | 의도적 움직임 없이 timeout 후 두 축 정지 |
| pan-left | Pan 좌측 이동 후 정지, Tilt 유지 |
| pan-right | Pan 우측 이동 후 정지, Tilt 유지 |
| tilt-up | Tilt 위쪽 이동 후 정지, Pan 유지 |
| tilt-down | Tilt 아래쪽 이동 후 정지, Pan 유지 |
| both | Pan 우측 및 Tilt 아래쪽 이동 후 두 축 정지 |

방향 기준은 카메라 뒤에서 정면을 바라보는 방향이다.
각 시험은 단일 VEL 명령 이후 명령 전송을 중단하여
300 ms 명령 timeout과 DISARM 동작을 확인했다.
정상 정지 후 두 축 토크는 유지한다.

## 검증 범위

통합 후보의 기본 방향, 단일 명령 timeout 및 정지 후 유지 동작을 확인했다.
위치 경계 정지, 실제 정지 지연, 모터 버스 통신 단절,
보드 정지 및 피드백 실패의 실제 장비 시험은 아직 미완료다.
ROS bridge 및 실제 카메라 추적은 아직 연결하지 않았다.
