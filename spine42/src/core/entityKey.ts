export type EntityKey =
  | { kind: 'bone'; name: string }
  | { kind: 'slot'; name: string }
  | { kind: 'skin'; name: string }
  | { kind: 'attachment'; skin: string; slot: string; name: string }
  | { kind: 'meshVertex'; skin: string; slot: string; attachment: string; vertexId: string }
  | { kind: 'animation'; name: string }
  | { kind: 'timeline'; animation: string; owner: string; property: string }
  | { kind: 'ikConstraint'; name: string }
  | { kind: 'transformConstraint'; name: string }
  | { kind: 'pathConstraint'; name: string };

const enc = (value: string) => encodeURIComponent(value);
export function entityKeyToString(key: EntityKey): string {
  switch (key.kind) {
    case 'bone': case 'slot': case 'skin': case 'animation': case 'ikConstraint': case 'transformConstraint': case 'pathConstraint':
      return `${key.kind}:${enc(key.name)}`;
    case 'attachment': return `attachment:${enc(key.skin)}/${enc(key.slot)}/${enc(key.name)}`;
    case 'meshVertex': return `meshVertex:${enc(key.skin)}/${enc(key.slot)}/${enc(key.attachment)}/${enc(key.vertexId)}`;
    case 'timeline': return `timeline:${enc(key.animation)}/${enc(key.owner)}/${enc(key.property)}`;
  }
}
export function sameEntityKey(a: EntityKey, b: EntityKey): boolean { return entityKeyToString(a) === entityKeyToString(b); }
export const boneKey = (name: string): EntityKey => ({ kind: 'bone', name });
export const slotKey = (name: string): EntityKey => ({ kind: 'slot', name });
export const attachmentKey = (skin: string, slot: string, name: string): EntityKey => ({ kind: 'attachment', skin, slot, name });
