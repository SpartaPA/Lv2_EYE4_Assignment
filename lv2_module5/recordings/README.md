# recordings — 문제 5 bag 기록·재현

실제 bag을 만들기 전에는 아래 표를 채우지 않는다 (2026-10-07 현재 기록된 bag 없음).
bag·영상 파일은 용량 때문에 Git에 올리지 않는다(.gitignore). 팀 공유 드라이브에 올리고 링크·체크섬을 적는다.

## 1. 기록 (Raspberry Pi)

절차와 사전조건: [../README.md 18절](../README.md#18-bag-record). 대표 성공(`success_NN`)과 소실·복귀(`lost_NN`)를 각각 10~30 s.

```bash
RUN=success_01
ros2 bag record -o ~/bags/$RUN \
  /camera/camera/color/image_raw /camera/camera/color/camera_info \
  /target /tracking_status /control/pan_tilt_cmd /opencr/bridge_status
ros2 bag info ~/bags/$RUN
du -sh ~/bags/$RUN && (cd ~/bags && tar -cf - $RUN | sha256sum)   # 크기·체크섬
git -C ~/git/Lv2_EYE4_Assignment rev-parse --short HEAD          # 기준 commit
```

같은 실행의 시리얼 로그: 실행 전 `opencr_live.yaml`의 선택적 `csv_path`에 `$HOME/runs/${RUN}_serial.csv`의 실제 절대경로 지정, 추적 CSV: `tools/tracking_logger.py --run-id $RUN`.

## 2. 재현 (모터 출력 OFF)

절차: [../README.md 19절](../README.md#19-bag-replay) — 정상 launch 종료 → 카메라 지지 → 모터 전원 OFF·OpenCR USB 출력 경로 분리 → opencr_node·control_node 미실행 확인 → 모든 replay 터미널에 격리 `ROS_DOMAIN_ID`. **정상 tracker.launch.py는 replay에 사용하지 않는다.**

| 재현 | 입력 | 출력 | 비교 대상 |
|---|---|---|---|
| A. 입력 재처리 | bag의 `/camera/camera/color/image_raw`만 → perception_node (`-r /target:=/target_replay`, `use_sim_time:=true`, `--clock`) | `<RUN>_reprocess.csv`, 재처리 이미지 | 원래 `<RUN>.csv`의 검출·ex/ey 경향 |
| B. 결과 재분석 | bag의 `/target`, `/tracking_status`, `/control/pan_tilt_cmd` | `<RUN>_reanalysis.csv` → analyze_tracking.py | 실시간 성능표와 지표 일치 여부 |

저장된 `/target`과 새 검출 결과를 같은 토픽에 섞지 않는다. 저장된 `/target`을 보기만 한 것은 입력 재처리가 아니다.

## 3. 메타데이터 (bag마다 1행 — 실제 값만)

| run ID | 목적 | bag 위치(링크) | 기간 [s] | 토픽·메시지 수 | 해상도 | 설정(commit의 config) | 기준 commit | 크기 | sha256 | 시리얼 로그 |
|---|---|---|---|---|---|---|---|---|---|---|
| (없음) | | | | | | | | | | |

## 4. 재현 기록 (작성자가 아닌 팀원)

| run ID | 재현 종류(A/B) | record 명령 | replay 명령 | 확인자 | 날짜 | 기준 commit | 결과 (일치·차이) |
|---|---|---|---|---|---|---|---|
| (없음) | | | | | | | |
