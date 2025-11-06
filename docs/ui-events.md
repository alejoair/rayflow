# UI Events System

This document explains how the visual editor handles events, state management, and the interaction between React Flow and the global context.

## Architecture Overview

```
React Flow (Visual Canvas) ←→ Canvas.js ←→ FlowContext (Global State) ←→ AutoSave (localStorage)
                                    ↓
                              Inspector.js
```

## Key Components

### 1. FlowContext (`editor/context/FlowContext.js`)

The global state manager using React Context + useReducer pattern:

- **State**: `nodes`, `edges`, `nodeIdCounter`, `selectedNode`, `variables`, etc.
- **Actions**: Functions to update state (`addNode`, `setNodes`, `updateNodeConstants`, etc.)
- **Auto-save**: Observes state changes and saves to localStorage with 2-second debounce

**Auto-save Implementation:**
```javascript
React.useEffect(() => {
    if (state.loading) return;

    const currentCounts = {
        nodeCount: state.nodes.length,
        edgeCount: state.edges.length,
        counter: state.nodeIdCounter
    };

    const hasChanged = /* compare with lastSaveRef */;

    if (hasChanged) {
        setTimeout(() => {
            window.AutoSave.save(stateToSave);
        }, 2000);
    }
});
```

### 2. Canvas.js (`editor/components/Canvas.js`)

Bridges React Flow with the global context. Handles the critical challenge of synchronizing React Flow's internal state with the global context without creating infinite loops.

**Key Challenge: The Infinite Loop Problem**

When using React Flow in "controlled mode" (passing `nodes` and `edges` as props), updates can create infinite loops:

```
1. Context updates nodes → 2. Canvas re-renders with new nodes prop
                              ↓
6. Canvas re-renders ← 5. Context updates ← 4. onNodesChange fires ← 3. React Flow detects prop change
```

**Solution: Filtering Non-Significant Changes**

React Flow generates multiple types of events:
- **`select`**: User selects/deselects nodes
- **`position`**: User drags nodes to new positions
- **`remove`**: User deletes nodes
- **`add`**: New nodes are added
- **`dimensions`**: React Flow recalculates node dimensions (internal, triggered by re-renders)

The key is to filter out `dimensions` events, which are purely internal to React Flow:

```javascript
const onNodesChange = React.useCallback((changes) => {
    // Filter out dimensions changes - these are internal React Flow events
    const significantChanges = changes.filter(change => change.type !== 'dimensions');

    if (significantChanges.length === 0) {
        // Don't propagate dimensions-only changes to global state
        return;
    }

    // Apply only significant changes
    const updatedNodes = applyNodeChanges(significantChanges, state.nodes);
    actions.setNodes(updatedNodes);
}, [actions]); // Note: state.nodes NOT in dependencies
```

**Critical Pattern: No State in Dependencies**

The callback does NOT include `state.nodes` in its dependency array:
```javascript
}, [actions]); // ← Only actions, NOT state.nodes
```

**Why?** If `state.nodes` were in the dependencies:
1. Every context update would recreate the callback
2. React Flow would detect the prop change
3. Generate new events (including dimensions)
4. Trigger `onNodesChange` again → **infinite loop**

Instead, we access `state.nodes` directly inside the callback (stale closure), which is safe because:
- We immediately call `actions.setNodes()` with the updated nodes
- The next render will have fresh state
- We filter out dimensions events that would cause loops

### 3. Inspector.js (`editor/components/Inspector.js`)

Edits node properties and constants. Updates go directly to global context:

```javascript
const handleConstantChange = (constName, value) => {
    const newValues = { ...constantValues, [constName]: value };
    actions.updateNodeConstants(selectedNode.id, newValues);
    // ↑ Updates context → triggers auto-save
    // ↓ React Flow recalculates dimensions (but we filter these out)
};
```

**When you change a constant:**
1. Inspector calls `actions.updateNodeConstants()`
2. Context updates the node's `data.constantValues`
3. Auto-save detects the change and saves to localStorage (2s debounce)
4. Canvas receives new `nodes` prop from context
5. React Flow recalculates dimensions and fires "dimensions" events
6. Canvas filters out these events (returns early)
7. **No loop, change is saved** ✅

## Event Flow Diagrams

### User Clicks Node

```
User clicks → React Flow detects → onNodeClick fires → onSelectionChange fires
                                        ↓                        ↓
                              onNodeSelect(node)       Update internal selection
                                        ↓
                              actions.selectNode(node)
                                        ↓
                              Context updates selectedNode
                                        ↓
                              Inspector shows node details
```

### User Drags Node

```
User drags → onNodeDragStart → onNodeDragStop → React Flow generates "position" change
                                                            ↓
                                                    onNodesChange([{ type: 'position' }])
                                                            ↓
                                                    Filter: position is significant ✓
                                                            ↓
                                                    actions.setNodes(updatedNodes)
                                                            ↓
                                                    Context updates
                                                            ↓
                                                    Auto-save triggers (2s debounce)
```

