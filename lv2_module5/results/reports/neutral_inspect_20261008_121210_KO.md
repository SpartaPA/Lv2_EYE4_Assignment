# LIVE 준비: 실제 엔코더 중립 검사

## 실행 정보

- 실행 ID: neutral_inspect_20261008_121210
- 검사 펌웨어: commissioning/dxl_inspect/dxl_inspect.ino
- 소스 SHA-256: d5723d423c0591220777da2f991ed213e531ca5453d071cf151835ea5bbc7423
- 빌드 성공 및 OpenCR 업로드 CRC OK 확인.
- 모터 전원을 인가한 상태에서 r 명령으로 ID 11/12 레지스터를 읽었다.
- 검사 스케치는 모터 제어 레지스터 쓰기를 수행하지 않는다.
- 제출된 출력은 1회 측정이며 반복 측정으로 기록하지 않는다.

## 측정 결과

| 항목 | Pan ID11 | Tilt ID12 |
|---|---:|---:|
| 모델 번호 | 1020 | 1020 |
| 프로토콜 | 2.0 | 2.0 |
| Operating_Mode | 1 | 1 |
| Drive_Mode | 0 | 0 |
| Torque_Enable | 0 | 0 |
| Homing_Offset | 0 | 0 |
| Present_Position | 3076 | 1 |
| 중립 기준 대비 편차 | -2 counts | +1 count, wrap 보정 |
| Present_Velocity | 0 | 0 |
| Hardware_Error_Status | 0 | 0 |
| 읽기 결과 | READS_COMPLETE | READS_COMPLETE |

## 판정 및 한계

검토된 LIVE 펌웨어의 중립 허용 범위는 Pan/Tilt 각각 ±20 counts이다.
이번 측정값은 해당 위치 조건을 만족하며, 두 축 모두 정지·토크 OFF·
하드웨어 오류 없음으로 확인되었다.

이는 측정 당시의 실제 중립 확인이다. 이후 자세 변경 가능성이 있으므로
LIVE 펌웨어의 CHECK를 다시 수행해야 한다.
검사 스케치가 읽지 않은 Firmware_Version, Status_Return_Level,
Bus_Watchdog 등의 LIVE 사전 조건은 이 결과만으로 통과했다고 판단하지 않는다.

실제 토크 유지 및 추종 시험은 아직 수행하지 않았다.

## 원시 증거

- [엔코더 측정 출력](evidence/neutral_inspect_20261008_121210/encoder_inspection.log)
- [소스 해시](evidence/neutral_inspect_20261008_121210/source_sha256.txt)
- [바이너리 해시](evidence/neutral_inspect_20261008_121210/binary_sha256.txt)
- [업로드 및 CRC 결과](evidence/neutral_inspect_20261008_121210/upload.log)

## 증거 파일 형식

Git에 포함한 encoder_inspection.log와 upload.log는 열람 및 diff 검사를 위해
CRLF 줄바꿈을 LF로 정규화했다. 측정값과 메시지 내용은 변경하지 않았다.
원본 로그는 results/logs/opencr/neutral_inspect_20261008_121210/에 보존했다.

Git에 포함한 upload.log는 각 줄 끝의 공백과 탭도 제거했다. 원본 로그는 수정하지 않았다.
