const ARM_LABELS: Record<string, string> = {
  direct_raw_fixed_revision: "Fixed-envelope Direct",
  direct_raw_fixed_revision_rerun: "Fixed-envelope Direct",
  full_restart: "Card-only reconstruction",
  staged_card_only_rerun: "Card-only reconstruction",
  direct_raw_no_revision: "No-envelope Direct",
  staged_cumulative_raw: "Retained-evidence reconstruction",
};

export function armLabel(arm: string) {
  return ARM_LABELS[arm] ?? arm.replaceAll("_", " ");
}
