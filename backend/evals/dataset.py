"""Seeded evaluation dataset: synthetic documents + gold-labeled questions.

Kept small and deterministic so it runs in CI on stub providers. Each question
carries gold source files (for retrieval/citation metrics) and gold keywords
(for grounding/faithfulness). Extend SUBSET for `--full` runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalQuestion:
    question: str
    expect_files: list[str] = field(default_factory=list)
    expect_keywords: list[str] = field(default_factory=list)


@dataclass
class EvalDoc:
    filename: str
    source_type: str
    content: str


@dataclass
class EvalCase:
    name: str
    claim: dict
    documents: list[EvalDoc]
    questions: list[EvalQuestion]


_FLOOD_POLICY = """HOMEOWNERS INSURANCE POLICY - SUMMARY OF COVERAGE
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

_CONTRACTOR_INVOICE = """RIVERSIDE RESTORATION LLC - INVOICE
Invoice #: RR-4471
Date: 2024-06-20
Bill To: Maria Delgado, 482 Riverside Drive, Cedar Falls, IA

Water extraction and drying .............. $3,200.00
Drywall removal and replacement .......... $5,450.00
Flooring replacement ..................... $7,800.00

TOTAL DUE: $16,450.00
"""


SUBSET: list[EvalCase] = [
    EvalCase(
        name="cedar-falls-flood",
        claim={
            "title": "Cedar Falls flood — Delgado",
            "claimant_name": "Maria Delgado",
            "incident_type": "flood",
            "incident_date": "2024-06-12",
            "location": "482 Riverside Drive, Cedar Falls, IA",
        },
        documents=[
            EvalDoc("policy.txt", "policy", _FLOOD_POLICY),
            EvalDoc("invoice.txt", "invoice", _CONTRACTOR_INVOICE),
        ],
        questions=[
            EvalQuestion(
                "Does this policy cover flood damage and what is the deductible?",
                expect_files=["policy.txt"],
                expect_keywords=["flood", "2,500"],
            ),
            EvalQuestion(
                "How many days do I have to file the claim?",
                expect_files=["policy.txt"],
                expect_keywords=["60"],
            ),
            EvalQuestion(
                "What is the total of the contractor invoice?",
                expect_files=["invoice.txt"],
                expect_keywords=["16,450"],
            ),
            EvalQuestion(
                "What does the policy exclude?",
                expect_files=["policy.txt"],
                expect_keywords=["seepage", "mold", "earth movement"],
            ),
        ],
    ),
]


def get_cases(full: bool = False) -> list[EvalCase]:
    # Hook for a larger `--full` dataset later; SUBSET is the CI gate set.
    return SUBSET
