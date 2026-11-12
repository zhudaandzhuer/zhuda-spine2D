export type EditorMode = 'review' | 'animate' | 'setup' | 'mesh' | 'weights' | 'constraints' | 'deform';
export type EditorCapability =
  | 'read'
  | 'playback'
  | 'reviewQa'
  | 'editAnimation'
  | 'editSetup'
  | 'editMeshTopology'
  | 'editWeights'
  | 'editConstraintSetup'
  | 'editConstraintAnimation'
  | 'editDeform'
  | 'editGraph'
  | 'editDopeSheet';

const CAPABILITIES: Record<EditorMode, ReadonlySet<EditorCapability>> = {
  review: new Set(['read','playback','reviewQa']),
  animate: new Set(['read','playback','reviewQa','editAnimation','editConstraintAnimation','editGraph','editDopeSheet']),
  setup: new Set(['read','reviewQa','editSetup','editConstraintSetup']),
  mesh: new Set(['read','reviewQa','editMeshTopology']),
  weights: new Set(['read','reviewQa','editWeights']),
  constraints: new Set(['read','playback','reviewQa','editConstraintSetup','editConstraintAnimation']),
  deform: new Set(['read','playback','reviewQa','editDeform','editGraph','editDopeSheet']),
};
export const EDITOR_MODES = Object.freeze(Object.keys(CAPABILITIES) as EditorMode[]);
export function isEditorMode(value: unknown): value is EditorMode { return typeof value==='string' && Object.prototype.hasOwnProperty.call(CAPABILITIES,value); }
export function canModePerform(mode: EditorMode, capability: EditorCapability): boolean { return !!CAPABILITIES[mode]?.has(capability); }
export function requireModeCapability(mode: EditorMode, capability: EditorCapability): void {
  if (!canModePerform(mode, capability)) throw new Error(`MODE_BLOCKED: ${mode} cannot perform ${capability}`);
}
export interface ModeMachine {
  readonly mode: EditorMode;
  setMode(next: EditorMode): EditorMode;
  can(capability: EditorCapability): boolean;
  require(capability: EditorCapability): void;
}
export function createModeMachine(initial: EditorMode = 'review', onChange?: (next: EditorMode, previous: EditorMode) => void): ModeMachine {
  let current = initial;
  return {
    get mode() { return current; },
    setMode(next) { if(!isEditorMode(next))throw new Error(`Unknown editor mode: ${String(next)}`);const previous=current; current=next; if(next!==previous) onChange?.(next,previous); return current; },
    can(capability) { return canModePerform(current, capability); },
    require(capability) { requireModeCapability(current, capability); },
  };
}
export const EDITOR_MODE_CAPABILITIES = CAPABILITIES;
