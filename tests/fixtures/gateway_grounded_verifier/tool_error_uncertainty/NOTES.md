**Scenario:** pytest collection fails (rc=2). The adapter
classifies the result as `status="error"`, NOT `failed`. Phase
5.2 §5.2-D says `error` is uncertainty: the gateway loop emits
NO deterministic negative estimate; the run records a warning
but does not contradict the LLM claim with a tool fault. The
aggregator's verdict for this event remains `diagnostic_only`.
