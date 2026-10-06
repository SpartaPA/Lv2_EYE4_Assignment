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
