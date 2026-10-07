# Requirement Traceability (발제문 문제 1~5 + 팀 2축 조건)

작성: 2026-10-07, 브랜치 `dev/test1`. 기준: 발제문 문제 1~5, 팀 확정 조건(Pan/Tilt 2축 필수, Raspberry Pi 단일 runtime).

- **감사 시점** = 통합본 ZIP(상화·민혁·상준)을 수정하기 전 상태
- **구현** = 현재 코드에 기능이 있음 (IMPLEMENTED) / 해당 없음 (NOT APPLICABLE)
- **검증** = VERIFIED: 저장소의 원본 기록이 있는 실제 실행 결과 / NOT VERIFIED: 실행 기록 없음.
  단위·host 시험만 있는 항목은 "코드 시험"으로 따로 적고, 장비 결과로 세지 않는다.
- 2026-10-06 기록은 이번 수정(축별 파라미터, LIVE bridge, 깊이 gate 옵션) **이전 코드**로 실행된 것이다. 현재 commit으로 Pi에서 다시 실행해야 한다.

## 문제 1 — HSV·Contour 검출

| ID | 요구사항 | 관련 파일 | 감사 시점 | 구현 | 검증 | 근거 / 비고 |
|---|---|---|---|---|---|---|
| P1-01 | 단일 색상 목표 선정·사진 | results/images/detection | 있음 | IMPLEMENTED | VERIFIED | normal_*_raw.png (파란 퍽) |
| P1-02 | Blur→HSV→Mask→잡음 제거→Contour→선택→중심 | detector.py | 구현됨 | IMPLEMENTED | VERIFIED | 세 장면 이미지 + test_detector.py |
| P1-03 | HSV·최소 면적·해상도 설정 분리 | tracker.yaml, camera.yaml | 구현됨 | IMPLEMENTED | VERIFIED | 설정 파일 |
| P1-04 | 여러 후보 선택 규칙 | detector.py | 최대 면적 1개 | IMPLEMENTED | VERIFIED | `n_candidates` 기록 |
| P1-05 | 원본 위 컨투어·목표 중심·영상 중심 표시 | detector.draw | 구현됨 | IMPLEMENTED | VERIFIED | *_det.png |
| P1-06 | 미검출 시 이전 좌표 재사용 금지 (x=y=z=0) | detector.py, control_core.py | 구현됨 | IMPLEMENTED | VERIFIED(코드 시험) | test_detector, test_control_core |
| P1-07 | 정상·없음·가림 같은 설정 | results/logs/perception/log.csv | 있음 | IMPLEMENTED | VERIFIED | 세 행 같은 HSV·면적 |
| P1-08 | ex=(cx−W/2)/(W/2), ey, 오른쪽·아래 + | detector.py | 구현됨 | IMPLEMENTED | VERIFIED(코드 시험) | test_detector |
| P1-09 | area_ratio=contour_area/(W·H) | detector.py | 구현됨 | IMPLEMENTED | VERIFIED(코드 시험) | test_detector |
| P1-10 | Depth는 기록용, 검출을 막지 않음 (팀 결정 근거 없음) | detector.py, perception_node.py | **hard gate 항상 켜짐** | IMPLEMENTED (옵션, 기본 off) | VERIFIED(코드 시험) | test_detector depth 2건 |
| P1-11 | 정렬 Depth·CameraInfo 수집·유효성 기록 | perception_node stats, camera.yaml | 부분 | IMPLEMENTED | VERIFIED(노트북) / NOT VERIFIED(Pi) | camera.yaml 기록, 유효 거리 측정 비율 로그 |
| P1-12 | D435 serial·firmware·wrapper·USB·profile·encoding·K·frame_id 기록 | camera.yaml | 있음(노트북) | IMPLEMENTED | VERIFIED(노트북) / NOT VERIFIED(Pi) | |
| P1-13 | HSV 근거·오검출 감소 조건·미검출 전달 설명 | report.md | 없음 | IMPLEMENTED | — | report 문제 1 |
| P1-14 | (심화) 조명/거리 변경 비교 | — | 없음 | NOT IMPLEMENTED | — | 선택 과제, 미수행 |

