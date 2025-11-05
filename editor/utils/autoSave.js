// Auto-save utilities for canvas state persistence
const AUTOSAVE_KEY = 'rayflow-canvas-autosave';
const AUTOSAVE_DELAY = 2000; // 2 seconds debounce

/**
 * Extract serializable canvas state for persistence
 */
function getCanvasState(state) {
    return {
        nodes: state.nodes || [],
        edges: state.edges || [],
        nodeIdCounter: state.nodeIdCounter || 1,
        timestamp: Date.now(),
        version: '1.0'
    };
}

/**
 * Save canvas state to localStorage with error handling
 */
function saveCanvasState(state) {
    try {
        const canvasState = getCanvasState(state);
        const serialized = JSON.stringify(canvasState);
        localStorage.setItem(AUTOSAVE_KEY, serialized);
        console.log('✅ Canvas auto-saved:', canvasState.nodes.length, 'nodes,', canvasState.edges.length, 'edges');
        return true;
    } catch (error) {
        console.error('❌ Failed to auto-save canvas:', error);
        return false;
    }
}

/**
 * Load canvas state from localStorage
 */
function loadCanvasState() {
    try {
        const saved = localStorage.getItem(AUTOSAVE_KEY);
        if (!saved) {
            console.log('💭 No auto-saved canvas found');
            return null;
        }

        const parsed = JSON.parse(saved);
        
        // Validate required fields
        if (!parsed.nodes || !parsed.edges || !parsed.nodeIdCounter) {
            console.warn('⚠️ Invalid auto-save data, ignoring');
            return null;
        }

        // Check if save is too old (more than 24 hours)
        const maxAge = 24 * 60 * 60 * 1000; // 24 hours
        if (parsed.timestamp && (Date.now() - parsed.timestamp) > maxAge) {
            console.log('🗑️ Auto-save too old, clearing');
            clearCanvasState();
            return null;
        }

        console.log('📂 Loaded auto-saved canvas:', parsed.nodes.length, 'nodes,', parsed.edges.length, 'edges');
        return {
            nodes: parsed.nodes,
            edges: parsed.edges,
            nodeIdCounter: parsed.nodeIdCounter
        };
    } catch (error) {
        console.error('❌ Failed to load auto-saved canvas:', error);
        clearCanvasState(); // Clear corrupted data
        return null;
    }
}

/**
 * Clear auto-saved canvas state
 */
function clearCanvasState() {
    try {
        localStorage.removeItem(AUTOSAVE_KEY);
        console.log('🗑️ Auto-save cleared');
        return true;
    } catch (error) {
        console.error('❌ Failed to clear auto-save:', error);
        return false;
    }
}

/**
 * Check if there's an auto-saved state available
 */
function hasAutoSave() {
    try {
        const saved = localStorage.getItem(AUTOSAVE_KEY);
        return saved !== null;
    } catch (error) {
        return false;
    }
}

/**
 * Get info about auto-saved state without loading it
 */
function getAutoSaveInfo() {
    try {
        const saved = localStorage.getItem(AUTOSAVE_KEY);
        if (!saved) return null;

        const parsed = JSON.parse(saved);
        return {
            nodeCount: parsed.nodes?.length || 0,
            edgeCount: parsed.edges?.length || 0,
            timestamp: parsed.timestamp,
            age: parsed.timestamp ? Date.now() - parsed.timestamp : null
        };
    } catch (error) {
        return null;
    }
}

/**
 * Debounce function to limit auto-save frequency
 */
function debounce(func, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

/**
 * Create debounced auto-save function
 */
const debouncedSave = debounce(saveCanvasState, AUTOSAVE_DELAY);

// Export for use in components
window.AutoSave = {
    save: saveCanvasState,
    load: loadCanvasState,
    clear: clearCanvasState,
    hasAutoSave,
    getInfo: getAutoSaveInfo,
    debouncedSave,
    AUTOSAVE_KEY,
    AUTOSAVE_DELAY
};