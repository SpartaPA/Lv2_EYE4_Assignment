# Lv2 Module 5 디렉토리 및 담당 업무 가이드

> 프로젝트: `Lv2_EYE4_Assignment`  
> 대상: Lv2 Module 5  
> 목적: 팀원별 작업 영역과 디렉토리 역할을 명확하게 분리하여 통합 과정에서 충돌을 최소화한다.

---

## 1. 프로젝트 전체 구조

```text
lv2_module5/
│
├── README.md
├── report.md
├── team.md
├── presentation.md
│
├── ros2_ws/
│   └── src/
│       └── realsense_tracker/
│           ├── package.xml
│           ├── setup.py
│           ├── setup.cfg
│           ├── resource/
│           │   └── realsense_tracker
│           │
│           ├── realsense_tracker/
│           │   ├── __init__.py
│           │   ├── camera_node.py
│           │   ├── perception_node.py
│           │   ├── control_node.py
│           │   └── opencr_node.py
│           │
│           ├── launch/
│           │   └── tracker.launch.py
│           │
│           └── config/
│               └── tracker.yaml
│
├── firmware/
│   └── opencr/
│       └── README.md
│
├── config/
│   ├── robot.yaml
│   ├── camera.yaml
│   └── opencr.yaml
│
├── results/
│   ├── images/
│   ├── logs/
│   ├── plots/
│   └── metrics.csv
│
└── recordings/
    └── README.md
```

---

# 2. 담당 파트별 기본 원칙

프로젝트는 크게 다음과 같이 구분한다.

| 영역 | 주요 담당 | 주요 업무 |
|---|---|---|
| `ros2_ws/src/realsense_tracker/realsense_tracker/` | 통합 + 인지 + 제어 | ROS 2 Node 구현 |
| `ros2_ws/src/realsense_tracker/launch/` | 통합 | 전체 Node 실행 구성 |
| `ros2_ws/src/realsense_tracker/config/` | 통합 | ROS Node Parameter |
| `firmware/opencr/` | 제어 | OpenCR / Dynamixel 펌웨어 |
| `config/` | 통합 | 프로젝트 전체 하드웨어 설정 |
| `results/` | 전체 | 실험 결과 및 검증 자료 |
| `recordings/` | 전체 | 영상 / rosbag 등 기록 |
| `report.md` | 전체 | 최종 보고서 |
| `presentation.md` | 전체 | 발표 자료 |

---

# 3. `ros2_ws/`

```text
ros2_ws/
└── src/
```

## 역할

ROS 2 프로젝트의 **개발 Workspace**이다.

실제 ROS 2 Node, Launch, Package가 이 영역에 위치한다.

### 담당

**통합 담당이 전체 구조를 관리한다.**

인지/제어 담당자는 자신이 담당하는 Node의 구현에 참여할 수 있지만, Workspace 전체 구조를 임의로 변경하지 않는다.

### 주의

다음 디렉토리는 Git에 올리지 않는다.

```text
ros2_ws/build/
ros2_ws/install/
ros2_ws/log/
```

이들은 `colcon build` 과정에서 자동 생성되는 빌드 결과물이다.

---

# 4. `ros2_ws/src/realsense_tracker/`

```text
realsense_tracker/
├── package.xml
├── setup.py
├── setup.cfg
├── resource/
├── realsense_tracker/
├── launch/
└── config/
```

## 역할

프로젝트의 **메인 ROS 2 패키지**이다.

로봇 시스템을 실제로 실행하는 Node와 Launch 파일이 이곳에 위치한다.

### 주요 담당

**통합 담당**

### 통합 담당 업무

- ROS 2 Package 관리
- Node 구조 관리
- Topic 연결
- Launch 구성
- Node 간 데이터 흐름 관리
- 전체 시스템 실행 테스트
- 인지/제어 코드 통합

---

# 5. `realsense_tracker/`

```text
ros2_ws/src/realsense_tracker/realsense_tracker/
```

실제 Python ROS 2 Node가 들어가는 디렉토리이다.

---

## 5.1 `camera_node.py`

```text
camera_node.py
```

### 담당

**통합 담당**

필요에 따라 인지 담당과 협업한다.

### 역할

RealSense D435에서 데이터를 받아 ROS 2 Topic으로 전달한다.

예:

```text
RealSense D435
      │
      ├── RGB Image
      │
      └── Depth Image
              │
              ▼
        camera_node
              │
              ├── /camera/color/image_raw
              └── /camera/depth/image_raw
```

