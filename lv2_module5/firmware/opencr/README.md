# OpenCR 펌웨어

## 기준 버전과 통합 후보

기존 tracking_controller는 단일 축 파서 기준 버전이다. 수정하지 않았다.
pan_commission, tilt_hold_test, tilt_commission은 각 축에서 시험한 기록이다.
새 tracking_controller_2axis는 두 축 통합 **후보**이며 기본 빌드는 MODE=DRY다.
MODE=DRY에서 모터 버스 호출은 없고 피드백은 모의 값이다.
기존 test_parser*.py는 새 두 축 프로토콜에 사용하지 않는다.

## 문서

- [제어 인터페이스](../../docs/control_interface.md)
- [시험 계획](../../docs/control_test_plan.md)
- [설치·실행 절차](../../docs/integration_steps.md)
- [후보 검증 범위](../../docs/integration_validation.md)
- [하드웨어 기록](../../docs/hardware.md)

## 파일

| 경로 | 역할 |
|---|---|
| tracking_controller_2axis/ | 새 두 축 후보 |
| tests/test_2axis_dry.py | 실제 보드 MODE=DRY 전용 시리얼 시험 |
| tests/bench_2axis_once.py | 명시적 LIVE 한 번 명령, 300 ms timeout 관찰 |
| tests/test_integrated_native.cpp | 실제 스케치 logic의 host-side 회귀 검사 |
| tests/native_stubs/ | host-side 검사 전용 가짜 Arduino/Workbench |
| tests/native_pty.cpp | DRY 시리얼 시험을 위한 host-side PTY 실행기 |
| patches/ | 기존 GCC/Arduino min/max 호환성 패치 |

native_stubs는 Arduino 라이브러리로 설치하지 않는다.
Arduino는 tracking_controller_2axis 디렉터리만 빌드한다.

## 운용 주의점

CHECK/HOLD는 명시적으로 수행하며, HOLD는 두 축 토크를 활성화한다.
ARM은 HOLD 완료 이후에만 가능하다. ARM 다음에는 300 ms 안에 VEL이 필요하므로
LIVE VEL 시험은 수동 타이핑 대신 제공된 짧은 실행기를 사용한다.
STOP/DISARM/명령 timeout은 토크를 유지한다.
카메라를 지지한 뒤 SUPPORTED_OFF를 사용한다. 포트 닫기는 토크 해제가 아니다.
FAULT 후 토크/정지를 가정하지 말고 지지 후 해제 또는 전원을 차단한다.
