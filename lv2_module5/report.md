# Report — 비전 객체 추적 시스템 (EYE4 / 아이뻐)

> 작성 기준: 2026-10-07, 브랜치 `dev/test1`. 팀 확정 조건: **Pan/Tilt 2축 추적 필수**, 모든 ROS 2 노드는 Raspberry Pi 단일 runtime (PC는 SSH 터미널).
> 표기: **실측** = 저장소 원본 기록이 있는 결과 / **TODO — 실제 장비 시험 후 작성** = 아직 실행하지 않은 시험.
> 코드가 있다는 것만으로 시험 성공이라고 쓰지 않는다. 요구사항별 상태표: [docs/requirements_traceability.md](docs/requirements_traceability.md)

## 0. 목표와 시험 조건 (시험 전 확정)

| 항목 | 값 | 출처 |
|---|---|---|
| 대상 | 파란색 퍽 1개 (단일 색상, 단일 대상) | results/images/detection |
| 추적 | Pan(좌우, ex) + Tilt(상하, ey) 속도형 P 제어 | control.yaml |
| 해상도 | 640×480 @30 fps (Color rgb8) | camera.yaml |
| 시험 횟수 | 정상 30 s 이상 · 가림 약 2 s × 5 · /target 중단 ≥1 · 제어 통신 중단 ≥1 · Kp A/B × 3 | config/test.yaml |
| 판정 | 복구 성공 = 재등장 후 3 s 이내 TRACKING, 평가 프레임 목표 30 / 배경 10 | config/test.yaml |
| Kp A/B | **미확정 (null)** — 방향 확인 후 시험 전에 확정 | TODO |

---

## 문제 1 — HSV·Contour 검출 파이프라인

**1. 구현 내용** — `detector.py`: 블러(5) → HSV → `inRange` 마스크 → 열기·닫기(5) → 외곽 컨투어 → `min_area_ratio` 이상 후보 중 **최대 면적 1개** 선택 → 모멘트 중심 →
ex=(cx−W/2)/(W/2), ey=(cy−H/2)/(H/2) (오른쪽·아래 +), area_ratio=contour_area/(W·H). 미검출이면 x=y=z=0(이전 좌표 재사용 없음).
`perception_node.py`가 RealSense wrapper 컬러 토픽을 직접 구독해 영상마다 `/target`을 발행한다 (`camera_node` 재발행 없음). 원본 위에 컨투어(초록)·목표 중심(빨강)·영상 중심(흰 십자) 표시(`draw`).

**2. 실행 조건** — HSV [93,120,35]~[130,255,255], `min_area_ratio` 0.002(640×480에서 약 614 px), 같은 설정으로 세 장면. 기존 기록은 인지 담당 **노트북**(Ubuntu 24.04 + ROS 2 Lyrical, D435 USB 3.2, wrapper v4.57.7)에서 측정.

**3. 관련 코드** — `realsense_tracker/detector.py`, `perception_node.py`, `config/tracker.yaml`, `config/camera.yaml`, `tools/image_capture.py`, `tools/eval_frames.py`, `tools/eval_score.py`, `test/test_detector.py`

**4. Interface / 설정** — `/target` (geometry_msgs/PointStamped, best effort, depth 1), header = 원본 컬러 영상 header. 깊이는 기록용(`use_depth`), 거리 gate는 `enforce_depth_range`(기본 false).

**5. 검증 방법** — 세 장면 캡처(원본·마스크·검출), 사람 대조 평가 프레임: 목표가 보이는 30장(15 s 동안 고르게, 목표를 화면 여러 위치로 이동) / 목표 없는 10장.

**6. 실제 결과 (실측)**

| 장면 | found | ex | ey | area_ratio | 후보 | 근거 |
|---|---|---|---|---|---|---|
| normal | True | −0.0312 | −0.0649 | 0.03758 | 1 | logs/perception/log.csv, images/detection/normal_20261006_103251_* |
| empty | False | 0 | 0 | 0 | 0 | empty_20261006_103256_* |
| occluded | True | −0.0325 | −0.2246 | 0.01748 | 1 | occluded_20261006_103306_* |

