# Multiple RETURN Nodes Strategy

## Problem
When a flow has multiple RETURN nodes that can execute simultaneously, we need to define clear behavior for how the orchestrator handles this scenario.

## Example Scenario
```
START → ADD_1 → RETURN_A
   └──→ ADD_2 → RETURN_B
              └─→ RETURN_A (data connection)
```

In this case, both RETURN_A and RETURN_B can potentially execute.

## Chosen Strategy: "First Return Wins"

### Behavior
1. **Immediate Termination**: When ANY RETURN node executes, the entire flow terminates immediately
2. **Single Result**: The value from the first RETURN becomes the flow's final result
3. **Cancellation**: All other running nodes are cancelled/stopped
4. **Ignore Subsequent**: Any RETURN nodes that haven't executed yet are ignored

### Rationale
- **Consistency with Functions**: Traditional functions return once
- **Unreal Engine Compatibility**: Blueprints use this same strategy
- **Predictable Behavior**: Clear, deterministic outcome
- **Performance**: No need to wait for all branches

### Implementation in Orchestrator

```python
class FlowOrchestrator:
    def __init__(self):
        self._flow_completed = False
        self._final_result = None
        self._cancelled_nodes = set()

    async def handle_return_execution(self, node_id: str, return_value: Any):
        """Handle RETURN node execution with First Return Wins strategy"""
        if self._flow_completed:
            # Another RETURN already won, ignore this one
            return

        # Mark flow as completed
        self._flow_completed = True
        self._final_result = return_value

        # Cancel all other running nodes
        await self._cancel_remaining_nodes(except_node=node_id)

        # Complete the flow with this result
        await self._complete_flow(return_value)
```

### Validation Considerations

**Option 1: Allow Multiple RETURNs (Recommended)**
- Show warning in frontend: "⚠️ Multiple RETURN paths detected. First executed RETURN will terminate flow."
- Allow advanced users to use this pattern intentionally

**Option 2: Prohibit Multiple RETURNs**
- Add validation error: "Flow must have exactly one reachable RETURN node"
- More restrictive but simpler for beginners

**Recommendation**: Use Option 1 with clear documentation.

### Edge Cases

1. **Simultaneous Execution**: If two RETURNs execute at exactly the same time, the orchestrator's internal race condition determines winner
2. **RETURN with No Result**: Empty/null values are still valid return values
3. **Exception in RETURN**: If RETURN fails, that's an error, not a successful completion

### Future Extensions

Could add optional flow metadata to control this behavior:
```json
{
  "returnStrategy": "firstWins" | "waitAll" | "primaryPath",
  "primaryReturnPath": "node_id_of_primary_return"
}
```

But for now, "First Return Wins" is the default and only strategy.