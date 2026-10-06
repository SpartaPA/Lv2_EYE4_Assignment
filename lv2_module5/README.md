# Module 5 — 비전 객체 추적 시스템

## 목적과 개발 기준

D435 Color 영상의 단일 색상 목표를 HSV·Contour로 검출하고, 영상 중심 오차를 줄이는 Pan/Tilt 2축 추적을 구현한다. 목표 소실·입력 중단·제어 통신 중단의 안전 정지와 복구를 검증한다.

개발 기준은 제공된 `팀업무_네비게이터_FINAL_개발기준.md`와 `directory_workflow_guide_FINAL_개발기준.md`이다. 발제문의 모터 2개 조건과 팀 확정 요구에 따라 두 축 모두 필수다. 발제문에 남은 1축 기본·2축 선택 문구보다 이 팀 기준을 우선한다.

현재 노드·Launch·설정은 빈 초기 파일이며 실행·장비 검증은 TODO다. 저장소의 기존 `팀업무_네비게이터.md`, `directory_workflow_guide.md`는 FINAL 기준과 대조가 필요한 이전 문서다.

## 시스템과 장비

```text
RealSense D435
  → RealSense ROS 2 wrapper (realsense2_camera)
  → Color / aligned Depth / CameraInfo
  → perception_node
  → /target (geometry_msgs/msg/PointStamped)
  → control_node
  → /control/pan_tilt_cmd
  → opencr_node → Serial → OpenCR
  → Pan Dynamixel + Tilt Dynamixel
```

영상·인지 PC에 D435를 USB 3로 연결하고 perception/control을 실행한다. Raspberry Pi에서 opencr_node와 OpenCR 빌드·업로드·시리얼 작업을 수행한다. PC↔Pi의 ROS_DOMAIN_ID·RMW·DDS를 확인한다. SSH 접속은 ROS 메시지 전달을 대신하지 않는다.

장비: D435, Dynamixel 2개, OpenCR, Raspberry Pi, 영상 처리 PC, 규격 전원, Pan/Tilt 브래킷. 실제 모델·전원·고정 상태는 TODO.

별도 `camera_node.py`는 기본 구조에 사용하지 않는다. 기존 빈 파일은 남아 있으나 perception이 wrapper Topic을 직접 구독하도록 구현한다. Depth는 유효 거리 확인·기록에 사용하며 `/target.point.z`에 넣지 않는다.

## 역할과 작업 위치

| 역할 | 담당 | 작업 |
| --- | --- | --- |
| 팀장 + 검증·문서화 | 전승혜 | 시험 조건, 지표·증빙, 문서, PR 병합·제출 |
| 인지 | 김상화 | wrapper 데이터 유효성, perception_node, HSV·Contour, `/target` |
| 통합 | 한상준 | wrapper 실행·Launch·패키지, PC↔Pi DDS, opencr_node·Serial, bag |
| 제어 | 조민혁 | control_node, 양축 제한·정지·복귀, OpenCR firmware·watchdog |

협업 규칙과 실제 Issue·PR·Review 기록은 [team.md](team.md)에 연결한다.

## ROS 2 인터페이스

| 방향 | Topic | Type | 의미 |
| --- | --- | --- | --- |
| wrapper → perception | TODO: 실제 Color Topic | `sensor_msgs/msg/Image` | 색상 검출 입력 |
| wrapper → perception | TODO: 실제 aligned Depth Topic | `sensor_msgs/msg/Image` | 정렬 Depth 유효성 |
| wrapper → perception | TODO: 실제 CameraInfo Topic | `sensor_msgs/msg/CameraInfo` | 카메라 정보 |
| perception → control | `/target` | `geometry_msgs/msg/PointStamped` | 정규화 오차·면적비 |
| control → 전체 | `/tracking_status` | `std_msgs/msg/String` | IDLE / TRACKING / LOST |
| control → opencr | `/control/pan_tilt_cmd` | `realsense_tracker_interfaces/msg/PanTiltCommand` | 팀 기준의 양축 속도·정지 명령, 구현 TODO |

모터 명령의 팀 기본안은 Velocity Mode이며 필드는 `std_msgs/Header header`, `bool stop`, `float32 pan_velocity_rad_s`, `float32 tilt_velocity_rad_s`이다. 단위는 rad/s, 정지는 `stop=true`와 양축 속도 0이다. Custom Message는 모터 명령에만 사용한다. Interface 패키지·`package.xml`·`CMakeLists.txt`·`rosidl_generate_interfaces`는 아직 없으며 통합 담당 구현 TODO다. Serial 형식·단위 변환 위치·발행 주기·watchdog 시간도 TODO다.

### `/target` 규약

```text
point.x = ex = (cx - W/2) / (W/2)
point.y = ey = (cy - H/2) / (H/2)
point.z = area_ratio = contour_area / (W × H)
```

W/H는 실제 프레임 크기다. ex 양수는 오른쪽, 음수는 왼쪽이고 ey 양수는 아래쪽, 음수는 위쪽이다. 값은 정규화된 무차원 값이다.

- 미검출은 `point.z=0`; 이때 x/y로 계속 추적하지 않는다.
- 영상 처리마다 발행하며 정상 영상의 미검출도 z=0을 발행한다.
- `header.stamp`는 원본 영상 시각을 유지한다. 촬영 시각을 모르면 영상 수신 시각임을 기록한다. 실제 frame_id는 TODO다.
- 이전 영상에 새 timestamp를 붙이거나 이전 좌표를 새 검출로 재사용하지 않는다.
- 기본 QoS는 best-effort, depth 1이며 발행·구독 호환을 확인한다.

### Pan/Tilt와 안전 정지