| 지표 | 산식 | 결과 | 근거 |
|---|---|---|---|
| 검출률 (사람 대조) | 올바른 검출 / 판정 프레임 ×100 | **30/30 = 100.0 %** | logs/perception/eval_visible_20261006_104850.csv |
| 배경 오검출 | 목표 없는 프레임의 잘못된 검출 수 | **0 / 10** | logs/perception/eval_empty_20261006_104942.csv |
| 처리 FPS (인지 단독) | 처리 프레임 / 경과 초 | **30.03 fps** (29,276 프레임 / 975 s, 5 s 창 195개) | logs/perception/perception_node_20261006_1043.log |

**7. 결과 해석** — 같은 설정에서 정상·가림은 검출, 대상 없음은 z=0. 가림 장면은 면적비가 정상의 약 47 %로 줄었지만 중심 오차는 보이는 부분 기준으로 계산된다(가림 정도에 따라 ey가 치우침: −0.22). 처리 FPS는 카메라 설정 30 fps와 같아 인지가 병목이 아니었다(노트북 기준).
HSV 근거·오검출 조건: H 93~130은 파란 퍽 범위, S 하한 120으로 흰·회색 배경 제외, V 하한 35로 어두운 그림자 일부 허용, 최소 면적으로 작은 잡티 제거. 비슷한 파란 물체가 더 크면 그것을 고를 수 있다(최대 면적 규칙의 한계).
미검출 전달: `/target`을 생략하지 않고 z=0으로 발행 → 제어가 "입력은 신선하지만 목표 없음"으로 즉시 정지.

**8. 남은 검증** — Raspberry Pi에 D435를 연결한 상태의 처리 FPS·USB 속도(TODO). 이번 수정 후 코드로 같은 장면 재확인(TODO).

**9. 한계** — 위 결과는 깊이 거리 gate가 추가되기 **이전** 코드(commit 85ce391, `use_depth: false` — 노드 시작 로그로 확인)에서 측정했다. 통합본(5ffa72a)에서 13~100 cm gate가 항상 켜지도록 바뀌었으나 팀 결정 근거가 없어 이번에 기본 off(`enforce_depth_range: false`)로 되돌렸다 → 현재 기본 동작은 측정 당시와 같은 "컬러 기준 검출"이다. 단, 같은 코드라고 단정하지 않고 재측정을 TODO로 둔다. 심화(조명/거리 비교)는 미수행.

---

## 문제 2 — 인지·제어 노드 연결

**1. 구현 내용** — `control_node`가 `/target`을 best effort로 구독, `control_core.Controller`가 판정·계산, 20 Hz로 `/control/pan_tilt_cmd`와 `/tracking_status` 발행. LOST 전환 시 즉시 발행.

**2. 실행 조건** — 모터 출력 없음(DRY sink 또는 DRY 펌웨어), Kp 0.1 rad/s, 속도 상한 0.05 rad/s, deadband 0.03, timeout 0.5 s, direction Pan −1 / Tilt +1 (`control_dry.yaml`).

**3. 관련 코드** — `control_core.py`, `control_node.py`, `dry_bridge.py`, `test_control_dry.py`, `test/test_control_core.py`

