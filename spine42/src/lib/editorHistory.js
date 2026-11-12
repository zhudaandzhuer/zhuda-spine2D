function defaultClone(value) {
  if (typeof structuredClone === 'function') return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

export function createEditorHistory({ limit = 80, clone = defaultClone, serialize = JSON.stringify } = {}) {
  const maxEntries = Math.max(1, Math.floor(Number(limit) || 80));
  const undoStack = [];
  const redoStack = [];
  let baselineSignature = null;

  const signature = document => serialize(document ?? null);
  const snapshot = (document, context = {}, label = '') => ({
    document: clone(document),
    context: clone(context),
    label: String(label || ''),
    signature: signature(document),
  });
  const trim = stack => { while (stack.length > maxEntries) stack.shift(); };

  function reset(document) {
    undoStack.length = 0;
    redoStack.length = 0;
    baselineSignature = signature(document);
  }

  function clear() {
    undoStack.length = 0;
    redoStack.length = 0;
  }

  function hasChanged(before, document) {
    return !!before && before.signature !== signature(document);
  }

  function commit(before, document, label = before?.label || '') {
    if (!hasChanged(before, document)) return false;
    undoStack.push({ ...before, label: String(label || before?.label || '編輯') });
    trim(undoStack);
    redoStack.length = 0;
    return true;
  }

  function undo(currentDocument, currentContext = {}) {
    const target = undoStack.pop();
    if (!target) return null;
    redoStack.push(snapshot(currentDocument, currentContext, target.label));
    trim(redoStack);
    return clone(target);
  }

  function redo(currentDocument, currentContext = {}) {
    const target = redoStack.pop();
    if (!target) return null;
    undoStack.push(snapshot(currentDocument, currentContext, target.label));
    trim(undoStack);
    return clone(target);
  }

  function markSaved(document) {
    baselineSignature = signature(document);
  }

  function state(document) {
    return {
      dirty: baselineSignature != null && signature(document) !== baselineSignature,
      canUndo: undoStack.length > 0,
      canRedo: redoStack.length > 0,
      undoLabel: undoStack.at(-1)?.label || '',
      redoLabel: redoStack.at(-1)?.label || '',
      undoDepth: undoStack.length,
      redoDepth: redoStack.length,
      limit: maxEntries,
    };
  }

  return { snapshot, reset, clear, hasChanged, commit, undo, redo, markSaved, state };
}

export default createEditorHistory;