```text
pan_command  = pan_direction × Kp_pan × ex
tilt_command = tilt_direction × Kp_tilt × ey
```

각 축에 direction, Kp, speed limit, angle limit, deadband를 적용한다. 범위 끝에서 바깥 방향 명령을 금지한다. 실제 영상 오차가 줄어드는 방향을 작은 명령으로 확인하며 수치는 확인 전 TODO다.

| 상태/조건 | 동작 |
| --- | --- |
| IDLE: 시작 전 또는 명시적 중지 | 새 추적 명령을 내보내지 않음 |
| TRACKING: 신선한 목표 검출 | 제한 범위 안에서 양축 추적 |
| z=0 | LOST, Pan/Tilt 즉시 정지 |
| 0.5초 동안 신선한 `/target` 없음 | LOST, Pan/Tilt 정지 |
| control→opencr 명령 중단 | OpenCR 또는 모터 측 watchdog으로 양축 정지; 마지막 명령 유지 금지 |
| LOST에서 신선한 목표 3프레임 연속 검출 | TRACKING 복귀 |

복구 대기 중 양축 정지를 유지한다. 오래된·중복 입력을 복귀 프레임으로 세지 않는다. 복구는 현재 시야 안에 재등장한 목표를 대상으로 한다.

## 디렉토리 안내

| 위치 | 용도와 현재 상태 |
| --- | --- |
| `ros2_ws/src/realsense_tracker/` | 노드·패키지·Launch·`config/tracker.yaml`, 현재 빈 초기 파일 |
| `firmware/opencr/` | 제어 담당 firmware·watchdog·업로드 안내, 구현 TODO |
| `config/camera.yaml`, `config/opencr.yaml` | 카메라·장치 설정, 현재 빈 파일 |
| `config/test.yaml` | 사전 시험 조건; ROS 노드 파라미터 파일과 구분 |
| `config/robot.yaml` | 기존 빈 파일, 현재 Pan/Tilt 기준의 설정 용도 정리 TODO |
| `config/vision.yaml`, `config/control.yaml` | FINAL 기준의 인지·양축 제어 설정, 생성·연결 TODO |
| `results/` | 실측 이미지·로그·그래프·CSV 저장 위치; 기존 파일과 측정 완료 여부는 별개 |
| `recordings/README.md` | bag·영상 위치와 모터 비활성 재현 안내 |
| `report.md`, `presentation.md`, `team.md` | 분석·발표·협업 증빙 |

`build/`, `install/`, `log/` 생성물은 Git에 올리지 않는다. 실제 시험 전 results 데이터나 CSV row·그래프·bag을 예시 결과로 채우지 않는다.

## 실행 및 장비 확인 TODO

실제 실행 명령: TODO (wrapper 설치·호환, 패키지·Launch 구현과 장비 확인 후 기록).
확인 순서: 환경·장치 → wrapper → 실제 Topic·데이터 → 모터 비활성 모의 입력 → 제어·Serial·watchdog → 제한 범위의 실물 시험.

wrapper 실행 후 `ros2 topic list`와 `ros2 topic type <확인한 Topic>`으로 이름·형식을 확인한다. 결과를 `config/camera.yaml`의 `color_topic`, `aligned_depth_topic`, `camera_info_topic`에 기록하고 설정 또는 Launch remap으로 전달한다. 추측한 카메라 Topic을 하드코딩하지 않는다.

| 확인 항목 | 상태 |
| --- | --- |
| PC/Pi 실제 OS·ROS 2 버전, ROS_DOMAIN_ID·RMW·DDS | TODO; 발제문의 Pi OS 버전 표기가 달라 장비·운영 공지 확인 필요 |
| D435 serial·firmware·SDK/wrapper version·USB speed | TODO |
| 실제 Color/Depth profile·해상도·encoding·CameraInfo·frame_id·stamp | TODO |
| Dynamixel 모델·Pan/Tilt ID·baud·protocol·direction | TODO |
| 양축 Kp·속도/각도 제한·deadband·단위 변환·watchdog 시간 | TODO |
| wrapper·전체 Launch·OpenCR 빌드/업로드·모터 비활성 실행 명령 | TODO |

## 검증 계획

[test.yaml](config/test.yaml)에 정상 추적 30초 이상, 약 2초 가림 5회, 입력 중단·제어 통신 중단 각각 1회 이상, A/B 양축 Kp 세트 각각 3회(총 6회)를 고정한다. Kp는 장비·제어 담당 확인 후 시험 전에 확정한다. 대상·거리·조명·해상도·이동 순서·산식·로그 컬럼도 시험 전에 확정한다: TODO.

복구 성공 기준은 재등장 후 3초 이내 TRACKING 복귀다. 목표 존재 최소 30프레임, 목표 없음 최소 10프레임을 사람이 대조한다.

측정 지표: processing FPS(처리 프레임 수/경과 초), detection rate(올바른 검출/목표 존재 평가 프레임), background false detection(목표 없는 프레임의 오검출 수), horizontal RMSE `sqrt(mean(ex²))`, vertical RMSE `sqrt(mean(ey²))`(검출·TRACKING 구간), recovery success rate(3초 내 복귀/전체 가림 회차), recovery time(복귀 시각−재등장 시각). 유효 추적 비율의 분모·포함 구간은 TODO다. 실패 회차도 포함하고 복구 실패를 0초로 기록하지 않는다.

실제 수치·로그·이미지·그래프·bag·하드웨어 결과는 실측 후 기록한다. 성공과 소실·복귀 bag은 각각 10~30초 기록하고 다른 팀원이 모터 비활성 상태에서 재현한다. 실제 record/replay 명령과 확인 기록은 TODO다.