**4. Interface** — [docs/control_interface.md](docs/control_interface.md) 2~4절 (노드 연결도: [README 2절](README.md#2-최종-시스템-구조)).

| 방향 | Topic | Type | 의미 |
|---|---|---|---|
| wrapper → perception | /camera/camera/color/image_raw | sensor_msgs/Image | 입력 (rgb8) |
| perception → control | /target | geometry_msgs/PointStamped | x=ex, y=ey, z=area_ratio(0=미검출) |
| control → 전체 | /tracking_status | std_msgs/String | IDLE/TRACKING/LOST |
| control → opencr | /control/pan_tilt_cmd | realsense_tracker_interfaces/PanTiltCommand | stop, pan/tilt rad/s (모터 원시 부호) |

**5. 검증 방법** — 별도 프로세스(control_node, opencr_node DRY sink, 시험 노드)에 7개 입력 발행 → 명령·상태 판정.

**6. 실제 결과 (실측, 이전 commit — 2026-10-06 Raspberry Pi)**

| 입력 | 결과 | 근거 |
|---|---|---|
| 7개 모의 입력 + 3프레임 복귀 + 제어 프로세스 종료 시 bridge 영속도 + dry_run=false 거부 | `ALL REPOSITORY SEPARATE-PROCESS DRY CHECKS PASSED` | logs/control/ros_repository_dry_20261006_170913 |
| 제어 → 시리얼 bridge → DRY 펌웨어(PTY): 5개 방향, 미검출 STOP, 3프레임 복귀, 침묵 LOST, 제어 종료 → DISARM, 재ARM 없음 | `ALL SERIAL ROS PTY CHECKS PASSED` | logs/control/serial_bridge_stop_fix_20261006_182228 |
| 실제 OpenCR(MODE=DRY) USB: 중심 0,0 / 오른쪽 −2,0 / 왼쪽 2,0 / 아래 0,2 / 위 0,−2 (원시 단위) / 미검출·침묵 0,0 | 관찰됨, 단 장시간 침묵 중 FAULT 1건 (문제 4) | logs/control/serial_usb_seven_20261006_195242 |

원시 단위 2 = 0.04 rad/s ÷ 0.02398 rad/s(0.229 rpm) 반올림.

**7. 결과 해석** — 오른쪽 목표(x=+0.4)에 Pan 음의 명령(= 모터 원시 우측)이 나와 오차를 줄이는 방향이다(원시 방향 근거: docs/hardware.md). 부호가 반대면 카메라가 목표 반대쪽으로 돌아 오차가 커지고 목표가 화면 밖으로 나간다 → Kp를 키우지 말고 direction부터 확인.
미검출(z=0)은 신선한 입력이므로 즉시 LOST, 토픽 침묵은 0.5 s 뒤 timeout으로 LOST — 두 경우를 구분한다. 노드별 책임: 인지는 오차만, 제어는 판단·부호·상한, bridge는 신선도·세션, 펌웨어는 각도 경계·하드웨어 timeout.

**8. 남은 검증** — 이번 수정(축별 파라미터, `/control/enable`)을 포함한 현재 commit으로 `test_control_dry` Pi 재실행 (README 10절). 이 환경(Windows, ROS 없음)에서는 ROS 런너를 실행하지 못했다. 순수 로직 단위 시험 32개는 통과(아래 "자동 검사").

**9. 한계** — DRY 출력은 모의 처리 결과이며 실제 모터 피드백이 아니다.

---

## 문제 3 — 객체 중심 기반 추적 제어

**1. 구현 내용** — pan = clamp(pan_direction·kp_pan·ex, ±pan_speed_limit), tilt = clamp(tilt_direction·kp_tilt·ey, ±tilt_speed_limit), 축별 deadband. direction은 control_node 한 곳에서만 적용. 회전 범위는 엔코더를 아는 OpenCR 펌웨어가 중립 ±80 counts에서 바깥 방향 명령을 막는다(EVENT LIMIT + DISARM).

**2. 실행 조건** — Velocity Mode, 단위: ex·ey 무차원 → Kp [rad/s], 명령 [rad/s], 펌웨어에서 0.229 rpm 원시 단위로 변환. 속도 상한 0.05 rad/s(펌웨어 MAX_RAD_S 이하만 허용).

**3. 관련 코드** — `control_core.py`, `control.yaml`, 펌웨어 `tracking_controller_2axis.ino`, `tools/tracking_logger.py`, `tools/analyze_tracking.py`

**4. Interface / 설정** — `control.yaml` (Kp 0.1은 기존 팀 초기값, 튜닝값 아님), `config/test.yaml` Kp A/B (null).

**5. 검증 방법** — ① 추적 없이 작은 단일 명령으로 방향 확인 ② 폐루프에서 오른쪽 목표 시 ex 감소 확인 ③ Kp A/B × 3회, 왼쪽 3 s → 중앙 3 s → 오른쪽 3 s → 중앙 3 s, `tracking_logger` CSV → `analyze_tracking --plot`.

**6. 실제 결과**

| 시험 | 결과 | 근거 |
|---|---|---|
| ① 단일 명령 방향 (LIVE 펌웨어, ROS 없이) | **실측**: pan-left/right, tilt-up/down, both, zero 6개 성공. 각 VEL 후 300 ms timeout 정지·토크 유지 | logs/opencr/integration_live_20261006_141057/test_notes.md |
| ② 폐루프 영상 오차 감소 부호 | TODO — 실제 장비 시험 후 작성 | |
| ③ Kp A/B × 3회 CSV·그래프·RMSE | TODO — 실제 장비 시험 후 작성 | |
| 실제 추적 영상 | TODO — 실제 장비 시험 후 작성 | |

**7. 결과 해석** — ①로 원시 명령 부호(Pan + 좌, Tilt + 아래)가 확인되어 direction(Pan −1, Tilt +1)을 정했다. 실제 영상 오차가 줄어드는지는 ②에서 확인해야 한다.

**8. 남은 검증** — ②, ③, Kp 최종 선택 근거(반응 속도·흔들림), 실제 기구 안전 회전 범위 확정.

**9. 한계** — 모터 위치를 측정해 기록하지 않으므로 그래프의 명령값을 실제 위치로 해석하지 않는다. 펌웨어 경계 ±80 counts(약 ±7°)는 bench 값이라 추적 범위가 좁다(수동 측정 자세는 약 ±400 counts).

---

## 문제 4 — 성능 측정과 목표 소실 복구

**1. 구현 내용**

| 상태 | 조건 | 동작 |
|---|---|---|
| IDLE | 시작 전, `/control/enable false` | stop=true |
| TRACKING | 신선한 검출 3프레임 연속 | 제한된 2축 명령 |
| LOST | z=0(첫 프레임부터), 무효·오래된 입력, 0.5 s timeout | stop=true, 이전 속도 버림 |

통신 중단 정지 계층: control 0.5 s → opencr_node 명령 나이 0.15 s(FAULT·DISARM) → 펌웨어 300 ms(두 축 0 + DISARM) → 모터 Bus_Watchdog 200 ms. 자동 재ARM 없음.
상태 표시 유예는 두지 않았다(상태 = 명령 근거).

**2. 실행 조건** — config/test.yaml. 움직일 수 없는 상태에서 끊김 처리 확인 → 낮은 속도·제한 범위 실회전.

**3. 관련 코드** — `control_core.py`, `serial_core.py`, 펌웨어, `tools/tracking_logger.py`, `tools/analyze_tracking.py`, `results/logs/verification/*.csv` 템플릿

**4. Interface / 설정** — 로그 열: run_id, time_s, stamp_ns, receive_time_s, detected, ex, ey, area_ratio, state, stop, pan_command, tilt_command, command_unit.
유효 추적 비율 = (detected ∧ TRACKING) / 전체 /target 프레임, RMSE도 같은 프레임만(제외 수 병기).

**5. 검증 방법** — README 17절 표.

**6. 실제 결과**

| 시험 / 지표 | 결과 |
|---|---|
| 검출률·배경 오검출·인지 처리 FPS | 문제 1 결과 (실측: 30/30, 0/10, 30.03 fps — 노트북, 인지 단독) |
| 정상 추적 30 s (Pi 폐루프 FPS, 수평·수직 RMSE, 유효 추적 비율) | TODO — 실제 장비 시험 후 작성 |
| 2 s 가림 × 5 (정지·복귀 여부, 복구 시간, 복구 성공률) | TODO — 실제 장비 시험 후 작성 |
| /target 발행 중단 | DRY 실측(이전 commit): 0.5 s 후 LOST·STOP. 실기 TODO |
| 제어 통신 중단 → 보드 측 정지 | 펌웨어 단독 실측: VEL 1회 후 침묵 → 300 ms timeout 정지 (integration_live). PTY: 제어 종료 → bridge ROS_COMMAND_TIMEOUT → DISARM. ROS 경유 실기 TODO |

**실패 기록 (실측)** — 실제 OpenCR DRY USB 시험(serial_usb_seven_20261006_195242)에서 target 발행 중단 약 456.6 s 후 bridge가 `ROS_COMMAND_TIMEOUT` FAULT. 직전 보드 STATUS는 정상 영속도였고, 마지막 STATUS 수신과 FAULT 사이에 약 138 ms 로그 공백이 있었다. bridge는 즉시 DISARM을 보냈고 종료 후 보드는 DISARMED·영속도였다.
원인 미확정(제어 명령 간격 > 0.15 s가 된 이유: control 타이머·DDS·bridge 실행 지연 중 어느 것인지 미구분). 안전 측면에서는 정지 방향의 실패다. 다음 시험에서 명령 수신 간격·timestamp 나이를 함께 기록한다. 이 회차를 통과로 세지 않는다.

**7. 결과 해석** — 실측이 쌓이기 전이라 성능 해석 없음. 복구 판정의 "재등장 시각"은 영상으로 사람이 정하고, `analyze_tracking`의 "첫 재검출"은 보조값으로만 쓴다.

**8. 남은 검증** — 위 TODO 전부, Bus_Watchdog 실동작, 위치 경계 정지.

**9. 한계** — 노드 detected 비율은 사람 대조 검출률이 아니다. RMSE가 작아도 유효 추적 비율이 낮으면 좋은 추적이 아니다. 지연은 측정하지 않았다(촬영→구동 지연이라 쓰지 않음).

---

## 문제 5 — bag 재현과 팀 협업

**1. 구현 내용** — Pi에서 `ros2 bag record`(컬러·camera_info·/target·/tracking_status·/control/pan_tilt_cmd·/opencr/bridge_status), 시리얼 CSV·추적 CSV에 같은 run_id.
A. 입력 재처리: bag 컬러만 재생 → perception_node `-r /target:=/target_replay`, `use_sim_time:=true`, `--clock`.
B. 결과 재분석: 저장된 /target·상태·명령 재생 → 같은 `tracking_logger` → `analyze_tracking`.
재생 중 모터 OFF: opencr_node·control_node 종료 + 격리 ROS_DOMAIN_ID (+ bridge는 오래된 시각 명령을 거부).

**2~5.** 명령·조건: [README 18~20절](README.md#18-bag-record), 메타데이터 양식: [recordings/README.md](recordings/README.md).

**6. 실제 결과** — TODO — 실제 장비 시험 후 작성 (기록된 bag 없음).

**7. 해석** — 입력 재처리는 검출기를 다시 돌려 검출·오차 경향이 재현되는지 보는 것이고, 결과 재분석은 저장된 출력으로 지표 계산이 재현되는지 보는 것이다. 저장된 /target을 보기만 한 것은 재처리가 아니다.

**8. 남은 검증** — 성공·소실 bag, 두 재현, 작성자가 아닌 팀원의 README 실행 기록(확인자·날짜·commit·결과).

**9. 한계** — 640×480 rgb8 영상은 약 27.6 MB/s → Pi 저장 공간·기록 부하 확인 필요. bag은 Git에 올리지 않고 링크·체크섬으로 연결.

---

## 자동 검사 (2026-10-07, 이 저장소, Windows + uv Python 3.12 — ROS 없음)

| 검사 | 결과 |
|---|---|
| `python -m unittest discover -s test` (control_core 9, serial_core 19, detector 4) | 32 PASS |
| Python 29개 문법, YAML 8개, XML 2개 파싱 | PASS |
| 펌웨어 host native 시험 (zig c++ -Wall -Wextra -Werror, DRY / LIVE_STUB) | PASS / PASS |
| `analyze_tracking.py` 합성 CSV 동작 확인 | 동작 (결과 데이터 아님, 저장 안 함) |
| colcon build, `ros2 pkg executables`, ROS 런너(test_control_dry 등) | **실행 못 함** (이 환경에 ROS 2 없음) → Pi에서 README 8·10·11절 |

## 심화·도전 과제

미수행: 조명/거리 비교(A), SEARCHING(B), 데드밴드/필터 비교(C), 강건성 확장(D), 고정 bag 회귀(E). Depth 거리 gate는 옵션으로만 존재(기본 off).

## AI 도구 사용 범위

Claude Code를 사용해 통합본 감사, LIVE bridge 모드·축별 파라미터·명시적 중지·깊이 gate 옵션 코드 수정, logger·분석 도구, 단위 시험 추가, 문서 작성을 했다.
AI가 생성한 시험 결과는 없다: 이 보고서의 실측 값은 모두 팀원이 장비에서 기록한 `results/` 원본에서 계산했다. 수정된 코드의 실제 장비 동작은 팀원이 Pi에서 검증해야 한다 (README 22절).
