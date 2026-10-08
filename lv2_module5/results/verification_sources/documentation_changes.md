# 검증 담당 문서 변경 안내

대상 저장소의 lv2_module5 폴더와 같은 구조다. 먼저 기존 문서 변경사항을 확인한 뒤 아래 문서만 적용한다. 코드·펌웨어·설정·launch와 팀원 작업 파일은 포함하지 않는다.

| 파일 | 반영 내용 |
|---|---|
| report.md | 문제1~5 결과·이미지·팀원 보고·미완료 회고 통합 |
| docs/requirements_traceability.md | 필수 기준별 증거·미완료 판정 |
| results/metrics.csv | 기존 인지 수치 유지, 노트북/이전 버전 제한 명시 |
| results/logs/verification/verification_results.csv | 시험별 증거 상태·부족 자료·회고 |
| results/logs/verification/README.md | CSV 의미와 정지 증거 한계 |
| recordings/README.md | 영상 링크·bag/재현 미확인 상태 |
| results/verification_sources/ | 제공 회고·스크립트·PR 보고 요약·수정 전 report 보존 |

results/images 및 logs/perception·control·opencr는 기존 ZIP 원본 증거다. 같은 파일이 이미 있으면 중복 적용하지 않아도 된다. recovery_trials.csv와 interruption_trials.csv는 이번 원본이 비어 있어 그대로 보존했다. 대상 저장소에 새 실측행이 있다면 헤더만 있는 이 파일로 덮어쓰지 않는다. 기존 README·team.md·presentation.md는 다른 담당자 변경을 덮어쓰지 않도록 이 패키지에서 수정하지 않았다.

최신 control_progress_20261008.md·archive·최신 설정·PR URL은 미제공이며 이번 문서가 이를 생성한 것처럼 쓰지 않는다. 영상은 링크만 제공돼 미열람 상태다.
