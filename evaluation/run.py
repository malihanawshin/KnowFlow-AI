"""Evaluate the running KnowFlow API against the fictional employee handbook."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re

import httpx

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "employee-handbook.pdf"
CASES = Path(__file__).with_name("handbook_cases.json")
TOP_K = 5
ABSTENTION = "I found insufficient evidence in the uploaded documents."


def post(client, path, **kwargs):
    response = client.post(path, **kwargs)
    response.raise_for_status()
    return response.json()


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def matches_passage(passage, expected, document_id):
    return (
        passage["document_id"] == document_id
        and passage["page_number"] == expected["page"]
        and normalize(expected["passage"]) in normalize(passage["text"])
    )


def evaluate(client, case, document_id):
    query = {"question": case["question"], "limit": TOP_K}
    expected = case["expected"]
    checks = {}

    if expected is not None:
        passages = post(client, "/search", json=query)["passages"]
        checks["retrieval@5"] = any(
            matches_passage(passage, expected, document_id) for passage in passages
        )

    result = post(client, "/ask", json=query)
    answer = result["answer"]
    citations = result["citations"]

    if expected is None:
        checks["abstention"] = normalize(answer) == normalize(ABSTENTION) and not citations
    else:
        checks["answer"] = bool(re.search(expected["answer_pattern"], normalize(answer)))
        checks["citation"] = any(
            matches_passage(citation, expected, document_id) for citation in citations
        )

    return checks, answer, citations


def describe_error(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        response = error.response
        return f"{response.request.url.path} returned HTTP {response.status_code}: {response.text}"
    return str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI URL")
    args = parser.parse_args()
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    passed = Counter()
    completed = Counter()
    errors = 0

    with httpx.Client(base_url=args.base_url, timeout=120, trust_env=False) as client:
        try:
            with FIXTURE.open("rb") as pdf:
                upload = post(client, "/documents", files={"file": (FIXTURE.name, pdf, "application/pdf")})
            document_id = upload["document_id"]
        except (OSError, httpx.HTTPError, ValueError, KeyError) as error:
            print(f"Could not prepare the handbook: {describe_error(error)}")
            return 2

        for case in cases:
            try:
                checks, answer, citations = evaluate(client, case, document_id)
            except (httpx.HTTPError, ValueError, KeyError) as error:
                errors += 1
                print(f"ERROR {case['id']} — {describe_error(error)}")
                continue

            completed.update(checks.keys())
            passed.update(metric for metric, success in checks.items() if success)
            print(f"{'PASS' if all(checks.values()) else 'FAIL'} {case['id']}")
            print("  " + ", ".join(f"{name}: {'pass' if success else 'fail'}" for name, success in checks.items()))
            if not all(checks.values()):
                print(f"  Answer: {answer}")
                print(f"  Cited pages: {[(item['title'], item['page_number']) for item in citations]}")

    print("\nSummary")
    for metric in ("retrieval@5", "answer", "citation", "abstention"):
        print(f"  {metric}: {passed[metric]}/{completed[metric]} completed checks")
    print(f"  API errors: {errors}/{len(cases)} cases")
    if errors:
        return 2
    return int(passed != completed)


if __name__ == "__main__":
    raise SystemExit(main())
