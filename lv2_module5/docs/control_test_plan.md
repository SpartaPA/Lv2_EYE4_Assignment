# 제어 테스트 계획 및 결과

## 1. 목적 및 범위

OpenCR의 USB 시리얼 명령 파서와 명령 수신 타임아웃 감시 기능(워치독)을 검증한다.

현재 펌웨어는 **모터 출력을 비활성화한 파서 테스트용**이다. 명령에 따라 내부 요청 속도와 활성화 상태만 변경하며, DYNAMIXEL에는 제어 명령을 전송하지 않는다.

- 테스트 날짜: 2026-10-05
- 담당자: 조민혁 — Control
- 기본 파서 테스트: 통과
- 확장 테스트 5개: 모두 통과
- 실제 모터 동작 및 정지 검증: 미실시

## 2. 테스트 환경

| 항목 | 설정 |
|---|---|
| 호스트 | Raspberry Pi, Ubuntu 26.04.1 LTS, ARM64 |
| 제어 보드 | OpenCR R1.0 |
| Arduino CLI | 1.5.1 |
| ARM GCC | 14.2.1 |
| 업로더 | opencr_ld 1.0.4 |
| 통신 | USB 시리얼, 115200 baud, 8N1 |
| 명령 워치독 설정 | 300 ms |
| 파서 테스트 속도 범위 | ±0.10 rad/s |
| 모터 전원 | 테스트 중 비활성화 |

±0.10 rad/s는 파서의 입력 범위 검증을 위한 값이며, 실제 모터 운전 한계로 승인된 값은 아니다.

## 3. 빌드 및 업로드 결과

| 항목 | 결과 |
|---|---|
| 펌웨어 컴파일 | 성공 |
| 프로그램 저장 공간 | 76,772 bytes, 최대 공간의 9% |
| 전역 변수 메모리 | 40,148 bytes |
| 업로드 CRC 검증 | `CRC OK` |
| 펌웨어 다운로드 | `[OK] Download` |
| 업로드 후 명령 응답 | 정상 |

## 4. 기본 파서 테스트 결과

실행 스크립트: `tests/test_parser.py`

| 검증 항목 | 관찰 결과 | 판정 |
|---|---|---|
| 비활성화 상태에서 속도 명령 거부 | `ERR DISARMED` | 통과 |
| `ARM` 수신 후 활성화 | `ACK ARM` | 통과 |
| 유효한 속도 명령을 반복 수신 | `ACK VEL`, `STATE ARMED NONZERO` | 통과 |
| 명령 수신 중단 시 타임아웃 | `EVENT TIMEOUT DISARMED` | 통과 |
| 타임아웃 후 속도 명령으로 자동 재활성화되지 않음 | `ERR DISARMED` | 통과 |
| NaN 및 잘못된 숫자 거부 | `ERR VALUE` | 통과 |
| 허용 범위를 초과하는 속도 거부 | `ERR RANGE` | 통과 |
| 알 수 없는 명령 거부 | `ERR COMMAND` | 통과 |
| 음수 속도 명령 수락 | `ACK VEL` | 통과 |
| `STOP` 수신 시 속도만 0으로 변경 | `STATE ARMED ZERO` | 통과 |
| `DISARM` 수신 시 속도 0 및 비활성화 | `STATE DISARMED ZERO` | 통과 |

## 5. 확장 테스트 결과

실행 스크립트: `tests/test_parser_extended.py`

| 검증 항목 | 시험 방법 | 관찰 결과 | 판정 |
|---|---|---|---|
| 재시작 후 초기 상태 | 수동 재시작 후 `ARM`이나 `DISARM` 없이 상태 조회 및 속도 명령 전송 | `STATE DISARMED ZERO`, `ERR DISARMED` | 통과 |
| 잘못된 명령이 워치독을 갱신하지 않음 | 활성화 후 `VEL nan`을 약 50 ms 간격으로 0.7초 동안 전송 | 반복 수신 중 타임아웃 및 비활성화 | 통과 |
| 상태 조회가 워치독을 갱신하지 않음 | 활성화 후 `STATUS`를 약 50 ms 간격으로 0.7초 동안 전송 | 반복 조회 중 타임아웃 및 비활성화 | 통과 |
| 미완성 명령이 워치독을 차단하지 않음 | 개행 없는 `VEL 0.02`를 전송하고 0.7초 대기 | 타임아웃 발생, 이후 개행을 보내도 `ERR DISARMED` | 통과 |
| 과도하게 긴 입력 처리 및 복구 | 개행 없는 100자 입력 후 0.7초 대기, 이후 개행과 `STATUS` 전송 | 타임아웃, `ERR LINE`, 정상 상태 응답 | 통과 |

스크립트의 최종 결과는 `ALL FIVE EXTENDED CHECKS PASSED`이며, 종료 시 `ACK DISARM`을 수신했다.

## 6. 검증 범위와 한계

현재 결과는 펌웨어 루프가 실행되는 동안 명령 파서와 소프트웨어 워치독이 의도한 상태 전이를 수행함을 확인한 것이다.

다음 항목은 아직 검증하지 않았다.

- 설정값 300 ms에 대한 실제 타임아웃 발생 시간과 편차
- USB 송신 버퍼 포화 또는 호스트 수신 중단 시 워치독 동작
- 펌웨어 루프 정지에 대한 대응
- DYNAMIXEL 통신, 운전 모드, 회전 방향 및 위치 피드백
- 실제 모터의 속도 제한, 각도 제한 및 정지 성능

`ACK`는 명령의 소프트웨어 수락을 의미하며, 실제 모터 동작이나 정지를 보장하지 않는다.

## 7. 증빙 파일

아래 경로는 `lv2_module5/` 기준이다. Raspberry Pi에서 생성된 파일을 이 경로에 복사하여 보관한다.

| 파일 | 내용 |
|---|---|
| `firmware/tracking_controller/tracking_controller.ino` | 테스트 대상 펌웨어 |
| `tests/test_parser.py` | 기본 테스트 스크립트 |
| `tests/test_parser_extended.py` | 확장 테스트 스크립트 |
| `evidence/parser/parser_test.log` | 기본 테스트 결과 |
| `evidence/parser/parser_extended_test.log` | 확장 테스트 결과 |
| `evidence/parser/tracking_controller_build.log` | 컴파일 결과 |
| `evidence/parser/tracking_controller_upload.log` | 업로드 및 CRC 검증 결과 |
| `evidence/parser/opencr_source_commit.txt` | 사용한 OpenCR 소스 커밋 |

## 8. 후속 테스트 계획

1. 연결할 DYNAMIXEL의 모델, ID, baud rate 및 프로토콜을 확인한다.
2. 토크 비활성화 상태에서 통신 및 위치 피드백을 확인한다.
3. 운전 모드, 회전 방향, 기준 위치, 허용 각도 및 속도 한계를 확정한다.
4. 제한된 움직임으로 모터 제어와 정지 명령을 검증한다.
5. 대상 상실, 대상 메시지 발행 중단, 호스트 제어 프로그램 종료 시 실제 정지를 검증한다.
6. 타임아웃과 물리적 정지까지 걸리는 시간을 측정하여 기록한다.
