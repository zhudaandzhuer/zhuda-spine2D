export type JsonScalar = string | number | boolean | null;
export type JsonValue = JsonScalar | JsonObject | JsonValue[];
export interface JsonObject { [key: string]: JsonValue | undefined; }

export interface SpineSkeletonMeta extends JsonObject {
  spine?: string;
  hash?: string;
  width?: number;
  height?: number;
}
export interface SpineBone extends JsonObject {
  name: string;
  parent?: string;
}
export interface SpineSlot extends JsonObject {
  name: string;
  bone: string;
  attachment?: string;
}
export interface SpineConstraint extends JsonObject {
  name: string;
  order?: number;
  target?: string;
  bones?: string[];
}
export interface SpineAnimation extends JsonObject {
  bones?: JsonObject;
  slots?: JsonObject;
  ik?: JsonObject;
  transform?: JsonObject;
  paths?: JsonObject;
  deform?: JsonObject;
  drawOrder?: JsonValue[];
  events?: JsonValue[];
}
export interface SpineSkinRecord extends JsonObject {
  name?: string;
  attachments?: JsonObject;
}
export interface SpineDocument extends JsonObject {
  skeleton?: SpineSkeletonMeta;
  bones: SpineBone[];
  slots?: SpineSlot[];
  skins?: SpineSkinRecord[] | JsonObject;
  animations?: Record<string, SpineAnimation>;
  ik?: SpineConstraint[];
  transform?: SpineConstraint[];
  path?: SpineConstraint[];
}

export function isSpineDocument(value: unknown): value is SpineDocument {
  if (!value || typeof value !== 'object') return false;
  const raw = value as Record<string, unknown>;
  return Array.isArray(raw.bones) && raw.bones.every(bone => !!bone && typeof bone === 'object' && typeof (bone as Record<string, unknown>).name === 'string');
}
export function assertSpineDocument(value: unknown): asserts value is SpineDocument {
  if (!isSpineDocument(value)) throw new Error('Invalid Spine document: bones[] with stable names is required.');
}
export function cloneSpineDocument<T extends SpineDocument>(document: T): T {
  return (typeof structuredClone === 'function' ? structuredClone(document) : JSON.parse(JSON.stringify(document))) as T;
}
