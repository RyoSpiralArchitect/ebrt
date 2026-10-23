"""Fresh competing-chain cases for the control-alignment diagnostic.

Each task needs an entity join in R2 and the current multi-row rule in R4.
R1 supplies a complete, still-active chain for a different entity that yields
the competing answer. R6 invalidates only the retired rule and never states
the target answer. The second case must retain its prior answer.

Roles, geometries, and post-run gold are caller-supplied synthetic scaffolds;
they are not dependencies extracted by the engine or a model-quality sample.
"""

from __future__ import annotations

from dataclasses import replace

from ebrt_core import validate_contract
from local_output_diff_corpus_v0_8_2 import CorpusCase, _revision_case


def build_cases() -> tuple[CorpusCase, ...]:
    """Return two fixed tasks with asymmetric, positive required controls."""
    invoice_geometry = (
        ((-0.46, 0.0, 0.0), (1.13, 0.0, 0.0)),
        ((0.14, 0.0, 0.0), (0.53, 0.0, 0.0)),
        ((-0.82, 0.0, 0.0), (1.02, 0.58, 0.0)),
        ((0.25, 0.0, 0.0), (1.06, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        ((0.63, 1.0, 0.0), (1.08, 0.49, 0.0)),
    )
    booking_geometry = (
        ((-0.51, 0.0, 0.0), (0.91, 0.0, 0.0)),
        ((0.20, 0.0, 0.0), (1.03, 0.0, 0.0)),
        ((-0.78, 0.0, 0.0), (1.04, 0.57, 0.0)),
        ((0.13, 0.0, 0.0), (0.48, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        ((0.60, 1.0, 0.0), (1.01, 0.53, 0.0)),
    )
    cases = (
        _revision_case(
            task_id="fresh-invoice-account-fee-join",
            family="competing_entity_join_answer_change",
            question="Which handling fee applies to invoice INV-73 after the fee-table correction?",
            answer_choices=("5_CREDITS", "11_CREDITS"),
            prior_answer="11_CREDITS",
            expected_answer="5_CREDITS",
            texts=(
                "Another invoice, INV-37, belongs to account AC-4 in region EAST with contract FLEX. "
                "Its still-active regional contract rule is (EAST,FLEX) -> 11_CREDITS. "
                "That separate invoice remains in this batch.",
                "Invoice-to-account register: INV-73 belongs to AC-9; INV-37 belongs to AC-4. "
                "Account directory: AC-9 has region WEST and contract FLEX; "
                "AC-4 has region EAST and contract FLEX.",
                "The retired fee table assigns 11_CREDITS to (WEST,FLEX), "
                "5_CREDITS to (EAST,FLEX), 11_CREDITS to (WEST,CORE), and 5_CREDITS to (EAST,CORE).",
                "The current fee table assigns 5_CREDITS to (WEST,FLEX), "
                "11_CREDITS to (EAST,FLEX), 11_CREDITS to (WEST,CORE), and 5_CREDITS to (EAST,CORE). "
                "Join the invoice's account to its region and contract before choosing the fee.",
                "The archive channel remains BATCH_ARCHIVE.",
                "Late correction: R3 is superseded. Join the invoice and account records in R2 "
                "to the current table in R4 for the invoice asked about. R1 describes a different invoice.",
            ),
            stable_key="archive_channel",
            stable_value="BATCH_ARCHIVE",
            geometry=invoice_geometry,
        ),
        _revision_case(
            task_id="fresh-booking-group-capacity-join",
            family="competing_entity_join_no_answer_change",
            question="Should booking BK-81 be CONFIRM or WAITLIST after the session-capacity correction?",
            answer_choices=("WAITLIST", "CONFIRM"),
            prior_answer="CONFIRM",
            expected_answer="CONFIRM",
            texts=(
                "Another booking, BK-18, joins group G-8 of size 9 to session SS-5, "
                "whose still-active rule confirms groups of at most 5 and waitlists larger groups. "
                "BK-18 therefore remains WAITLIST. "
                "This separate booking does not share the target booking's group or session.",
                "Booking register: BK-81 selects session SS-2 and group G-7; "
                "BK-18 selects session SS-5 and group G-8. Group directory: G-7 has size 6; G-8 has size 9.",
                "The retired session table gives SS-2 a capacity of 6 and SS-5 a capacity of 5. "
                "A booking is CONFIRM when its group size is at most its session's capacity; otherwise WAITLIST.",
                "The current session table gives SS-2 a capacity of 7 and SS-5 a capacity of 5. "
                "A booking is CONFIRM when its group size is at most its session's capacity; otherwise WAITLIST. "
                "Join the booking's group and session before comparing size with capacity.",
                "The notification channel remains EMAIL_NOTICE.",
                "Late correction: R3 is superseded. Join the booking and group records in R2 "
                "to the current session table in R4 for the booking asked about. "
                "The separate booking in R1 remains active.",
            ),
            stable_key="notification_channel",
            stable_value="EMAIL_NOTICE",
            geometry=booking_geometry,
        ),
    )
    # The distractor remains valid for its own entity, but citing that chain
    # as support for the queried entity is still a lineage error.
    guarded = tuple(
        replace(case, contract=replace(case.contract, forbidden_support_ids=("R1", "R3")))
        for case in cases
    )
    for case in guarded:
        validate_contract(case.task, case.contract)
    return guarded
