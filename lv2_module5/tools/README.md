# 인지 파트: 검출 노드와 도구 (담당: 인지 김상화)

RealSense 영상에서 파란색 목표(퍽)를 HSV 색상으로 찾아, 화면 중심 대비 어긋남(`ex`, `ey`)을 계산합니다.

| 위치 | 역할 |
|---|---|
| `ros2_ws/src/realsense_tracker/realsense_tracker/detector.py` | 검출 알고리즘 (ROS·카메라와 무관) — 노드와 도구가 함께 사용 |
| `ros2_ws/src/realsense_tracker/realsense_tracker/perception_node.py` | ROS 2 인지 노드 — `/target` 발행 |
| `ros2_ws/src/realsense_tracker/config/tracker.yaml` | 인지 파라미터 (`perception_node` 항목) |
| `config/camera.yaml` | 카메라 해상도·fps (도구에서 사용) |
| `tools/hsv_tuning.py` | HSV 범위 튜너 (트랙바) → `tracker.yaml`에 저장 |
| `tools/image_capture.py` | 정상·미검출·가림 장면 검출 결과 저장 → `results/` |
| `tools/common.py` | 도구 공통 (경로, 설정 읽기, RealSense 카메라) |

검출 순서: 영상 → 블러 → HSV 변환 → 색 마스크 → 잡음 제거 → 외곽선 → **가장 큰 덩어리 1개 선택** → 중심 계산

---

## 1. `/target` 메시지 약속 (발제문 지정 — 이름·형식 임의 변경 금지)

`geometry_msgs/msg/PointStamped`

| 필드 | 값 | 미검출일 때 |
|---|---|---|
| `point.x` | `ex` = 화면 중심 기준 가로 어긋남, −1(왼쪽 끝) ~ +1(오른쪽 끝) | 0 |
| `point.y` | `ey` = 화면 중심 기준 세로 어긋남, −1(위쪽 끝) ~ +1(아래쪽 끝) | 0 |
| `point.z` | `z` = 목표 넓이 ÷ 화면 넓이 (검출되면 항상 0보다 큼) | **0 → 미검출 신호** |
| `header` | 입력 컬러 영상의 시각·좌표계 | 같음 |

- 제어는 **`z == 0`이면 미검출**로 판단합니다. (`x = y = 0`만으로는 "정중앙"과 구분되지 않음)
- 영상이 들어올 때마다 1번씩 발행합니다. 영상이 끊기면 발행도 멈춥니다.

## 2. 인지 노드 실행 (`perception_node`)

```bash
cd lv2_module5/ros2_ws
colcon build --packages-select realsense_tracker
source install/setup.bash
ros2 run realsense_tracker perception_node --ros-args \
  --params-file src/realsense_tracker/config/tracker.yaml
```

- 구독: `/camera/color/image_raw` (bgr8 / rgb8), `use_depth: true`이면 `/camera/depth/image_raw` (컬러에 정렬된 16UC1 / 32FC1)
- 확인 화면: `-p publish_debug_image:=true`로 실행하면 `/perception/debug_image`에 검출 결과를 그린 영상이 나옵니다.
  (`ros2 run rqt_image_view rqt_image_view`로 확인)
- 필요한 패키지: `rclpy`, `sensor_msgs`, `geometry_msgs`, `message_filters`, `python3-numpy`, `python3-opencv`
  (`cv_bridge`는 쓰지 않고 영상을 직접 변환)

### 영상 구독 방식 (`image_reliable`)

- 기본값 `true` (reliable). 노트북(Fast DDS 기본 설정)에서 실측한 결과, **640×480 영상은 다른 프로세스에서 받을 때
  reliable 구독일 때만 전달**되고 best effort 구독으로는 한 장도 전달되지 않았습니다.
- camera_node의 발행 방식과 맞아야 합니다. **reliable 구독 + best effort 발행은 연결되지 않습니다.**
  camera_node가 best effort로 발행한다면 `image_reliable: false`로 바꾸세요.

### 파라미터 (`tracker.yaml`의 `perception_node`)

