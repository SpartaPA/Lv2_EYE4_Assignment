# ROS repository dry 통합 시험

## 구현 범위

2026-10-06: 업로드된 realsense_tracker package.xml/setup.py/setup.cfg와
control_node.py/opencr_node.py는 빈 파일이었다. 본 변경은 제어 코드와
모의 bridge, 인터페이스 생성 package, 별도 프로세스 시험을 추가한다.
기존 tracking_control과 camera/perception/tracker.launch.py는 변경하지 않는다.
control_dry.launch.py는 새 모의 제어용 launch이며 실제 영상 추적 launch가 아니다.

- 입력 /target: PointStamped, x/y는 영상 오차, z는 면적 비율.
- 출력 /control/pan_tilt_cmd: PanTiltCommand, motor-native rad/s.
- 상태 /tracking_status: IDLE/TRACKING/LOST.
- /opencr/dry_status: String(JSON), 모의 bridge 처리 결과, 실제 모터 피드백 아님.
- opencr_node는 dry_run=true만 지원한다. false는 시작 오류다.
- 시리얼 장치 초기화/열기/쓰기와 ARM 자동 실행은 구현하지 않았다.
- 목표 소실 0.5초, 3프레임 복귀, deadband 0.03, 속도 상한 0.05 rad/s.
- 초기 Kp_pan/Kp_tilt=0.1. A/B 게인 실험은 별도 수행해야 한다.
- dry bridge 명령 타임아웃과 원본 시각 최대 지연은 0.15초.

## 실행

OpenCR를 토크 해제한 뒤 카메라를 지지하고 USB 연결을 분리한다.
새 SSH 터미널에서 ROS base만 source한다. 과거 pa-ros-mock-ws overlay를 source하지 않는다.
ROS_DOMAIN_ID=77과 LOCALHOST discovery는 시험 격리를 위한 설정이다.
실제 PC–Pi 통신 시험에서는 별도 도메인/discovery 설정을 다시 확인한다.

```bash
source /opt/ros/lyrical/setup.bash
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_LOCALHOST_ONLY=1

REPO_ROOT="$HOME/git/Lv2_EYE4_Assignment"
WS="$REPO_ROOT/lv2_module5/ros2_ws"
RUN_ID="ros_repository_dry_$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$REPO_ROOT/lv2_module5/results/logs/ros/$RUN_ID"
mkdir -p "$LOG_DIR"
set -o pipefail
cd "$WS"

PYTHONPATH="$WS/src/realsense_tracker" \
  python3 -m unittest discover -s src/realsense_tracker/test -v \
  2>&1 | tee "$LOG_DIR/core_tests.log"
```

위 시험 통과 후:

```bash
colcon build --symlink-install \
  --base-paths src/realsense_tracker src/realsense_tracker_interfaces \
  --packages-select realsense_tracker_interfaces realsense_tracker \
  2>&1 | tee "$LOG_DIR/build.log"
```

빌드 성공 후:

```bash
source "$WS/install/setup.bash"
ros2 pkg prefix realsense_tracker
ros2 pkg prefix realsense_tracker_interfaces
ros2 interface show realsense_tracker_interfaces/msg/PanTiltCommand
ros2 run realsense_tracker test_control_dry --output-dir "$LOG_DIR" \
  2>&1 | tee "$LOG_DIR/ros_tests.log"
```

두 prefix는 이 repository workspace의 install 아래를 가리켜야 한다.
시험 runner가 control_node와 opencr_node를 각기 별도 subprocess로 시작한다.
수동 launch 또는 이전 mock 노드를 동시에 실행하지 않는다.

기대 결과:

```text
ALL REPOSITORY SEPARATE-PROCESS DRY CHECKS PASSED; SERIAL_OPENED=FALSE
```

7개 입력, 3프레임 복귀, 실제 제어 subprocess 종료 후 bridge 영속도,
dry_run=false 거부를 확인한다. hardware_mode_rejected.log에 기록되는
RuntimeError는 의도한 거부 시험이며 전체 PASS일 때 정상이다.
모든 자식 process는 성공/실패 후 정리된다. 기록 파일은 덮어쓰지 않으므로
재시도 시 새 RUN_ID/LOG_DIR를 사용한다.

## 증거

- core_tests.log, build.log, ros_tests.log
- control_node.log, opencr_node.log, hardware_mode_rejected.log
- commands.csv: dry bridge 수신·타임아웃 기록, 단위 rad/s

serial_opened=False는 본 bridge의 코드 경로를 뜻한다. 시스템의 다른 process
포트 접근이나 실제 모터 상태를 감사하는 값은 아니다. 실제 bus/전원 고장,
정지 지연, 경계 제한, PC–Pi 네트워크, 카메라 추적은 별도 시험한다.
이전 FAULT 원인 가설은 속도 6에 대한 UNEXPECTED_SPEED이지만 최초 이벤트가
없어 확정하지 않는다. 해당 보호 임계값과 firmware는 본 변경에서 수정하지 않는다.

통과 로그를 확인한 뒤 소스/설정/문서/시험 증거를 선택하여 commit한다.
기존 오래된 untracked 시험 디렉터리를 한꺼번에 추가하지 않는다.