### 주요 작업

- RealSense 연결
- Camera stream 설정
- RGB 데이터 Publisher
- Depth 데이터 Publisher
- Camera parameter 관리
- Camera 동작 확인

---

# 6. `perception_node.py`

```text
perception_node.py
```

### 담당

**인지 담당**

통합 담당은 Node 인터페이스와 실행 구조를 지원한다.

### 역할

카메라 데이터를 받아 목표물을 탐지하고 위치 정보를 생성한다.

현재 프로젝트의 핵심 대상:

```text
파란색 퍽
```

예:

```text
Camera
   │
   │ RGB / Depth
   ▼
perception_node
   │
   ├── 파란색 퍽 탐지
   ├── 중심점 계산
   ├── 거리 계산
   └── 목표 위치 생성
```

### 주요 작업

- RGB 이미지 처리
- 색상 기반 퍽 탐지
- 퍽 중심 좌표 계산
- Depth 기반 거리 계산
- 목표물 탐지 상태 생성
- 인지 결과 Topic Publish

### 주의

인지 알고리즘 자체와 ROS 2 통신 코드를 가능한 한 분리한다.

---

# 7. `control_node.py`

```text
control_node.py
```

### 담당

**제어 담당**

통합 담당과 협업한다.

### 역할

인지 결과를 받아 로봇이 어떻게 움직여야 하는지 결정한다.

예:

```text
/perception/target
        │
        ▼
 control_node
        │
        ├── 정지
        ├── 전진
        ├── 좌회전
        ├── 우회전
        └── 팔 동작
```

### 주요 작업

- 목표 위치 데이터 Subscribe
- 목표물과 로봇의 상대 위치 판단
- 이동 방향 결정
- 속도 명령 생성
- 정렬 로직
- 접근 로직
- 집기 동작 명령 생성

---

# 8. `opencr_node.py`

```text
opencr_node.py
```

### 담당

**통합 + 제어 담당**

### 역할

ROS 2에서 생성된 제어 명령을 OpenCR로 전달한다.

```text
control_node
     │
     │ ROS 2
     ▼
opencr_node
     │
     │ Serial
     ▼
OpenCR
     │
     ▼
Dynamixel
```

### 주요 작업

- Serial 포트 연결
- OpenCR 통신
- ROS 2 명령 Subscribe
- 명령을 Serial Protocol로 변환
- OpenCR 상태 수신
- 모터 상태 Publish
- 통신 오류 처리

---

# 9. `launch/`

```text
launch/
└── tracker.launch.py
```

### 담당

**통합 담당**

### 역할

프로젝트에 필요한 Node를 한 번에 실행한다.

예:

```bash
ros2 launch realsense_tracker tracker.launch.py
```

실행 결과:

```text
tracker.launch.py
│
├── camera_node
├── perception_node
├── control_node
└── opencr_node
```

### 주요 작업

- Node 실행 구성
- Parameter 전달
- 실행 순서 관리
- 전체 시스템 실행 테스트

---

# 10. ROS 2 `config/`

```text
ros2_ws/src/realsense_tracker/config/
└── tracker.yaml
```

### 담당

**통합 담당**

### 역할

ROS 2 Node에서 사용하는 Parameter를 관리한다.

예:

```yaml
camera:
  resolution: ...
  fps: ...

control:
  linear_speed: ...
  angular_speed: ...

opencr:
  port: ...
  baudrate: ...
```

실제 Parameter는 각 담당자가 필요한 값을 제안하고 통합 담당이 최종 관리한다.

---

# 11. `firmware/opencr/`

```text
firmware/
└── opencr/
```

### 담당

**제어 담당**

### 역할

OpenCR에서 실행되는 Arduino 기반 펌웨어를 관리한다.

```text
ROS 2
  │
  │ Serial
  ▼
OpenCR Firmware
  │
  ├── Dynamixel
  ├── Motor
  └── Sensor
```

### 주요 작업

- OpenCR Arduino 코드
- Serial Protocol
- Dynamixel 제어
- 모터 명령 처리
- 센서 상태 처리
- 모터 상태 반환
- Firmware 빌드 및 업로드
- Hardware 테스트

### 중요

ROS 2 Python 코드와 OpenCR Firmware를 혼합하지 않는다.

```text
ros2_ws/       → Raspberry Pi에서 실행
firmware/      → OpenCR에서 실행
```

---

# 12. `config/`

```text
config/
├── robot.yaml
├── camera.yaml
└── opencr.yaml
```

