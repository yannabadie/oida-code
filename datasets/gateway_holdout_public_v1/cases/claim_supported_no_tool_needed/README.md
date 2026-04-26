# Case `claim_supported_no_tool_needed`

Family: claim_contract. Expected delta: `same`.

Gateway pass-1 returns no `requested_tools`; the tool phase is a no-op; pass-2 mirrors the baseline. Both modes accept the same claim. The case demonstrates that the gateway-grounded loop does NOT introduce a regression on cases that don't need a tool.
