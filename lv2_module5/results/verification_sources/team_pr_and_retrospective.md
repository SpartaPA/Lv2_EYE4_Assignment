# 2026-10-08 팀원 제출 내용 정리

출처: 전승혜가 대화에 제공한 제어·통합 PR 설명 및 통합 회고. 원본 PR URL·전체 diff·최신 archive는 제공되지 않았다. 아래는 제출 설명의 요약이며 독립적인 실측 판정이 아니다.

## 조민혁 — 제어 PR 보고

- ex/ey 축별 P 제어, Kp·방향·속도 제한·deadband, 입력 timeout 0.5초, 신선 3프레임 후 복귀 구현.
- ARM/DISARM/STOP, DRY/LIVE 확인, 시리얼 응답·timeout·bridge 상태 보고 구현.
- 모터 탐색·commissioning·Tilt 유지·중립/범위 확인 수행 보고.
- 단위·모의·PTY·USB DRY·카메라 LIVE 시험 수행 보고.
- ROS_COMMAND_TIMEOUT 구간에서 시리얼 처리·상태 발행·로그 지연을 조사하고 비동기 CSV 기록, 상태 발행 주기와 명령 신선도 설정 변경을 적용했다고 보고.
- Pan Kp 0.05/0.10 비교, Tilt Kp 0.10 유지. 운전자 관찰을 근거로 후속 시험용 Pan/Tilt 0.10/0.10 선정.
- 최근 두 시험 로그, DISARM 응답·정지 상태 보고 시간, 소실/복귀 구간, archive·SHA-256·영상 링크를 control_progress_20261008.md에 기록했다고 보고.
- 해당 진행 문서와 최근 원본 로그·archive는 이번 자료에 포함되지 않아 시간·반복 수·지표를 확인하지 못했다.

## 한상준 — 통합 PR 보고

- Module 5 구조 정리, Pan/Tilt 및 OpenCR LIVE bridge, LIVE tracking 안정화와 복구 로직 개선.
- runtime origin calibration, tracking limit 및 reversible limit stop 관련 변경.
- 검증 로그·replay 분석 기능, 실행 문서, 설정 불일치·중복 상수 정리.
- OpenCR 통신, LIVE tracking, Pan/Tilt, recovery, runtime origin 및 limit 검증 수행 보고.
- dev/sangjun → main PR이라는 설명만 있으며, 실제 merge 결과·PR URL·시험 commit은 미제공.

## 통합 회고의 해석

회고에는 RealSense D435, ROS 2 Lyrical, Raspberry Pi 4, Color/Depth/Debug Image 확인 및 HSV·Contour→/target→Control→OpenCR 구조가 기재되어 있다. 일부 설명은 수평 1축 및 앞으로 구현할 기능을 혼합한다. 최종 검증 문서는 팀의 2축 조건을 유지하고 이 글을 성능 실측 증거로 쓰지 않는다. Depth gate가 최종 실행에서 켜졌는지는 최신 설정·시작 로그 없이는 판단하지 않는다.

## 시연 영상

[팀 공유 드라이브](https://drive.google.com/drive/folders/1tOibtMF1Q7g7146O-sqSVVbWGnd0sBoK?usp=sharing)

공유자 설명: 과제 발제문 조건에 부합하는 영상이 필요하면 재촬영해야 할 수 있음. 이번 작성에서 폴더 내용을 열지 못했다. 파일명·기간·장면·촬영 환경·조건 충족 여부는 판정하지 않았다.