## 문제 2 — 인지·제어 연결

| ID | 요구사항 | 관련 파일 | 감사 시점 | 구현 | 검증 | 근거 / 비고 |
|---|---|---|---|---|---|---|
| P2-01 | `/target` PointStamped, x=ex, y=ey, z=area_ratio | perception_node.py | 구현됨 | IMPLEMENTED | VERIFIED | perception 로그, DRY 시험 |
| P2-02 | header.stamp = 원본 영상 시각 | perception_node.py | 구현됨 | IMPLEMENTED | NOT VERIFIED(Pi 확인 기록 없음) | header 그대로 복사 |
| P2-03 | z=0 → x/y로 제어 안 함, 정지 | control_core.py | 구현됨 | IMPLEMENTED | VERIFIED(이전 commit) | logs/control/ros_repository_dry_20261006_170913 |
| P2-04 | 영상마다 발행, 미검출도 z=0 발행 | perception_node.py | 깊이 동기 실패 시 발행 멈춤 | IMPLEMENTED | VERIFIED(코드) | 컬러 콜백마다 발행 |
| P2-05 | QoS best effort, depth 1, 구독 호환 | perception_node, control_node | 구현됨 | IMPLEMENTED | VERIFIED(이전 commit) | DRY 시험 TARGET_QOS |
| P2-06 | `/tracking_status` IDLE/TRACKING/LOST | control_node.py | 구현됨 | IMPLEMENTED | VERIFIED(이전 commit) | DRY 시험 |
| P2-07 | 모터 명령 단위·부호·주기·정지 명시 | PanTiltCommand.msg, docs/control_interface.md | 문서 부분 | IMPLEMENTED | — | rad/s, 20 Hz, stop |
| P2-08 | 입력 timeout 0.5 s | control_core.py, control.yaml | 구현됨 | IMPLEMENTED | VERIFIED(이전 commit) | DRY 시험 7번 |
| P2-09 | 7개 모의 입력 (발제 5 + y±0.4) | test_control_dry.py, test_control_core.py | 구현됨 | IMPLEMENTED | VERIFIED(이전 commit, Pi) / 현재 commit 재실행 TODO | ros_repository_dry, serial_usb_seven(실제 OpenCR DRY) |
| P2-10 | 미검출과 토픽 침묵 구분 | control_core.py | 구현됨 | IMPLEMENTED | VERIFIED(코드 시험) | z=0은 신선 입력, 침묵은 timeout |
| P2-11 | 멈춘 카메라의 옛 영상 재사용 금지 (오래됨·중복·역순 거부) | control_core.py | 구현됨 | IMPLEMENTED | VERIFIED(코드 시험) | test_stale_duplicate_invalid_and_future |
| P2-12 | 노드 연결도·인터페이스 표 | README 2절, 팀업무_네비게이터.md | 문서만 | IMPLEMENTED | — | |
| P2-13 | (심화) /search 액션 | — | 없음 | NOT APPLICABLE | — | 기본 범위 밖, 미구현 |

## 문제 3 — 2축 P 제어

