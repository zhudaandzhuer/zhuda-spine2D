import { computeAutoWeightScalars } from './meshWeights.ts';

(self as any).onmessage = (event: MessageEvent) => {
  const { id, points, bones, options } = event.data || {};
  try {
    const rows = computeAutoWeightScalars(points || [], bones || [], options || {});
    (self as any).postMessage({ id, ok: true, rows });
  } catch (error) {
    (self as any).postMessage({ id, ok: false, error: String((error as Error)?.message || error) });
  }
};
