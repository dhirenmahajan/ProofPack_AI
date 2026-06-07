"""ProofPack AI evaluation harness (Month 3).

HTTP-driven (like scripts/smoke_test.py): it exercises a *running* backend so it
validates the real ingestion -> retrieval -> cited-QA -> packet path end to end,
in CI, with zero API keys (deterministic stub providers).
"""
