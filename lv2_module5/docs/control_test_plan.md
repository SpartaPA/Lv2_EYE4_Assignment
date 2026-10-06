# 제어 테스트 계획 및 결과

## 1. 목적

Pan/Tilt 2축 추적 시스템의 제어 명령, 상태 전이, 제한 조건, 통신 중단 정지 및 복구 동작을 검증한다.

현재 완료한 시험은 실제 OpenCR에서 수행한 **모터 출력 없는 단일 속도 명령 파서 및 소프트웨어 워치독 시험**이다. 실제 모터 제어와 2축 추적 시험은 아직 수행하지 않았다.

## 2. 현재 검증 상태

| 항목 | 상태 |
|---|---|
| Raspberry Pi에서 OpenCR 펌웨어 빌드 | 완료 |
| USB 업로드 및 CRC 검증 | 완료 |
| 단일 속도 명령 파서 기본 시험 | 통과 |
| 확장 시험 5개 | 모두 통과 |
| Pan/Tilt 2축 시리얼 명령 | 미구현 |
| DYNAMIXEL 식별 및 위치 피드백 | 미검증 |
| 실제 모터 정지 및 제한 조건 | 미검증 |
| ROS 2 모의 입력 7개 | 미검증 |
| PC–Pi DDS 연결 | 미검증 |
| 실제 2축 추적 및 성능 측정 | 미검증 |

기존 로그는 단일 속도 파서 기준의 원본 증거로 보존한다. 이를 2축 펌웨어의 통과 기록으로 사용하지 않는다.

## 3. 기존 파서 시험 환경

- 시험일: 2026-10-05
- 담당: 조민혁 — 제어
- 호스트: Raspberry Pi, Ubuntu 26.04.1 LTS, ARM64
- 제어 보드: OpenCR R1.0
- Arduino CLI: 1.5.1
- ARM GCC: 14.2.1
- 업로더: opencr_ld 1.0.4
- USB 시리얼 설정: 115200 baud, 8N1
- 보드 명령 타임아웃 설정: 300 ms
- 파서 입력 범위: ±0.10 rad/s
- 모터 출력: 비활성화

±0.10 rad/s는 입력 검증용 소프트웨어 한계이며, 실제 장착 상태에서 검증된 모터 속도 한계가 아니다.

## 4. 빌드 및 업로드 결과

| 항목 | 결과 |
|---|---|
| 컴파일 | 성공 |
| 프로그램 저장 공간 | 76,772 bytes, 최대 공간의 9% |
| 전역 변수 메모리 | 40,148 bytes |
| CRC 검증 | `CRC OK` |
| 다운로드 | `[OK] Download` |
| 업로드 후 명령 응답 | 정상 |

메모리 사용량과 결과는 시험 당시 펌웨어에 해당한다.

## 5. 기본 파서 시험

시험 스크립트: [test_parser.py](../firmware/opencr/tests/test_parser.py)

| 항목 | 관찰 결과 | 판정 |
|---|---|---|
| 비활성화 상태에서 속도 명령 거부 | `ERR DISARMED` | 통과 |
| 명시적 활성화 | `ACK ARM` | 통과 |
| 유효한 속도 명령 반복 수신 | `ACK VEL`, `STATE ARMED NONZERO` | 통과 |
| 명령 수신 중단 | `EVENT TIMEOUT DISARMED` | 통과 |
| 타임아웃 후 속도 명령 거부 | `ERR DISARMED` | 통과 |
| NaN 및 잘못된 숫자 거부 | `ERR VALUE` | 통과 |
| 범위 초과 값 거부 | `ERR RANGE` | 통과 |
| 알 수 없는 명령 거부 | `ERR COMMAND` | 통과 |
| 음수 속도 수락 | `ACK VEL` | 통과 |
| STOP으로 속도 초기화 | `STATE ARMED ZERO` | 통과 |
| DISARM으로 속도 초기화 및 비활성화 | `STATE DISARMED ZERO` | 통과 |

## 6. 확장 파서 시험

시험 스크립트: [test_parser_extended.py](../firmware/opencr/tests/test_parser_extended.py)

| 항목 | 방법 | 결과 |
|---|---|---|
| 재시작 후 비활성화 | 초기 상태 조회 및 속도 명령 전송 | 통과 |
| 잘못된 명령의 연속 수신 | `VEL nan`을 약 50 ms 간격으로 0.7초 전송 | 수신 중 타임아웃 발생 |
| STATUS 연속 수신 | 약 50 ms 간격으로 0.7초 전송 | 조회 중 타임아웃 발생 |
| 개행 없는 미완성 명령 | `VEL 0.02` 전송 후 0.7초 대기 | 타임아웃 발생, 이후 명령 완성 시 거부 |
| 과도하게 긴 입력 및 복구 | 개행 없는 100자 전송 후 개행과 STATUS 전송 | 타임아웃, `ERR LINE`, 정상 상태 응답 |

