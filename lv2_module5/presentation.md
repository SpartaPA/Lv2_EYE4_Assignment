# Presentation — EYE4 (아이뻐) 비전 객체 추적 시스템

5분 시연 발표 자료의 소스. 녹화를 쓰면 "녹화"라고 표시한다. 실측 전 항목은 `TODO: 실제 시험 후 삽입`.

## 1. 과제 목표 (30 s)

- D435 Color로 파란 퍽 1개를 찾고, 중심 오차를 줄이도록 **Pan/Tilt 2축** DYNAMIXEL을 P 제어
- 목표 소실·입력 중단·제어 통신 중단 시 정지, 시야 내 재등장 시 3프레임 후 복귀
- 측정(FPS·검출률·RMSE·복구)과 bag 재현으로 결과를 증명

## 2. 2축 시스템 구조

```text
PC (SSH 터미널) ──SSH──▶ Raspberry Pi
  D435 ─USB3─▶ realsense2_camera ─▶ perception_node ─/target─▶ control_node ─/control/pan_tilt_cmd─▶ opencr_node
                                                                                        ─USB Serial─▶ OpenCR ─▶ Pan(ID 11) / Tilt(ID 12)
```

모든 ROS 2 노드는 Pi 한 대. 계층별 정지: control 0.5 s → bridge 0.15 s → 펌웨어 300 ms → 모터 watchdog 200 ms.

## 3. Problem 1 — 인지

- 블러 → HSV [93,120,35]~[130,255,255] → 마스크 → 열기·닫기 → 최대 면적 컨투어 → 중심
- ex=(cx−W/2)/(W/2), ey=(cy−H/2)/(H/2), z=면적비, 미검출 z=0
- 이미지: `results/images/detection/normal|empty|occluded_*_det.png` (원본·마스크·검출)
- 실측: 검출률 30/30, 배경 오검출 0/10, 인지 처리 30.03 fps (노트북 측정)

## 4. Problem 2 — Interface

- `/target` PointStamped (best effort, depth 1), `/tracking_status`, `/control/pan_tilt_cmd` (stop + rad/s)
- 7개 모의 입력 (발제 5 + y±0.4): 실측 PASS (2026-10-06 Pi, 이전 commit) — `results/logs/control/ros_repository_dry_20261006_170913`
- 미검출(z=0, 즉시 정지) ≠ 토픽 침묵(0.5 s timeout)

## 5. Problem 3 — P Control

- pan = clamp(−1·Kp·ex, ±0.05), tilt = clamp(+1·Kp·ey, ±0.05) rad/s, deadband 0.03
- direction 근거: 원시 + = Pan 좌 / Tilt 아래 (실측 commission, LIVE 6케이스)
- 각도 경계: 펌웨어 엔코더 ±80 counts → LIMIT
- Kp A/B 비교 그래프: TODO: 실제 시험 후 삽입
- 정상 추적 영상: TODO: 실제 시험 후 삽입

## 6. Problem 4 — Safety / Recovery

- IDLE / TRACKING / LOST 전이표, `/control/enable`로 명시적 중지
- 가림 5회 복구 표: TODO: 실제 시험 후 삽입
- /target 중단, control 종료, opencr_node 강제 종료 → 보드 300 ms 정지: TODO: 실제 시험 후 삽입
- 보드 측 timeout 단독 실측: VEL 1회 후 침묵 → 정지 (integration_live_20261006_141057)
- 실패 사례: DRY USB 장시간 침묵 중 ROS_COMMAND_TIMEOUT (원인 미확정, 정지 쪽 실패)

## 7. Problem 5 — Reproducibility

- bag (컬러·/target·상태·명령) + 시리얼 CSV를 같은 run_id로 연결
- 입력 재처리 `/target_replay` vs 결과 재분석 (같은 analyze_tracking.py)
- 재현 기록 (다른 팀원): TODO: 실제 시험 후 삽입

## 8. 코드 핵심

- `control_core.py` — 신선도(시각 노화·중복·역순), timeout을 복귀보다 먼저 평가, 3프레임 복귀
- `serial_core.py` — DRY/LIVE 명시 모드(`enable_live_hardware`), 명령 1건 = 전송 1회, STOP 후 STATUS 확인 전 VEL 금지, FAULT 래치·자동 재ARM 없음
- `tracking_controller_2axis.ino` — 두 값 모두 검사 후 쓰기, 엔코더 경계, 300 ms timeout, Bus_Watchdog

## 9. 정량 결과

| 지표 | 값 |
|---|---|
| 검출률 / 배경 오검출 | 100 % (30/30) / 0 (10) — 실측 |
| 처리 FPS (인지 단독, 노트북) | 30.03 — 실측 |
| Pi 폐루프 FPS, 수평·수직 RMSE, 유효 추적 비율, 복구 성공률·시간 | TODO: 실제 시험 후 삽입 |

## 10. 팀 기여

| 이름 | 역할 | 기여 |
|---|---|---|
| 전승혜 | 팀장 + 검증·문서화 | 시험 조건, 통합 감사·문서, 지표 도구 |
| 김상화 | 인지 | detector·perception_node, 평가 도구, 30/10 대조 |
| 한상준 | 통합 | launch·패키지, 제어 파라미터, recordings |
| 조민혁 | 제어 | control·serial bridge, 2축 펌웨어, 모터 commissioning |

PR·리뷰 링크: team.md

## 11. 한계

- 실제 장비 폐루프 시험(30 s, 가림 5회, 중단 2종, Kp A/B)과 bag 재현 미완료
- 펌웨어 회전 경계가 좁은 bench 값(±7°), 기구 범위 미확정
- Pi 단일 runtime의 처리 부하·FPS 미측정
- 위치를 측정하지 않으므로 명령값 ≠ 실제 각도