### User Changes Constant in Inspector

```
User types → handleConstantChange → actions.updateNodeConstants
                                            ↓
                                    Context updates node.data.constantValues
                                            ↓
                            ┌───────────────┴───────────────┐
                            ↓                               ↓
                    Auto-save triggers              Canvas receives new nodes prop
                    (2s debounce)                           ↓
                            ↓                       React Flow recalculates dimensions
                    Save to localStorage                    ↓
                                            onNodesChange([{ type: 'dimensions' }])
                                                            ↓
                                            Filter: dimensions NOT significant ✗
                                                            ↓
                                                    return early (no state update)
                                                            ↓
                                                    No loop! ✅
```

## Event Types Reference

### React Flow Node Change Types

| Type | Description | Significant? | Action |
|------|-------------|--------------|--------|
| `select` | User selects/deselects node | ✅ Yes | Update context, propagate to Inspector |
| `position` | User drags node | ✅ Yes | Update context, trigger auto-save |
| `remove` | User deletes node | ✅ Yes | Update context, clean up edges, auto-save |
| `add` | New node added | ✅ Yes | Update context, auto-save |
| `dimensions` | React Flow recalculates size | ❌ No | **Filtered out** to prevent loops |

### React Flow Edge Change Types

All edge changes are currently considered significant and propagated to context.

## Common Pitfalls

### ❌ DON'T: Include state in onNodesChange dependencies

```javascript
// BAD - Creates infinite loop
const onNodesChange = React.useCallback((changes) => {
    const updated = applyNodeChanges(changes, state.nodes);
    actions.setNodes(updated);
}, [actions, state.nodes]); // ← state.nodes causes loop!
```

### ✅ DO: Access state directly, filter dimensions

```javascript
// GOOD - No loop
const onNodesChange = React.useCallback((changes) => {
    const significant = changes.filter(c => c.type !== 'dimensions');
    if (significant.length === 0) return;

    const updated = applyNodeChanges(significant, state.nodes);
    actions.setNodes(updated);
}, [actions]); // ← Only actions
```

### ❌ DON'T: Update context on every dimension change

```javascript
// BAD - Causes infinite re-renders
const onNodesChange = React.useCallback((changes) => {
    // No filtering = dimensions events propagate
    const updated = applyNodeChanges(changes, state.nodes);
    actions.setNodes(updated); // ← Triggers re-render → dimensions → repeat
}, [actions]);
```

## Auto-Save System

Located in `editor/utils/autoSave.js`, provides:

- **`window.AutoSave.save(state)`**: Save to localStorage
- **`window.AutoSave.load()`**: Load from localStorage
- **`window.AutoSave.clear()`**: Clear saved state
- **`window.AutoSave.hasAutoSave()`**: Check if save exists
- **`window.AutoSave.getInfo()`**: Get metadata (node count, timestamp)

**Integration with FlowContext:**

```javascript
// FlowContext observes state and triggers auto-save
React.useEffect(() => {
    if (hasChanged) {
        setTimeout(() => {
            window.AutoSave.save({
                nodes: state.nodes,
                edges: state.edges,
                nodeIdCounter: state.nodeIdCounter
            });
        }, 2000); // 2-second debounce
    }
});
```

**On page load:**

```javascript
// FlowContext checks for saved state
React.useEffect(() => {
    if (window.AutoSave.hasAutoSave()) {
        const savedState = window.AutoSave.load();
        dispatch({ type: ActionTypes.SET_NODES, payload: { nodes: savedState.nodes } });
        dispatch({ type: ActionTypes.SET_EDGES, payload: { edges: savedState.edges } });
    }
}, [state.loading, state.availableNodes.length]);
```

## Debugging Tips

### Check Event Flow

Add logging to track events:
```javascript
const onNodesChange = React.useCallback((changes) => {
    console.log('Changes:', changes.map(c => ({ type: c.type, id: c.id })));
    // ...
});
```

### Verify Auto-Save

Check localStorage in browser DevTools:
```javascript
// Console
window.AutoSave.getInfo()
// Returns: { nodeCount: 3, edgeCount: 2, timestamp: 1699... }
```

### Test Loop Prevention

If you see repeated logs of the same event type, check:
1. Are dimensions events being filtered?
2. Is `state.nodes`/`state.edges` in callback dependencies?
3. Is `actions.setNodes()` being called unnecessarily?

## Performance Considerations

- **Debounced Auto-Save**: 2-second delay prevents excessive localStorage writes
- **Filtered Events**: Only propagate significant changes to reduce re-renders
- **Stable Callbacks**: Keep dependencies minimal to prevent callback recreation
- **Direct State Access**: Access `state.nodes` directly in callbacks (no dependency) to avoid recreation

## Future Improvements

- Consider using `useNodesState` and `useEdgesState` from React Flow for truly local state
- Sync with context only for:
  - Auto-save (periodic snapshot)
  - Export/Import operations
  - Cross-component communication (e.g., Inspector)
- This would eliminate the need for filtering dimensions events
