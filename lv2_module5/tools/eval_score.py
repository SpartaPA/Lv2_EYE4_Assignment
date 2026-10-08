"""평가 프레임 판정 집계 — eval_frames.py가 만든 CSV의 human_ok 칸을 사람이 채운 뒤 실행

  python3 tools/eval_score.py results/logs/perception/eval_visible_*.csv results/logs/perception/eval_empty_*.csv

human_ok: 1 = 노드 출력이 맞음, 0 = 틀림 (비어 있으면 미판정으로 따로 셈)
  visible(목표가 보이는 장면): 검출률 = 올바른 검출 프레임 / 판정한 프레임 × 100
                              틀린 프레임은 node_detected로 미검출(0)과 다른 물체 검출(1)을 구분
  empty(목표가 없는 장면)    : 배경 오검출 = 틀린 프레임 수 (검출률과 별도로 기록)
참고로 노드가 스스로 검출로 표시한 비율(node_detected)도 함께 출력 — 발제문: 정답 대조 검출률과 다름
"""
import csv
import sys

MIN_FRAMES = {"visible": 30, "empty": 10}  # 발제문 최소 평가 프레임 수


def score(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"{path}: 빈 파일")
        return
    scene = rows[0]["scene"]
    judged = [r for r in rows if r["human_ok"].strip() in ("0", "1")]
    unjudged = len(rows) - len(judged)
    wrong = [r for r in judged if r["human_ok"].strip() == "0"]
    node_det = sum(int(r["node_detected"]) for r in rows)

    print(f"\n== {path}")
    print(f"  장면 {scene}, 프레임 {len(rows)}장 (판정 {len(judged)}, 미판정 {unjudged})")
    if len(rows) < MIN_FRAMES.get(scene, 0):
        print(f"  ! 발제문 최소 {MIN_FRAMES[scene]}프레임보다 적음")
    if scene == "visible":
        ok = len(judged) - len(wrong)
        rate = ok / len(judged) * 100 if judged else 0.0
        miss = [r["idx"] for r in wrong if r["node_detected"] == "0"]
        other = [r["idx"] for r in wrong if r["node_detected"] == "1"]
        print(f"  검출률 = {ok} / {len(judged)} × 100 = {rate:.1f} %")
        print(f"  틀린 프레임: 미검출 {miss or '없음'}, 다른 물체 검출 {other or '없음'}")
    else:
        print(f"  배경 오검출 = {len(wrong)}프레임 / {len(judged)}  (틀린 프레임 번호: {[r['idx'] for r in wrong] or '없음'})")
    print(f"  (참고) 노드가 검출로 표시한 프레임 {node_det}/{len(rows)} — 사람 대조 결과와 다를 수 있음")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in sys.argv[1:]:
        score(p)
