"""Evaluate the running KnowFlow API against the fictional employee handbook."""

import argparse
from collections import Counter
from getpass import getpass
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
        path = response.request.url.path
        status = f"{path} returned HTTP {response.status_code}"
        return status if path == "/login" else f"{status}: {response.text}"
    return str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI URL")
    parser.add_argument("--email", required=True, help="Evaluation workspace account")
    parser.add_argument("--other-email", help="Account in a separate, empty workspace for the isolation check")
    args = parser.parse_args()
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    passed = Counter()
    completed = Counter()
    errors = 0

    with httpx.Client(base_url=args.base_url, timeout=120, trust_env=False) as client:
        try:
            member = post(client, "/login", json={"email": args.email, "password": getpass(f"Password for {args.email}: ")})
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

    isolation_failed = False
    if args.other_email:
        with httpx.Client(base_url=args.base_url, timeout=120, trust_env=False) as other:
            try:
                second = post(other, "/login", json={
                    "email": args.other_email,
                    "password": getpass(f"Password for {args.other_email}: "),
                })
                if member["workspace_id"] == second["workspace_id"]:
                    raise ValueError("Use an account in a different workspace for the isolation check.")
                query = {"question": cases[0]["question"], "workspace_id": member["workspace_id"]}
                passages = post(other, "/search", json=query)["passages"]
                result = post(other, "/ask", json=query)
                isolation_failed = bool(passages or result["citations"]) or normalize(result["answer"]) != normalize(ABSTENTION)
                print(f"{'FAIL' if isolation_failed else 'PASS'} workspace-isolation")
            except (httpx.HTTPError, ValueError, KeyError) as error:
                print(f"ERROR workspace-isolation — {describe_error(error)}")
                return 2

    print("\nSummary")
    for metric in ("retrieval@5", "answer", "citation", "abstention"):
        print(f"  {metric}: {passed[metric]}/{completed[metric]} completed checks")
    print(f"  API errors: {errors}/{len(cases)} cases")
    if errors:
        return 2
    return int(passed != completed or isolation_failed)


if __name__ == "__main__":
    raise SystemExit(main())
