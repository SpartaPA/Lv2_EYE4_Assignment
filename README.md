# Lv2_EYE4_Assignment
Lv2_E팀_아이뻐_과제용 repository (제출 명칭: Lv2_EYE4_과제)

RealSense D435 영상으로 단일 색상 목표를 검출하고, OpenCR과 DYNAMIXEL 2개로 **Pan/Tilt 2축 추적**과 안전 정지를 구현하는 프로젝트입니다.
모든 ROS 2 노드는 Raspberry Pi에서 실행하고, PC는 SSH 터미널로 사용합니다.

- 팀명: **EYE4 (아이뻐)**
- 팀장: **전승혜 / SeungHye-J**
- 프로젝트 폴더: [lv2_module5/](lv2_module5/) — 실행·재현 안내 [lv2_module5/README.md](lv2_module5/README.md)
- 보고서 [report.md](lv2_module5/report.md) · 팀 기록 [team.md](lv2_module5/team.md) · 발표 [presentation.md](lv2_module5/presentation.md)

| 이름 | GitHub ID | 역할 |
| --- | --- | --- |
| 전승혜 | SeungHye-J | 팀장 + 검증·문서화 |
| 김상화 | SangHwaKim09 | 인지 |
| 한상준 | WindForce08 | 통합 |
| 조민혁 | eiioitsMin | 제어 |

```text
SpartaPA/Lv2_EYE4_Assignment/
├── README.md
└── lv2_module5/
    ├── README.md
    ├── report.md
    ├── team.md
    ├── presentation.md
    ├── ros2_ws/src/
    ├── firmware/
    ├── config/
    ├── tools/
    ├── docs/
    ├── results/
    │   ├── images/
    │   ├── logs/
    │   ├── plots/
    │   └── metrics.csv
    └── recordings/README.md
```

## 제출 전 체크리스트

실제로 확인한 항목만 체크합니다 (2026-10-07 기준).

- [x] 팀 저장소에 팀명·팀장·팀원 3명의 이름과 계정이 있습니다.
- [ ] main 보호 설정 또는 적용 불가 사유·운영 규칙을 기록했습니다.
- [ ] 4인 모두 본인 PR 병합 1건 이상과 다른 PR 리뷰 1건 이상을 남겼습니다.
- [ ] 팀장 본인의 PR도 다른 팀원이 승인했습니다.
- [ ] 목표 존재·부재·가림 장면과 실제 추적을 확인했습니다. (세 장면 검출은 완료, 실제 추적은 미완료)
- [ ] 인지 입력 중단과 제어 통신 중단 모두 정지합니다. (DRY·펌웨어 단독 기록만 있음)
- [ ] Kp 두 설정을 동일 조건에서 반복했습니다.
- [ ] 소실·복귀 5회의 성공·실패를 모두 남겼습니다.
- [ ] 지표 정의와 원본 로그·평가 프레임이 일치합니다.
- [ ] 실제 모터 출력 없이 bag을 재현했습니다.
- [ ] 다른 팀원이 README로 실행한 기록이 있습니다.
- [ ] 팀 보고서와 4인 기여, 자료 접근 권한을 확인했습니다.
- [ ] 팀장이 최종 main에 제출 태그를 만들고 팀 대표로 제출합니다.
