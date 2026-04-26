**Scenario:** pass-1 forward asks for pytest; gateway runs ok;
pass-2 forward cites the tool's `[E.tool_output.0]` evidence;
backward says necessary conditions met; aggregator accepts.

The fixture demonstrates the happy path of the two-pass loop:
forward → tool phase → enriched evidence → forward → accept.
