"""End-to-end smoke test against a running ProofPack backend.

Usage: python scripts/smoke_test.py [base_url]
"""

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

SAMPLE_POLICY = """HOMEOWNERS INSURANCE POLICY - SUMMARY OF COVERAGE
Policy Number: HO-2024-55817
Named Insured: Maria Delgado
Property Address: 482 Riverside Drive, Cedar Falls, IA 50613

COVERAGE A - DWELLING: $320,000
COVERAGE C - PERSONAL PROPERTY: $160,000

FLOOD DAMAGE: This policy COVERS direct physical loss caused by flooding when a
federal disaster has been declared for the property location. The flood deductible
is $2,500 per occurrence. Claims must be filed within 60 days of the loss date.

EXCLUSIONS: Damage from gradual seepage, mold not resulting from a covered peril,
and earth movement are excluded.
"""


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read())


def upload(claim_id, filename, content, source_type):
    boundary = "----proofpackboundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="source_type"\r\n\r\n{source_type}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: text/plain\r\n\r\n{content}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        f"{BASE}/claims/{claim_id}/documents",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main():
    print("health:", get("/health"))
    print("providers:", get("/providers"))

    claim = post(
        "/claims",
        {
            "title": "Cedar Falls flood — Delgado",
            "claimant_name": "Maria Delgado",
            "incident_type": "flood",
            "incident_date": "2024-06-12",
            "location": "482 Riverside Drive, Cedar Falls, IA",
        },
    )
    print("created claim:", claim["id"])

    up = upload(claim["id"], "policy.txt", SAMPLE_POLICY, "policy")
    print("uploaded:", up["document"]["filename"], "chunks:", up["chunks_created"])

    qa = post(
        f"/claims/{claim['id']}/qa",
        {"question": "Does this policy cover flood damage and what is the deductible?"},
    )
    print("\n--- ANSWER (", qa["provider"], qa["latency_ms"], "ms ) ---")
    print(qa["answer"])
    print("\ncitations:", len(qa["citations"]))
    for c in qa["citations"]:
        print(f"  [{c['index']}] {c['filename']} score={c['score']} :: {c['snippet'][:80]}")

    assert qa["citations"], "expected at least one citation"
    print("\nSMOKE_TEST_PASSED")


if __name__ == "__main__":
    main()
