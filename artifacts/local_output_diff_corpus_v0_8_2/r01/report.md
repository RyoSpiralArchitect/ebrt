# EBRT v0.8.2 local output-diff development corpus

This is a development corpus, not a benchmark or a causal-effect estimate.

## Summary

- Models: `4`
- Paired cells: `16`
- Provider calls: `32`
- Direct strict passes: `3`
- EBRT strict passes: `2`
- Raw-output diff cells: `16`
- Answer-diff cells: `0`
- Support-diff cells: `4`
- Both-arms-parsed cells: `4`
- Format-failed cells: `12`
- Generation-error cells: `0`
- Categories: `{"BOTH_FAIL": 12, "BOTH_PASS": 1, "DIRECT_ONLY_PASS": 2, "EBRT_ONLY_PASS": 1}`

## Adapter readiness

A model enters algorithm diagnosis only when both arms parse in all four cells. A format failure is an adapter/capability observation, not an EBRT-quality loss.

| Model | Prompt mode | Parsed outputs | Format errors | Generation errors | Diagnostic scope |
| :--- | :--- | ---: | ---: | ---: | :--- |
| mlx-community/Mistral-7B-Instruct-v0.3-4bit@a4b8f870474b0eb527f466a03fbc187830d271f5 | chat_template | 8/8 | 0 | 0 | ALGORITHM_DIAGNOSTIC_ELIGIBLE |
| mlx-community/Llama-3.2-3B-bf16@60a99aaf43164077157d64bf909b7b61143c6a6d | plain_text | 0/8 | 8 | 0 | ADAPTER_OR_CAPABILITY_DIAGNOSTIC |
| mlx-community/gemma-2-2b-4bit@2da7060bea6e767e27d7a776f834071ba69bd3ba | plain_text | 0/8 | 8 | 0 | ADAPTER_OR_CAPABILITY_DIAGNOSTIC |
| HuggingFaceTB/SmolLM2-135M-Instruct@12fd25f77366fa6b3b4b768ec3050bf629380bac | chat_template | 0/8 | 8 | 0 | ADAPTER_OR_CAPABILITY_DIAGNOSTIC |

## Cells

| Model | Case | Direct | EBRT | Direct strict | EBRT strict | Category |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| mlx-community/Mistral-7B-Instruct-v0.3-4bit@a4b8f870474b0eb527f466a03fbc187830d271f5 | release-priority-revision | PROVE | PROVE | FAIL | PASS | EBRT_ONLY_PASS |
| mlx-community/Mistral-7B-Instruct-v0.3-4bit@a4b8f870474b0eb527f466a03fbc187830d271f5 | registry-route-revision | BLUE | BLUE | PASS | FAIL | DIRECT_ONLY_PASS |
| mlx-community/Mistral-7B-Instruct-v0.3-4bit@a4b8f870474b0eb527f466a03fbc187830d271f5 | invalidated-sensor-fallback | BACKUP_42 | BACKUP_42 | PASS | FAIL | DIRECT_ONLY_PASS |
| mlx-community/Mistral-7B-Instruct-v0.3-4bit@a4b8f870474b0eb527f466a03fbc187830d271f5 | unit-schema-reinterpretation | 0.25_M | 0.25_M | PASS | PASS | BOTH_PASS |
| mlx-community/Llama-3.2-3B-bf16@60a99aaf43164077157d64bf909b7b61143c6a6d | release-priority-revision | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| mlx-community/Llama-3.2-3B-bf16@60a99aaf43164077157d64bf909b7b61143c6a6d | registry-route-revision | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| mlx-community/Llama-3.2-3B-bf16@60a99aaf43164077157d64bf909b7b61143c6a6d | invalidated-sensor-fallback | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| mlx-community/Llama-3.2-3B-bf16@60a99aaf43164077157d64bf909b7b61143c6a6d | unit-schema-reinterpretation | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| mlx-community/gemma-2-2b-4bit@2da7060bea6e767e27d7a776f834071ba69bd3ba | release-priority-revision | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| mlx-community/gemma-2-2b-4bit@2da7060bea6e767e27d7a776f834071ba69bd3ba | registry-route-revision | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| mlx-community/gemma-2-2b-4bit@2da7060bea6e767e27d7a776f834071ba69bd3ba | invalidated-sensor-fallback | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| mlx-community/gemma-2-2b-4bit@2da7060bea6e767e27d7a776f834071ba69bd3ba | unit-schema-reinterpretation | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| HuggingFaceTB/SmolLM2-135M-Instruct@12fd25f77366fa6b3b4b768ec3050bf629380bac | release-priority-revision | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| HuggingFaceTB/SmolLM2-135M-Instruct@12fd25f77366fa6b3b4b768ec3050bf629380bac | registry-route-revision | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| HuggingFaceTB/SmolLM2-135M-Instruct@12fd25f77366fa6b3b4b768ec3050bf629380bac | invalidated-sensor-fallback | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |
| HuggingFaceTB/SmolLM2-135M-Instruct@12fd25f77366fa6b3b4b768ec3050bf629380bac | unit-schema-reinterpretation | FORMAT_ERROR | FORMAT_ERROR | FAIL | FAIL | BOTH_FAIL |

## Boundary

- Each arm receives one deterministic local-model generation call under the same model snapshot and token ceiling.
- The arms necessarily differ in evidence order and revision instructions; output differences are not attributable to gradients alone.
- Semantic contracts are development labels fixed with the synthetic cases and are never included in model prompts.
- Public trajectories are inspectable surrogates, not transcripts of private model reasoning.
- No native activation or sampled latent receipt is captured by this breadth runner.
- This corpus can suggest engineering hypotheses but does not establish general reasoning improvement or cross-model regularity.