### 담당

**통합 담당**

각 담당자의 하드웨어 설정 정보를 취합하여 관리한다.

---

## `robot.yaml`

### 내용

로봇 기본 정보 및 공통 설정

예:

```yaml
robot:
  name: ...
  wheel_radius: ...
  wheel_base: ...
```

---

## `camera.yaml`

### 내용

RealSense 설정

예:

```yaml
camera:
  width: ...
  height: ...
  fps: ...
```

### 담당

**인지 + 통합**

---

## `opencr.yaml`

### 내용

OpenCR 및 Dynamixel 관련 설정

예:

```yaml
opencr:
  port: /dev/ttyACM0
  baudrate: ...
```

### 담당

**제어 + 통합**

---

# 13. `results/`

```text
results/
├── images/
├── logs/
├── plots/
└── metrics.csv
```

## 역할

실험 및 테스트 결과를 저장한다.

---

## `results/images/`

### 담당

**전체**

저장 예:

```text
images/
├── detection/
├── camera/
└── system/
```

예:

- 퍽 탐지 결과
- 카메라 화면
- 로봇 동작 결과
- 최종 테스트 사진

---

## `results/logs/`

### 담당

**전체**

예:

```text
logs/
├── ros2/
├── perception/
├── control/
└── opencr/
```

ROS 2 실행 로그, 오류 로그, 테스트 로그 등을 저장한다.

---

## `results/plots/`

### 담당

**전체**

실험 데이터를 그래프로 만든 결과를 저장한다.

예:

- 위치 오차
- 거리 오차
- 제어 응답
- 탐지 성공률
- 처리 시간

---

## `results/metrics.csv`

### 담당

**통합 + 전체**

최종 성능 측정값을 기록한다.

예:

```csv
test,success_rate,error,detection_time
test_01,0.95,0.12,0.08
```

---

# 14. `recordings/`

```text
recordings/
└── README.md
```

### 담당

**전체**

실험 영상 및 ROS 데이터 기록을 관리한다.

예:

```text
recordings/
├── README.md
├── test01/
├── test02/
└── final/
```

대용량 영상이나 rosbag은 Git에 직접 저장하지 않는 것을 원칙으로 한다.

필요한 경우 README에 파일의 저장 위치와 설명을 기록한다.

---

# 15. `report.md`

### 담당

**전체 → 통합 담당이 최종 취합**

최종 보고서 작성 영역이다.

구성 예:

```text
1. 프로젝트 개요
2. 시스템 구성
3. 하드웨어 구성
4. 소프트웨어 구성
5. ROS 2 구조
6. 인지 알고리즘
7. 제어 알고리즘
8. OpenCR / Dynamixel
9. 통합 테스트
10. 결과 분석
11. 문제점 및 개선점
12. 결론
```

각 담당자는 자신의 파트 내용을 작성하고 통합 담당이 최종 취합한다.

---

# 16. `presentation.md`

### 담당

**전체**

최종 발표 자료의 내용을 관리한다.

각 파트 담당자는 자신의 담당 영역을 작성한다.

```text
인지
→ 카메라 및 퍽 탐지

제어
→ 이동 및 모터 제어

통합
→ ROS 2 구조 및 전체 시스템 연결
```

---

# 17. `team.md`

### 담당

**팀 전체**

팀원 역할과 담당 업무를 기록한다.

예:

```text
| 이름 | 담당 | 주요 업무 |
|---|---|---|
| 팀원 A | 인지 | RealSense / 퍽 탐지 |
| 팀원 B | 제어 | 이동 / Dynamixel |
| 희우 | 통합 | ROS 2 / 시스템 통합 |
```

---

# 18. 작업 영역 충돌 방지 규칙

## 원칙 1. 다른 담당자의 핵심 코드를 임의로 수정하지 않는다.

예:

```text
인지 담당
→ perception_node.py

제어 담당
→ control_node.py

통합 담당
→ launch / package / 전체 연결
```

수정이 필요하면 담당자와 먼저 협의한다.

---

## 원칙 2. Topic 인터페이스는 임의로 변경하지 않는다.

예:

```text
/perception/target
```

을 다른 이름으로 변경해야 한다면 팀원 전체에게 공유한다.

---

## 원칙 3. 하드웨어 설정은 `config/`에서 관리한다.

코드 안에 다음처럼 하드코딩하지 않는 것을 권장한다.

```python
port = "/dev/ttyACM0"
```

가능하면:

```text
config/opencr.yaml
```

