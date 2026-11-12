import { computeAutoWeightScalars, type AutoWeightBoneSegment, type AutoWeightPoint } from './meshWeights.ts';

export interface AutoWeightAsyncDiagnostics {
  usedWorker: boolean;
  workload: number;
  elapsedMs: number;
  fallbackReason?: string;
}
export interface AutoWeightAsyncResult extends AutoWeightAsyncDiagnostics {
  rows: ReturnType<typeof computeAutoWeightScalars>;
}
export interface AutoWeightAsyncControl {
  workerThreshold?: number;
  timeoutMs?: number;
}
const now = () => globalThis.performance?.now?.() ?? Date.now();
export async function computeAutoWeightScalarsAsync(
  points: AutoWeightPoint[],
  bones: AutoWeightBoneSegment[],
  options: Parameters<typeof computeAutoWeightScalars>[2] = {},
  control: AutoWeightAsyncControl = {},
): Promise<AutoWeightAsyncResult> {
  const workload = points.length * bones.length;
  const threshold = Math.max(1, Number(control.workerThreshold ?? 100_000));
  const timeoutMs = Math.max(1000, Number(control.timeoutMs ?? 30_000));
  const started = now();
  const sync = (fallbackReason?: string): AutoWeightAsyncResult => ({ rows: computeAutoWeightScalars(points, bones, options), usedWorker: false, workload, elapsedMs: now() - started, ...(fallbackReason ? { fallbackReason } : {}) });
  if (workload < threshold || typeof Worker === 'undefined') return sync(typeof Worker === 'undefined' && workload >= threshold ? 'worker-unavailable' : undefined);
  try {
    return await new Promise<AutoWeightAsyncResult>((resolve) => {
      const worker = new Worker(new URL('./weightAutoWorker.ts', import.meta.url), { type: 'module' });
      const id = `auto-weight-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      let settled = false;
      const finish = (value: AutoWeightAsyncResult) => { if (settled) return; settled = true; clearTimeout(timer); worker.terminate(); resolve(value); };
      const fallback = (reason: string) => finish(sync(reason));
      const timer = setTimeout(() => fallback('worker-timeout'), timeoutMs);
      worker.onmessage = (event: MessageEvent) => {
        if (event.data?.id !== id) return;
        if (!event.data?.ok) return fallback(`worker-error:${event.data?.error || 'unknown'}`);
        finish({ rows: event.data.rows, usedWorker: true, workload, elapsedMs: now() - started });
      };
      worker.onerror = (event) => fallback(`worker-runtime-error:${event.message || 'unknown'}`);
      worker.postMessage({ id, points, bones, options });
    });
  } catch (error) {
    return sync(`worker-init-error:${String((error as Error)?.message || error)}`);
  }
}
