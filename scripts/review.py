"""Human-operated review client. No automatic approval, no vendor SDK required."""

import argparse
import json
import os
import webbrowser

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--agent", default="demo")
    parser.add_argument("--text", default="rectangle 5000 x 4000 mm")
    parser.add_argument("--target", default="simulation:room")
    args = parser.parse_args()
    token = os.environ.get("AI_AUTOCAD_OPERATOR_TOKEN")
    if not token:
        raise SystemExit("Set AI_AUTOCAD_OPERATOR_TOKEN in this operator terminal first")
    with httpx.Client(base_url=args.url, timeout=90, trust_env=False) as client:
        response = client.post(
            "/requests",
            json={
                "agent_id": args.agent,
                "target_document": args.target,
                "input": {"text": args.text},
            },
        )
        response.raise_for_status()
        job = response.json()
        print(json.dumps(job, indent=2, ensure_ascii=False))
        if job["proposal"]["unresolved_questions"]:
            raise SystemExit("Missing information: proposal remains draft")
        webbrowser.open(f"{args.url}/requests/{job['id']}/preview.svg")
        phrase = f"APPROVE {job['revision']}"
        if (
            input(f"Review ALL dimensions and assumptions above. Type '{phrase}' to proceed: ")
            != phrase
        ):
            raise SystemExit("Not approved. No execution.")
        payload = {"revision": job["revision"], "digest": job["digest"]}
        headers = {"X-Operator-Token": token}
        response = client.post(
            f"/requests/{job['id']}/approve",
            headers=headers,
            json={
                **payload,
                "accepted_review_items": job["review_items"],
            },
        )
        response.raise_for_status()
        response = client.post(f"/requests/{job['id']}/execute", headers=headers, json=payload)
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