| 이름 | 기본값 | 뜻 |
|---|---|---|
| `hsv_lower`, `hsv_upper` | `[93, 120, 35]`, `[130, 255, 255]` | 목표 색 HSV 범위 (OpenCV: H 0~179) |
| `min_area_ratio` | 0.002 | 화면 넓이 대비 최소 크기 |
| `blur_ksize`, `morph_ksize` | 5, 5 | 블러·잡음 제거 크기 |
| `use_depth` | false | 깊이도 구독해 거리(dist)를 확인 화면·로그에 표시 |
| `depth_unit_m` | 0.001 | 16UC1 깊이 값 1의 길이(m) |
| `depth_min_valid_ratio`, `depth_max_spread_cm` | 0.5, 5.0 | 이 기준을 못 넘으면 거리를 믿을 수 없다고 보고 비움 |
| `publish_debug_image` | false | 확인 화면 발행 |
| `image_reliable` | true | 영상 구독 방식 (위 설명) |

## 3. 도구 (노트북, ROS 없이 RealSense 직접 사용)

ROS의 camera_node가 RealSense를 쓰고 있으면 도구가 카메라를 열 수 없습니다. (카메라는 한 프로그램만 사용 가능)

### 설치 (한 번만)

```bash
cd lv2_module5
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
```

### 3-1. HSV 범위 조절 (`hsv_tuning.py`)

```bash
python tools/hsv_tuning.py
```

목표만 흰색으로 깔끔하게 보이도록 트랙바를 맞춘 뒤 `s`로 저장, `q`로 종료합니다.
`tracker.yaml`의 `hsv_lower`, `hsv_upper`, `min_area_ratio`만 바뀌고 주석과 다른 항목은 그대로 유지됩니다.

| 트랙바 | 뜻 | 조절 요령 |
|---|---|---|
| H 최소 / 최대 | 색상 범위 (파랑 ≈ 100~130) | 비슷한 색 물체가 잡히면 범위를 좁힘 |
| S 최소 / 최대 | 채도 (0 = 흰색·회색) | 흰 배경이 잡히면 S 최소를 올림 |
| V 최소 / 최대 | 밝기 (0 = 검정) | 그림자가 잡히면 V 최소를 올림 |
| 최소 크기 | 화면 넓이 × (값 ÷ 10000) | 작은 잡티가 잡히면 올림 |

트랙바 이름이 안 보이면 한글 글꼴(`fonts-noto-cjk`)이 설치되어 있는지 확인하세요.

### 3-2. 장면별 검출 결과 저장 (`image_capture.py`)

```bash
python tools/image_capture.py              # 화면이 있는 노트북
python tools/image_capture.py --headless   # 화면 없는 SSH (터미널에 n/e/o/q 입력 후 Enter)
```

| 키 | 장면 |
|---|---|
| `n` | normal — 목표가 잘 보이는 상태 |
| `e` | empty — 목표를 치운 상태 (`found=False`가 정상) |
| `o` | occluded — 목표 일부를 가린 상태 |
| `q` | 종료 |

저장 위치:
- `results/images/detection/<장면>_<시각>_{raw,mask,det}.png` (원본 / 색 마스크 / 검출 결과)
- `results/logs/perception/log.csv` — 열: `time, scene, found, ex, ey, z, dist_cm, n_candidates, width, height, hsv_ranges, min_area_ratio`
- 같은 초에 같은 장면을 다시 저장하면 이름 뒤에 `_2`, `_3`이 붙습니다.

## 4. 알아둘 점

- **목표는 가장 큰 덩어리 1개만 고릅니다.** 비슷한 색의 더 큰 물체(남색, 하늘색 등)가 있으면 그쪽을 목표로 잡을 수 있습니다.
  화면의 `candidates`가 2 이상이면 다른 후보가 있다는 뜻입니다.
- **`z`는 거리가 아닙니다.** 거리의 제곱에 반비례하고, 목표가 가려지면 작아집니다.
- **거리(dist_cm) 실측 결과** (D435, 640×480):
  - 가린 것이 없으면 약 17cm ~ 68cm에서 오차 3% 이내 (17cm보다 가까운 거리는 측정하지 않음)
  - 목표 바로 앞을 손으로 가려도 거리는 정확
  - 손 같은 물체가 **카메라 가까이**에서 가리면 거리를 잴 수 없음 (적외선 카메라 두 대 중 한쪽 시야만 가려짐)
    → 틀린 값 대신 `--`(빈칸)가 나오도록 `depth_*` 두 기준으로 걸러냄
  - 화면 왼쪽 끝 부근은 RealSense 특성상 깊이가 측정되지 않아 `--`가 나올 수 있음
