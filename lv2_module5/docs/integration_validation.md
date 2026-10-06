# 통합 후보 검증 기록

이 패키지는 입력 archive(control_integration_inputs.tar.gz)의 내용을 검토하여
작성한 후보이다. 실제 Pi/OpenCR에 접속하거나 펌웨어를 업로드하지 않았다.

## 수행한 검사

- g++ C++17, -Wall -Wextra -Werror: DRY 및 LIVE-stub 스케치 빌드/실행 통과.
- 실제 .ino를 include한 test_integrated_native.cpp 시나리오 통과:
  - 두 값 중 잘못된 값이 있으면 모터 쓰기/타이머 갱신 없음
  - silence, 오류/STATUS, 미완성/과대 입력에서도 timeout
  - ARM 중 반복 ARM이 타이머를 갱신하지 않음
  - STOP/DISARM, 지지 후 토크 해제
  - millis rollover
  - 두 번째 모터 쓰기 실패 후 두 모터 zero 시도, FAULT 고정
  - FAULT 후 자동 버스 읽기/쓰기 중단
  - 피드백 실패, 위치 경계 정지, encoder reset 검출
  - Tilt 시작 raw=0과 raw=4096 표현
  - DRY에서 버스 init/read/write 호출 수 0
- 실제 test_2axis_dry.py를 host PTY의 DRY .ino 실행기에 연결하여 통과:
  `ALL TWO-AXIS DRY CHECKS PASSED`.
- Python 두 스크립트 syntax compile 통과.

이 결과는 USB, ARM toolchain, 보드 scheduling, 실제 SDK 지연, 토크/전류,
중력 부하 및 정지 거리를 재현하지 않는다. LIVE-stub의 피드백은 가짜다.
하드웨어 승인이나 실제 두 축 통과 기록으로 사용하지 않는다.

## host 재현

```bash
cd lv2_module5/firmware/opencr/tests
g++ -std=c++17 -Wall -Wextra -Werror -I native_stubs \
  test_integrated_native.cpp -o /tmp/integration-dry
/tmp/integration-dry
g++ -std=c++17 -Wall -Wextra -Werror -DENABLE_MOTOR_OUTPUT=1 \
  -I native_stubs test_integrated_native.cpp -o /tmp/integration-live
/tmp/integration-live
```

실제 보드 및 live 절차는 integration_steps.md에 분리했다.
기존 single-axis commissioning 결과는 사용자가 제공한 로그/관찰을 근거로
정리했으며 이번 host 검사와 구분한다.

## 참고한 하드웨어 정의

ROBOTIS XM430-W350 e-Manual:
https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/

기존 OpenCR source commit:
68ec75d8a400949580ecf263e0105ea9743b878e

- Goal_Velocity: 0.229 rpm 단위
- Bus_Watchdog: 20 ms 단위, firmware v38부터, 모든 instruction packet 감시
- 위치 원시값은 재부팅 시 단일 회전 표현으로 재설정될 수 있음

현재 후보의 80/100 counts 및 ±0.05 rad/s는 프로젝트 bench 설정값이며
제조사가 보장한 기구 안전 한계가 아니다.
