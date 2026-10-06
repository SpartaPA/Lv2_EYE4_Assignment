## Pan/Tilt DYNAMIXEL 식별 결과

- 확인일: 2026-10-06
- 확인 방법: OpenCR의 `dxl_discovery` 펌웨어로 스캔
- 카메라: RealSense D435, 기구에 장착됨
- 축과 ID의 대응: 실제 장착 상태를 기준으로 담당자가 확인

| 축 | 스캔 모델명 | 모델 번호 | ID | DYNAMIXEL baud rate | 프로토콜 |
|---|---|---:|---:|---:|---:|
| Pan — 좌우 | XM430-W350 | 1020 | 11 | 1000000 | 2.0 |
| Tilt — 상하 | XM430-W350 | 1020 | 12 | 1000000 | 2.0 |

### 통신 구간별 설정

| 구간 | 연결 | Baud rate |
|---|---|---:|
| Raspberry Pi ↔ OpenCR | USB 시리얼 | 115200 |
| OpenCR ↔ DYNAMIXEL | DYNAMIXEL 버스 | 1000000 |

두 baud rate는 서로 다른 통신 구간의 설정이므로 같을 필요가 없다.

OpenCR USB 장치 경로:

`/dev/serial/by-id/usb-ROBOTIS_OpenCR_Virtual_ComPort_in_FS_Mode_FFFFFFFEFFFF-if00`

### 검증 범위

- 두 모터가 서로 다른 ID로 응답함을 확인했다.
- 두 모터의 통신 속도와 프로토콜이 같음을 확인했다.
- 스캔 중 모터 제어 레지스터를 변경하지 않았다.
- 운전 모드, 토크 활성화 상태, 위치·속도 피드백, 실제 방향,
  각도 제한 및 물리적 정지는 아직 검증하지 않았다.

### 빌드 호환성 수정

ARM GCC 14.2.1 환경에서 Arduino의 min/max 매크로와
C++ 표준 라이브러리의 이름 충돌을 해결하기 위해 다음 패치를 적용했다.

- `firmware/opencr/patches/workbench_minmax.patch`
- `firmware/opencr/patches/sdk_minmax.patch`

패치 적용 후 discovery 펌웨어 컴파일에 성공했다.

### 모터 식별 시험 증거

[모터 스캔 원본 로그](../results/logs/opencr/discovery_sdk_fix_20261006_103249/scan.log)

### 모터 상태 읽기 시험 — 2026-10-06

- 시험 방식: 제어 레지스터 쓰기 없이 상태 조회
- 원본 증거: [inspect.log](../results/logs/opencr/inspect_20261006_110144/inspect.log)

| 항목 | Pan (ID 11) | Tilt (ID 12) |
|---|---:|---:|
| 모델 번호 | 1020 | 1020 |
| 프로토콜 | 2.0 | 2.0 |
| Operating_Mode | 1 | 1 |
| Drive_Mode | 0 | 0 |
| Torque_Enable | 0 | 0 |
| Homing_Offset | 0 | 0 |
| Min_Position_Limit | 0 | 0 |
| Max_Position_Limit | 4095 | 4095 |
| Velocity_Limit | 200 | 200 |
| Present_Position | 3172 | 3249 |
| Present_Velocity | 0 | 0 |
| Present_Input_Voltage | 120 | 121 |
| Present_Temperature | 31 | 32 |
| Hardware_Error_Status | 0 | 0 |

두 모터 모두 속도 제어 모드이며, 조회 시 토크는 비활성화 상태였다.
모든 조회가 성공했고 하드웨어 오류 비트는 보고되지 않았다.

현재 위치는 시험 당시의 엔코더 값이며 중립 위치 또는 안전 가동 범위로
확정하지 않았다. 실제 구동 방향, 기구적 가동 범위, 정지 성능은 미검증이다.