| ID | 요구사항 | 관련 파일 | 감사 시점 | 구현 | 검증 | 근거 / 비고 |
|---|---|---|---|---|---|---|
| P3-01 | 작은 명령으로 모터 방향 확인 | firmware tests/bench_2axis_once.py | 기록 있음 | IMPLEMENTED | VERIFIED | integration_live_20261006_141057 (6 케이스) |
| P3-02 | 실제 영상 오차가 줄어드는 부호 확인 (2축) | control.yaml direction | 미시험 | IMPLEMENTED | NOT VERIFIED | README 12절 단계 B |
| P3-03 | pan=clamp(dir·Kp·ex), tilt=clamp(dir·Kp·ey) | control_core.py | 구현됨 | IMPLEMENTED | VERIFIED(코드 시험) | test_seven_inputs |
| P3-04 | direction ±1, 한 계층에서만 적용 | control_core.py | 구현됨 | IMPLEMENTED | VERIFIED(코드 시험) | bridge·펌웨어는 부호 미적용 (test_explicit_prepare_arm_and_no_sign_flip) |
| P3-05 | Kp·명령 단위 기록 | control.yaml, docs | 부분 | IMPLEMENTED | — | Kp [rad/s], 명령 [rad/s] |
| P3-06 | 속도 상한 (축별) | control_core.py, 펌웨어 MAX_RAD_S | 공통 1개 | IMPLEMENTED | VERIFIED(코드 시험) | test_per_axis_limits_and_deadbands |
| P3-07 | 회전 범위, 범위 끝 바깥 방향 명령 금지 | 펌웨어 STOP/OUTER_COUNTS | 펌웨어 구현 | IMPLEMENTED | VERIFIED(host native) / NOT VERIFIED(실기) | 경계값은 bench 값, 기구 범위 TODO |
| P3-08 | 중심 deadband (축별) | control_core.py | 공통 1개 | IMPLEMENTED | VERIFIED(코드 시험) | |
| P3-09 | 속도→위치 적분 시 실제 dt | — | 해당 없음 | NOT APPLICABLE | — | 속도 명령만 사용, 위치 적분 없음 |
| P3-10 | Kp A/B 사전 확정, 각 3회 | config/test.yaml | null | IMPLEMENTED(구조) | NOT VERIFIED | Kp 값 TODO |
| P3-11 | 오차·명령·상태 시간 기록, 비교 그래프 | tools/tracking_logger.py, analyze_tracking.py | **없음** | IMPLEMENTED | NOT VERIFIED | 합성 CSV로 도구 동작만 확인 |
| P3-12 | 실제 추적 영상 | — | 없음 | — | NOT VERIFIED | |

## 문제 4 — 성능·소실 복구·안전

| ID | 요구사항 | 관련 파일 | 감사 시점 | 구현 | 검증 | 근거 / 비고 |
|---|---|---|---|---|---|---|
| P4-01 | IDLE/TRACKING/LOST + 명시적 중지 | control_core.py, `/control/enable` | 명시적 중지 없음 | IMPLEMENTED | VERIFIED(코드 시험) | test_explicit_disable_is_idle_and_needs_three_frames |
| P4-02 | 미검출 첫 프레임부터 정지 | control_core/node | 구현됨 | IMPLEMENTED | VERIFIED(이전 commit, DRY) | LOST 전환 즉시 발행 |
| P4-03 | 입력 timeout 정지 | control_core.py | 구현됨 | IMPLEMENTED | VERIFIED(이전 commit, DRY) | |
| P4-04 | 신선 3프레임 연속 → TRACKING | control_core.py | 구현됨 | IMPLEMENTED | VERIFIED(이전 commit, DRY) | serial_bridge_stop_fix (PTY) |
| P4-05 | 제어 통신 중단 시 OpenCR/모터 측 정지 | 펌웨어 COMMAND_MS, serial_core | **ROS 경유 LIVE 불가** | IMPLEMENTED | 펌웨어 단독 VERIFIED / ROS 경유 NOT VERIFIED | integration_live(VEL 후 침묵 → 300 ms 정지), PTY 시험 |
| P4-06 | 모터 Bus_Watchdog | 펌웨어 BUS_TICKS | 구현됨 | IMPLEMENTED | NOT VERIFIED(실동작) | HOLD에서 설정·검증만 |
| P4-07 | 정상·가림·입력 중단·통신 중단 로그 구성 | tracking_logger, verification 템플릿 | 없음 | IMPLEMENTED | — | recovery_trials.csv, interruption_trials.csv |
| P4-08 | 정상 추적 30 s 이상 | — | — | — | NOT VERIFIED | |
| P4-09 | 2 s 가림 후 재등장 5회 | — | — | — | NOT VERIFIED | |
| P4-10 | 인지 입력 중단 1회 이상 | — | DRY 기록 | — | DRY VERIFIED(이전 commit) / 실기 NOT VERIFIED | |
| P4-11 | 제어 통신 중단 1회 이상 | — | DRY 기록 | — | PTY VERIFIED / 실기 NOT VERIFIED | |
| P4-12 | 처리 FPS | perception_node stats, analyze_tracking | 로그 있음 | IMPLEMENTED | 인지 단독 VERIFIED(노트북, 30.03) / Pi 폐루프 NOT VERIFIED | metrics.csv |
| P4-13 | 검출률 (사람 대조 30프레임) | tools/eval_frames.py, eval_score.py | 기록 있음 | IMPLEMENTED | VERIFIED 30/30 | 깊이 gate 추가 이전 코드, 컬러만 |
| P4-14 | 배경 오검출 (10프레임) | 같음 | 기록 있음 | IMPLEMENTED | VERIFIED 0/10 | |
| P4-15 | 수평·수직 RMSE, 제외 수, 유효 추적 비율 | analyze_tracking.py | 없음 | IMPLEMENTED | NOT VERIFIED | |
| P4-16 | 복구 성공률·복구 시간 (실패는 0 s 아님) | analyze_tracking.py, recovery_trials.csv | 없음 | IMPLEMENTED | NOT VERIFIED | |
| P4-17 | 실패 원인 분석 | report.md | serial_usb_seven FAULT 원인 미확정 | — | 미해결 | report 문제 4 |
| P4-18 | (심화) SEARCHING | — | 없음 | NOT APPLICABLE | — | 기본 범위 밖, 미구현 |

