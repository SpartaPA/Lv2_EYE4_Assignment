# 제어 테스트 계획 및 결과

## 2026-10-06 현재 상태

| 항목 | 상태 / 근거 |
|---|---|
| 단일 축 파서 기본·확장 시험 | 통과, 기존 efce660 증거 보존 |
| 두 XM430 식별 및 모드 조회 | 완료, ID 11 Pan / ID 12 Tilt, 1 Mbps, Protocol 2 |
| Pan 양/음 방향 및 기본 정지 | 확인, pan_commission_20261006_115112 |
| Tilt 중립 10초 부하 유지 | 확인, 2445a19 |
| Tilt 양/음 방향 및 토크 유지 정지 | 확인, 3494464 |
| 통합 후보 host-side 검사 | DRY 및 LIVE stub 시나리오 통과; 실제 모터 시험 아님 |
| 통합 후보 OpenCR 빌드/업로드 | 아직 미검증 |
| 통합 후보 보드 DRY 검사 | 아직 미검증 |
| 통합 후보 실제 두 축 제어 | 아직 미검증 |
| 위치 경계/실제 정지 지연/bus 장애 | 아직 미검증 |
| ROS 2 및 카메라 전체 추적 | 아직 미검증 |

기존 결과는 각 시험의 firmware와 조건에만 적용한다.

## 증거

- [기준 단일 축 파서](../firmware/opencr/tracking_controller/tracking_controller.ino)
- [기본 시험](../firmware/opencr/tests/test_parser.py), [확장 시험](../firmware/opencr/tests/test_parser_extended.py)
- [기준 로그](../results/logs/opencr/parser_baseline/)
- [Pan 결과](../results/logs/opencr/pan_commission_20261006_115112/test_notes.md)
- [Tilt 부하 유지](../results/logs/opencr/tilt_hold_20261006_122318/test_notes.md)
- [Tilt 구동](../results/logs/opencr/tilt_commission_20261006_124512/test_notes.md)
- [통합 후보 검증 설명](integration_validation.md)

## 통합 시험 순서

1. MODE=DRY OpenCR 빌드/업로드. 실제 모터 전원 OFF, 카메라 지지.
2. test_2axis_dry.py: 두 값 형식, 한 값 오류 시 전체 거부, timeout,
   STATUS/오류/반복 ARM의 비갱신, 미완성/과대 입력, STOP/DISARM.
3. DRY 통과 후 별도 LIVE 빌드. CHECK/HOLD에서 0 명령 및 중립을 확인.
4. bench_2axis_once.py --case zero: 0 명령 종료 후 timeout과 토크 유지 확인.
5. Pan 단독, Tilt 단독, 마지막으로 아주 작은 동시 명령. 각 단계 실제 방향/정지 확인.
6. 위치 제한 시험과 장애 주입은 별도 시험 설계 후 수행. 반복 jog로 한계까지 밀지 않는다.
7. ROS bridge 연결 후 stale 명령 차단, PC/Pi 명령 중단, 재연결 무자동 ARM 확인.
8. 카메라 제어 및 성능 측정.

각 run별 build/upload/serial 로그, 소스 commit과 변경 상태, 실제 관찰을 보관한다.
300 ms는 명령 timeout 설정값이지 실제 정지 시간이 아니다.
정지 지연은 마지막 유효 명령→0 쓰기→속도 정지 피드백을 구분하여 측정한다.
현 stdout은 best-effort이며 로그 누락 또는 낮은 샘플링만으로 지연을 확정하지 않는다.

## ROS 모의 입력

모터 출력 없는 dry_run에서 중심, x±0.4, y±0.4, 미검출 z=0,
/target 중단의 7개 입력을 시험한다. 최신 검출 3프레임 복귀를 확인한다.
Control은 ex/ey를 각각 사용하며 stale/invalid 입력에서 양 축 0을 출력해야 한다.

## 최종 실험

가이드 기준으로 PC–Pi DDS, 30초 추적, 약 2초 가림 및 재등장 5회,
인지 입력 중단/제어 명령 중단을 확인한다. Pan/Tilt Kp 두 조건을 각 3회
비교하고 ex/ey RMSE를 기록한다. bag 재생은 하드웨어 출력 없는 dry-run으로 한다.
본 통합 후보 패키지는 이 최종 실험을 완료한 결과물이 아니다.
