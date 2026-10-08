# 펌웨어 중립 허용 오차 및 축별 범위 변경

## 요청 및 구현

- CHECK/HOLD 중립 허용 오차: Pan/Tilt 각각 ±50 counts, 경계 포함.
- 기준 축: 기존 교정 중립 Pan=3078, Tilt=0 modulo 4096 유지.
- 시작 측정값을 새로운 중립으로 사용하지 않는다. 시작 오차 ±50이 전체 범위를 이동시키지 않는다.
- 요청된 각도 범위: Pan ±120°, Tilt ±60°.
- 4096 counts/revolution 기준으로 외곽 범위를 안쪽 정수화한다.

| 구분 | Pan | Tilt |
|---|---:|---:|
| 정상 LIMIT 정지 시작 | ±1345 counts (±118.2129°) | ±662 counts (±58.1836°) |
| 외곽 FAULT 시작 | ±1365 counts (±119.9707°) | ±682 counts (±59.9414°) |
| 정상 정지와 외곽 사이 여유 | 20 counts (1.7578°) | 20 counts (1.7578°) |

정상 사용 가능 범위는 요청한 외곽 범위보다 20 counts 안쪽이다. 외곽 FAULT를 기계적 범위 밖에 두지 않기 위한 설계 선택이며, 20 counts가 실제 제동에 충분한지는 검증되지 않았다. 소프트웨어 제한은 오버슈트 없는 물리적 정지를 보장하지 않는다. 실제 기구 끝단에 접근하는 방식으로 시험하지 않는다.

기존 공통 STOP=800, OUTER=900은 약 70.31°, 79.10°였다. 따라서 Pan은 확대되지만 Tilt는 요청된 ±60°에 맞춰 축소된다. hardware.yaml의 과거 80/100 counts 설명은 실제 800/900 상수와 불일치했으며 이번에 바로잡았다.

## 동작

- VEL 수신 직전과 주기적 피드백 처리 모두 해당 축의 STOP 경계를 검사한다.
- STOP 경계에서 바깥 방향 명령/목표가 있으면 두 축 영속도 및 DISARM 요청.
- 외곽 경계에 도달하면 FAULT 래치.
- LIMIT 발생 전에는 안쪽 방향 명령을 허용한다. LIMIT 후에는 기존 세션 복구 절차가 필요하다.
- HOLD_DRIFT ±20 counts, ARM 조건 abs(offset)<70 counts, 속도 상한 0.05 rad/s,
  펌웨어 timeout 300 ms, 모터 watchdog 200 ms, ROS 명령 신선도 제한 150 ms는 유지한다.
- MODE=DRY 기본값 유지. LIVE는 빌드 플래그로만 선택한다.

## 검증

호스트 C++ 레지스터 스텁으로 아래 시험을 통과했다.

- 기존 통합 회귀: MODE=DRY 및 MODE=LIVE_STUB.
- 새 test_axis_limits_native.cpp: 두 축 ±50 CHECK/HOLD 허용 및 ARM 가능,
  ±51 CHECK/HOLD 거부, 양방향 STOP/OUTER 경계, VEL 처리와 주기 처리의 LIMIT,
  경계 안쪽 복귀 방향 허용, Tilt wrap 표현, HOLD_DRIFT ±20 유지, 축별 범위 구분.
- 기존 회귀 시험의 과거 80-count 고정 위치 기대값을 현재 축별 경계 기반으로 수정했다.

아직 수행하지 않은 검증: OpenCR용 Arduino 빌드, 업로드, 변경 후 LIVE HOLD/추종/정지거리 시험.
이전에 기록된 51.8초/82.3초 DRY 결과와 중립 검사 기록은 변경 전 펌웨어의 기록으로 보존한다.

## 호스트 검증 명령

리포지토리의 lv2_module5/firmware/opencr/tests 디렉터리에서 실행한다.

```bash
g++ -std=c++17 -Wall -Wextra -Werror -DENABLE_MOTOR_OUTPUT=0 -I native_stubs test_integrated_native.cpp -o /tmp/opencr_dry_regression && /tmp/opencr_dry_regression
g++ -std=c++17 -Wall -Wextra -Werror -DENABLE_MOTOR_OUTPUT=1 -I native_stubs test_integrated_native.cpp -o /tmp/opencr_live_regression && /tmp/opencr_live_regression
g++ -std=c++17 -Wall -Wextra -Werror -DENABLE_MOTOR_OUTPUT=1 -I native_stubs test_axis_limits_native.cpp -o /tmp/opencr_axis_limits && /tmp/opencr_axis_limits
```