## 문제 5 — bag 재현·협업

| ID | 요구사항 | 관련 파일 | 감사 시점 | 구현 | 검증 | 근거 / 비고 |
|---|---|---|---|---|---|---|
| P5-01 | 성공·소실 bag 각 10~30 s, 용량 확인 | README 18절 | 문서 예시만 | IMPLEMENTED(절차) | NOT VERIFIED | |
| P5-02 | 영상·목표·상태·명령 기록, 시리얼 로그 같은 run_id | README 14·18절, opencr_node csv_path | 부분 | IMPLEMENTED | NOT VERIFIED | |
| P5-03 | 토픽·메시지 수·기간·해상도·설정·커밋·크기·해시 기록 | recordings/README.md | 일부 | IMPLEMENTED(양식) | NOT VERIFIED | |
| P5-04 | 재현 중 실제 모터 출력 비활성 | README 19절 | 문서 | IMPLEMENTED | NOT VERIFIED | 노드 종료 + 격리 도메인 + bridge 오래된 명령 거부 |
| P5-05 | 입력 재처리 → `/target_replay`, `--clock`, use_sim_time | perception_node remap | 문서 예시 | IMPLEMENTED | NOT VERIFIED | |
| P5-06 | 결과 재분석 → 같은 지표 코드 | tracking_logger + analyze_tracking | 없음 | IMPLEMENTED | NOT VERIFIED | |
| P5-07 | 작성자 아닌 팀원 README 재현 | team.md | 없음 | — | NOT VERIFIED | |
| P5-08 | team.md 4인 역할·Issue·PR·리뷰 | team.md | 역할 TODO | 역할 반영 | PR/Issue 링크 미기록 | 가짜 링크 금지 |
| P5-09 | (심화) 고정 bag 회귀 비교 | — | 없음 | NOT IMPLEMENTED | — | |

## 시스템 공통

| ID | 요구사항 | 관련 파일 | 구현 | 검증 |
|---|---|---|---|---|
| S-01 | Pan/Tilt 2축 필수 (코드 전체) | control_core, PanTiltCommand, 펌웨어 | IMPLEMENTED | VERIFIED(코드 시험) |
| S-02 | Raspberry Pi 단일 runtime launch | tracker.launch.py | IMPLEMENTED | NOT VERIFIED (Pi 실행 기록 없음) |
| S-03 | 기본값은 모터 출력 없음 (DRY sink, start_control/start_opencr false) | opencr_node, launch | IMPLEMENTED | VERIFIED(코드 시험) |
| S-04 | 자동 토크·자동 ARM·자동 재연결 없음 | serial_core.py | IMPLEMENTED | VERIFIED(코드 시험 + 이전 PTY 시험) |
| S-05 | 펌웨어 기본 빌드 DRY, LIVE는 명시 플래그 | tracking_controller_2axis.ino | IMPLEMENTED | VERIFIED(host native DRY/LIVE_STUB) |
| S-06 | 같은 값의 Source of Truth 하나 | config/README.md | IMPLEMENTED | — |
