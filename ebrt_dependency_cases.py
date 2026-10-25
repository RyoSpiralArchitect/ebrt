"""One engineered public join requiring context between reinspection sites.

The queried consignment's lookup key appears in R2, not R4. Both records are
longer than the quotation limit, so copying a whole source cannot satisfy the
extraction contract. Public geometry, graph, and post-run spans are manually
specified diagnostics, not automatically extracted dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Mapping

from ebrt_core import PostRunContract, RevisionTask
from local_output_diff_corpus_v0_8_2 import _revision_case


@dataclass(frozen=True)
class DependencyCase:
    task: RevisionTask
    contract: PostRunContract
    dependencies: tuple[tuple[str, str], ...]
    quote_contract: Mapping[str, list[str]]


def _tariff_key(index: int) -> str:
    return "BAND_" + hashlib.sha256(f"dependency-tariff-{index}".encode()).hexdigest()[:6].upper()


def build_case() -> DependencyCase:
    target_key = _tariff_key(37)
    target_register = (
        f"Consignment CN-581 belongs to account AC-204; account AC-204 uses tariff key {target_key}."
    )
    records = [
        f"Consignment CN-{710 + index} belongs to account AC-{430 + index}; "
        f"account AC-{430 + index} uses tariff key {_tariff_key((index * 11 + 5) % 64)}."
        for index in range(24)
    ]
    records.insert(13, target_register)
    target_mapping = f"{target_key} charges 29_CREDITS"
    rows = []
    for index in range(64):
        amount = 29 if index == 37 else (17, 23, 29)[index % 3]
        rows.append(
            f"Tariff key {_tariff_key(index)} charges {amount}_CREDITS per consignment. "
            f"Its settlement class remains CLASS_{index % 5} and its archive tier remains TIER_{index % 4}."
        )
    correction = (
        "Late correction: R3 is superseded. Join the queried consignment's account and tariff key "
        "from R2 to the current tariff table in R4. R1 concerns a different consignment."
    )
    geometry = (
        ((-0.46, 0.0, 0.0), (1.13, 0.0, 0.0)),
        ((0.14, 0.0, 0.0), (0.53, 0.0, 0.0)),
        ((-0.82, 0.0, 0.0), (1.02, 0.58, 0.0)),
        ((0.25, 0.0, 0.0), (1.06, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        ((0.63, 1.0, 0.0), (1.08, 0.49, 0.0)),
    )
    case = _revision_case(
        task_id="fresh-consignment-tariff-dependency",
        family="long_record_cross_source_lookup",
        question="Which service fee applies to consignment CN-581 after the tariff-table correction?",
        answer_choices=("17_CREDITS", "29_CREDITS"),
        prior_answer="17_CREDITS", expected_answer="29_CREDITS",
        texts=(
            f"Separate consignment CN-158 belongs to account AC-420 with tariff key {_tariff_key(12)}. "
            "Its still-active service fee is 17_CREDITS. It does not share the queried account.",
            "Account register. Each consignment uses its own account's tariff key.\n" + "\n".join(records),
            f"The retired tariff table assigns 17_CREDITS to tariff key {target_key}.",
            "Current tariff table. Match the registered key exactly; keys are not ordered by fee.\n"
            + "\n".join(rows),
            "The archive channel remains BATCH_LEDGER.",
            correction,
        ),
        stable_key="archive_channel", stable_value="BATCH_LEDGER", geometry=geometry,
    )
    return DependencyCase(
        task=case.task,
        contract=replace(case.contract, forbidden_support_ids=("R1", "R3")),
        dependencies=(("R2", "R4"),),
        quote_contract={
            "R6": ["R3 is superseded"],
            "R2": [target_register.removeprefix("Consignment ").removesuffix(".")],
            "R4": [target_mapping],
        },
    )
