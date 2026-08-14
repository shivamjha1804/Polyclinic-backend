import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.agents.scribe_graph import extract_entities, draft_soap

from metrics import(
    diagnosis_recall_precision,
    medication_f1,
    dosage_exact_match,
    section_completeness,
    check_hallucinations
)

CASES_DIR = Path(__file__).parent / "cases"

def run_case(case_dir: Path) -> dict:
    transcript = (case_dir / "transcript.txt").read_text()
    expected_note = json.loads((case_dir / "expected_note.json").read_text())

    state = {"transcript" : transcript}
    state.update(extract_entities(state))
    state.update(draft_soap(state))
    predicted_note = state["soap_draft"]

    recall, precision = diagnosis_recall_precision(predicted_note["diagnosis"], expected_note["diagnosis"])
    med_f1 = medication_f1(predicted_note["medications"], expected_note["medications"])
    dosage_match = dosage_exact_match(predicted_note["medications"], expected_note["medications"])
    completeness = section_completeness(predicted_note)
    hallucination = check_hallucinations(transcript, predicted_note)

    return {
        "case": case_dir.name,
        "diagnosis_recall": recall,
        "diagnosis_precision": precision,
        "medication_f1": med_f1,
        "dosage_exact_match": dosage_match,
        "section_completeness": completeness,
        "hallucination_count": hallucination["hallucination_count"],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    case_dirs = sorted(d for d in CASES_DIR.iterdir() if d.is_dir())
    results = [run_case(d) for d in case_dirs]

    avg = lambda key: sum(r[key] for r in results) / len(results)
    total_hallucinations = sum(r["hallucination_count"] for r in results)

    print(f"{'case':<10}{'d.recall':<10}{'d.prec':<10}{'med_f1':<10}{'dosage':<10}{'complete':<10}{'halluc':<8}")

    for r in results:
        print(f"{r['case']:<10}{r['diagnosis_recall']:<10.2f}{r['diagnosis_precision']:<10.2f}"
              f"{r['medication_f1']:<10.2f}{r['dosage_exact_match']:<10.2f}"
              f"{r['section_completeness']:<10.2f}{r['hallucination_count']:<8}")

    overall_score = (avg("diagnosis_recall") + avg("diagnosis_precision") + avg("medication_f1") + avg("section_completeness")) / 4
    print(f"\nAVERAGE  recall={avg('diagnosis_recall'):.2f} precision={avg('diagnosis_precision'):.2f} "
          f"med_f1={avg('medication_f1'):.2f} completeness={avg('section_completeness'):.2f} "
          f"total_hallucinations={total_hallucinations}")
    print(f"Overall score: {overall_score:.2f} (threshold: {args.threshold})")

    if overall_score < args.threshold:
        print("FAILED: below threshold")
        sys.exit(1)
    print("PASSED")


if __name__ == "__main__":
    main()
