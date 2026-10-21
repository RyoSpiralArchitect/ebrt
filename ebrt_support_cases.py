"""Fresh synthetic support-retention diagnostics for hosted development.

The three cases deliberately expose a low-credit required observation, a
low-credit required rule, and an already-covered no-answer-change control.
They are engineered compiler-coverage diagnostics, not a random sample or a
reasoning benchmark. The public geometry and post-run contracts are fixed
before provider calls; neither the answer nor a required-support list is
added to the model prompt by this module.
"""

from __future__ import annotations

from local_output_diff_corpus_v0_8_2 import CorpusCase, _revision_case


def build_cases() -> tuple[CorpusCase, ...]:
    """Return independent tasks with two materially necessary support facts."""
    miss_observation = (
        ((-0.42, 0.0, 0.0), (0.83, 0.0, 0.0)),
        ((0.12, 0.0, 0.0), (0.47, 0.0, 0.0)),
        ((-0.81, 0.0, 0.0), (1.01, 0.59, 0.0)),
        ((0.23, 0.0, 0.0), (0.95, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        ((0.61, 1.0, 0.0), (1.02, 0.51, 0.0)),
    )
    miss_rule = (
        ((-0.53, 0.0, 0.0), (1.10, 0.0, 0.0)),
        ((0.22, 0.0, 0.0), (0.98, 0.0, 0.0)),
        ((-0.79, 0.0, 0.0), (1.01, 0.59, 0.0)),
        ((0.12, 0.0, 0.0), (0.45, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        ((0.61, 1.0, 0.0), (1.02, 0.51, 0.0)),
    )
    covered_control = (
        ((-0.39, 0.0, 0.0), (0.20, 0.0, 0.0)),
        ((0.12, 0.0, 0.0), (0.90, 0.0, 0.0)),
        ((-0.77, 0.0, 0.0), (1.00, 0.60, 0.0)),
        ((0.22, 0.0, 0.0), (1.00, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        ((0.62, 1.0, 0.0), (1.00, 0.50, 0.0)),
    )
    return (
        _revision_case(
            task_id="fresh-normalization-support",
            family="required_observation_coverage_gap",
            question="What normalized value should be reported for sample V-31 under the corrected rule?",
            answer_choices=("28_UNITS", "70_UNITS"),
            prior_answer="70_UNITS",
            expected_answer="28_UNITS",
            texts=(
                "Sample V-31 requires one normalized report.",
                "The raw reading recorded for sample V-31 is 14.",
                "The retired rule multiplies the raw reading by 5.",
                "The current rule multiplies the raw reading by 2 to obtain normalized units.",
                "The report format remains CSV_REPORT.",
                "Late correction: R3 is superseded; apply the current rule in R4 to the measurement in R2.",
            ),
            stable_key="report_format",
            stable_value="CSV_REPORT",
            geometry=miss_observation,
        ),
        _revision_case(
            task_id="fresh-parcel-routing-support",
            family="required_rule_coverage_gap",
            question="Where must parcel K-19 be routed under the corrected routing table?",
            answer_choices=("HARBOR", "RIDGE"),
            prior_answer="HARBOR",
            expected_answer="RIDGE",
            texts=(
                "Parcel K-19 needs one routing destination.",
                "The recorded hazard class of parcel K-19 is CLASS_N.",
                "The retired routing table maps CLASS_N parcels to HARBOR.",
                "The current routing table maps CLASS_M parcels to HARBOR and CLASS_N parcels to RIDGE.",
                "The packaging remains SEALED_PACKAGE.",
                "Late correction: R3 is superseded; apply the current table in R4 to the parcel record in R2.",
            ),
            stable_key="packaging",
            stable_value="SEALED_PACKAGE",
            geometry=miss_rule,
        ),
        _revision_case(
            task_id="fresh-duration-no-answer-change",
            family="already_covered_no_answer_change",
            question="Should request D-18 be ALLOW or DENY under the corrected duration policy?",
            answer_choices=("DENY", "ALLOW"),
            prior_answer="ALLOW",
            expected_answer="ALLOW",
            texts=(
                "Request D-18 requires one duration-policy decision.",
                "The recorded duration of request D-18 is 8 hours.",
                "The retired policy says ALLOW for durations at most 10 hours and DENY otherwise.",
                "The current policy says ALLOW for durations at most 12 hours and DENY otherwise.",
                "The review channel remains HUMAN_REVIEW.",
                "Late correction: R3 is superseded; apply the current policy in R4 to the duration in R2.",
            ),
            stable_key="review_channel",
            stable_value="HUMAN_REVIEW",
            geometry=covered_control,
        ),
    )