에서 관리한다.

---

## 원칙 4. 빌드 결과물은 Git에 올리지 않는다.

```text
build/
install/
log/
```

은 커밋하지 않는다.

---

## 원칙 5. 실험 결과는 `results/`에 저장한다.

```text
코드       → ros2_ws/
펌웨어     → firmware/
설정       → config/
실험 결과  → results/
영상/기록  → recordings/
문서       → *.md
```

---

# 19. Git 작업 영역

팀원은 기본적으로 자신의 Branch에서 작업한다.

```text
main
 │
 ├── member-a
 ├── member-b
 └── sangjun
```

작업 흐름:

```text
Branch 생성
    ↓
작업
    ↓
git status
    ↓
git add
    ↓
git commit
    ↓
자신의 Fork/Remote에 백업
    ↓
팀 Remote에 반영
```

작업 전에는 항상 최신 상태를 확인한다.

```bash
git status
git fetch origin
```

공유 파일을 수정해야 하는 경우 다른 팀원의 작업과 충돌하지 않는지 확인한다.

---

# 20. 전체 시스템에서 각 담당자의 위치

```text
                         ┌──────────────────┐
                         │  RealSense D435  │
                         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │   Camera Node    │
                         │    [통합]        │
                         └────────┬─────────┘
                                  │
                              RGB/Depth
                                  │
                         ┌────────▼─────────┐
                         │ Perception Node  │
                         │     [인지]       │
                         └────────┬─────────┘
                                  │
                            Target Data
                                  │
                         ┌────────▼─────────┐
                         │   Control Node   │
                         │     [제어]       │
                         └────────┬─────────┘
                                  │
                              Command
                                  │
                         ┌────────▼─────────┐
                         │   OpenCR Node    │
                         │  [통합 + 제어]   │
                         └────────┬─────────┘
                                  │
                                Serial
                                  │
                         ┌────────▼─────────┐
                         │      OpenCR      │
                         │     [제어]       │
                         └────────┬─────────┘
                                  │
                              Dynamixel
```

---

# 21. 한눈에 보는 담당 영역

```text
┌─────────────────────────────────────────┐
│                 통합                    │
│                                         │
│  ROS 2 Workspace                        │
│  Package                                │
│  Camera Node                            │
│  Launch                                 │
│  Config                                 │
│  Topic 연결                             │
│  전체 시스템 테스트                     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│                  인지                   │
│                                         │
│  RealSense 데이터 처리                  │
│  파란색 퍽 탐지                         │
│  위치/거리 계산                         │
│  Perception Node                        │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│                  제어                   │
│                                         │
│  Control Node                            │
│  이동 제어                              │
│  Dynamixel 제어                         │
│  OpenCR Firmware                        │
│  모터/센서 통신                         │
└─────────────────────────────────────────┘
```

---

# 22. Phase별 담당

| Phase | 주요 작업 | 주 담당 |
|---|---|---|
| Phase 1 | 환경 구축 | 통합 |
| Phase 2 | ROS 2 구조 구축 | 통합 |
| Phase 3 | RealSense / 퍽 탐지 | 인지 |
| Phase 4 | 인지 → 제어 연결 | 인지 + 제어 + 통합 |
| Phase 5 | OpenCR / Dynamixel | 제어 |
| Phase 6 | 전체 통합 | 통합 + 전체 |
| Phase 7 | 실제 미션 테스트 | 전체 |
| Phase 8 | 결과 / 문서화 | 전체 |

---

# 23. 최종 작업 원칙

이 프로젝트의 기본적인 코드 소유 영역은 다음과 같이 한다.

```text
camera_node.py
    → 통합

perception_node.py
    → 인지

control_node.py
    → 제어

opencr_node.py
    → 통합 + 제어

tracker.launch.py
    → 통합

tracker.yaml
    → 통합

config/*.yaml
    → 통합 관리 + 각 담당 설정 협의

firmware/opencr/
    → 제어

results/
    → 전체

report.md
presentation.md
    → 전체
```

### 핵심

> **각 담당자는 자신의 기능을 구현하고, 통합 담당은 각 기능을 ROS 2를 통해 하나의 시스템으로 연결한다.**

따라서 개발 순서는:

```text
인지 구현
   ↓
제어 구현
   ↓
각각 단독 테스트
   ↓
ROS 2 Topic 연결
   ↓
통합 테스트
   ↓
OpenCR 연결
   ↓
실제 로봇 테스트
```

로 진행한다.