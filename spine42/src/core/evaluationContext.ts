export interface EvaluationContext {
  projectId: string;
  skinName: string;
  animationName: string;
  time: number;
  frame?: number;
  fps?: number;
  runtimeRevision?: number;
}
export function normalizeEvaluationContext(context: Partial<EvaluationContext>): EvaluationContext {
  const fps = Number.isFinite(Number(context.fps)) && Number(context.fps) > 0 ? Number(context.fps) : undefined;
  const time = Math.max(0, Number(context.time) || 0);
  const frame = context.frame != null ? Math.max(0, Math.round(Number(context.frame) || 0)) : fps ? Math.max(0, Math.round(time * fps)) : undefined;
  return {
    projectId: String(context.projectId || ''),
    skinName: String(context.skinName || 'default'),
    animationName: String(context.animationName || ''),
    time,
    ...(fps ? { fps } : {}),
    ...(frame != null ? { frame } : {}),
    ...(context.runtimeRevision != null ? { runtimeRevision: Number(context.runtimeRevision) || 0 } : {}),
  };
}
export function evaluationContextKey(context: Partial<EvaluationContext>): string {
  const c = normalizeEvaluationContext(context);
  return [c.projectId, c.skinName, c.animationName, c.time.toFixed(6), c.frame ?? '', c.fps ?? '', c.runtimeRevision ?? ''].map(encodeURIComponent).join('|');
}