최종 출력: `ALL FIVE EXTENDED CHECKS PASSED`

종료 시 `ACK DISARM`을 수신했다.

## 7. 검증 한계

현재 결과는 펌웨어 루프가 실행되는 동안 내부 요청 속도와 활성화 상태가 의도대로 변경됨을 확인한다.

아직 확인하지 않은 항목:

- 설정값 300 ms에 대한 실제 타임아웃 발생 시간과 편차
- USB 송신 버퍼 포화 또는 호스트 수신 중단 시 동작
- 펌웨어 루프 정지에 대한 대응
- 실제 모터의 움직임, 정지 시간 및 정지 후 자세 유지
- Pan/Tilt 동시 명령과 축별 제한
- 실제 모터 피드백 및 통신 오류 처리

ACK는 소프트웨어의 명령 수락을 의미한다. 실제 모터 동작이나 정지를 증명하지 않는다.

## 8. 증빙 파일

아래 링크는 이 문서의 위치를 기준으로 한다.

| 내용 | 파일 |
|---|---|
| 펌웨어 | [tracking_controller.ino](../firmware/opencr/tracking_controller/tracking_controller.ino) |
| 기본 시험 | [test_parser.py](../firmware/opencr/tests/test_parser.py) |
| 확장 시험 | [test_parser_extended.py](../firmware/opencr/tests/test_parser_extended.py) |
| 기본 결과 | [parser_test.log](../results/logs/opencr/parser_baseline/parser_test.log) |
| 확장 결과 | [parser_extended_test.log](../results/logs/opencr/parser_baseline/parser_extended_test.log) |
| 빌드 결과 | [tracking_controller_build.log](../results/logs/opencr/parser_baseline/tracking_controller_build.log) |
| 업로드 결과 | [tracking_controller_upload.log](../results/logs/opencr/parser_baseline/tracking_controller_upload.log) |
| OpenCR 소스 리비전 | [opencr_source_commit.txt](../firmware/opencr/opencr_source_commit.txt) |

기존 시험 코드와 증빙을 저장한 커밋은 `efce660`이다. 이후 디렉토리 변경 커밋과 2축 구현 커밋은 별도로 기록한다.

## 9. 후속 시험 계획

### 9.1 하드웨어 식별

1. 모터를 한 대씩 연결하여 모델, ID, baud rate, 프로토콜을 확인한다.
2. Pan/Tilt 축과 모터 ID의 대응 관계를 기록한다.
3. 두 모터를 함께 연결하기 전에 ID 중복 여부를 확인한다.
4. 위치 피드백, 운전 모드, 기준 위치를 확인한다.
5. 카메라 장착 상태에서 허용 각도, 속도 및 케이블 여유를 정한다.

### 9.2 2축 파서 및 보드 제어

- 하나의 명령에서 Pan/Tilt 값을 함께 검사하고 반영한다.
- 어느 한 값이라도 잘못되면 명령 전체를 거부한다.
- STOP, DISARM, 타임아웃이 두 축에 모두 적용되는지 확인한다.
- 비활성화 상태에서 두 축의 속도 명령을 거부한다.
- 물리 출력 없이 2축 파서 시험을 먼저 수행한다.
- 이후 제한된 움직임으로 각 축의 방향과 실제 정지를 검증한다.
- 위치 피드백 오류와 모터 통신 오류 시 정지 및 오류 보고를 확인한다.

### 9.3 ROS 2 모의 입력 7개

모터 출력을 비활성화하고 명령·상태·시간을 기록한다.

| 입력 | 기대 결과 |
|---|---|
| x=0, y=0, z>0 | 두 축 모두 속도 0 |
| x=+0.4, y=0, z>0 | Pan 양의 영상 오차를 줄이는 명령 |
| x=-0.4, y=0, z>0 | 반대 방향 Pan 명령 |
| x=0, y=+0.4, z>0 | Tilt 양의 영상 오차를 줄이는 명령 |
| x=0, y=-0.4, z>0 | 반대 방향 Tilt 명령 |
| z=0 | LOST 전이, 두 축 정지 |
| /target 발행 중단 | 기본 0.5초 타임아웃 후 LOST 전이 및 두 축 정지 |

검출 입력 시험은 신선한 메시지를 연속 발행하여 3프레임 복구 조건을 충족시킨다.

### 9.4 통합 및 필수 실험

| 시험 | 조건 |
|---|---|
| PC–Pi DDS | 실제 명령 토픽 전달 및 중단 처리 확인 |
| 정상 추적 | 동일 조건에서 30초 이상 |
| 가림 후 재등장 | 약 2초 가림, 현재 시야 안 재등장, 5회 |
| 인지 입력 중단 | /target