import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.retrieval import hybrid_search, vector_only_search, lexical_only_search

PATIENT_ID = "f46656e2-3223-4964-815d-d679ef4c11bd"

CASES_FILE = Path(__file__).parent / "retrieval_cases.json"

# Voyage AI's free tier (no payment method on file) allows only 3 requests
# per minute. vector-only and hybrid both call embed_query per question, so
# we space those calls out to stay under that limit.
EMBED_CALL_DELAY_SECONDS = 21

def recall_and_mrr(results: list[dict], expected_section: str) -> tuple[int, float]:
    sections = [r["section"] for r in results]
    if expected_section in sections:
        rank = sections.index(expected_section) + 1
        return 1, 1.0/rank
    return 0, 0.0

def evaluate(search_fn, cases, needs_delay: bool):
    recalls = []
    mrrs = []
    for case in cases:
        if needs_delay:
            time.sleep(EMBED_CALL_DELAY_SECONDS)
        results = search_fn(case["question"], PATIENT_ID, match_count = 8)
        recall, mrr = recall_and_mrr(results, case["expected_section"])
        recalls.append(recall)
        mrrs.append(mrr)
    return sum(recalls) / len(recalls), sum(mrrs) / len(mrrs)

def main():
    cases = json.loads(CASES_FILE.read_text())

    print(f"{'mode':<15}{'recall@8':<12}{'MRR':<8}")
    modes = [
        ("vector-only", vector_only_search, True),
        ("lexical-only", lexical_only_search, False),
        ("hybrid", hybrid_search, True),
    ]
    for name, fn, needs_delay in modes:
        recall, mrr = evaluate(fn, cases, needs_delay)
        print(f"{name:<15}{recall:<12.2f}{mrr:<8.2f}")

if __name__ == "__main__":
    main()
