import type { EditorCapability, ModeMachine } from './modeMachine.ts';
import { applyPatchSet, type PatchSet } from './patchSet.ts';

export interface Command<TPayload = unknown> { type: string; payload: TPayload; }
export interface CommandContext { mode: ModeMachine; [key: string]: unknown; }
export interface CommandDefinition<TDocument = unknown, TPayload = unknown> {
  capability: EditorCapability;
  createPatch(document: TDocument, payload: TPayload, context: CommandContext): PatchSet;
}
export interface CommandDispatchResult<TDocument> { document: TDocument; patch: PatchSet; inverse: PatchSet; metadata?: Record<string,unknown>; }
export type DocumentValidator<TDocument> = (document: TDocument, context: CommandContext) => void;

export class CommandBus<TDocument = unknown> {
  #handlers = new Map<string, CommandDefinition<TDocument, any>>();
  #validators: DocumentValidator<TDocument>[] = [];
  register<TPayload>(type: string, definition: CommandDefinition<TDocument, TPayload>): this { if(this.#handlers.has(type))throw new Error(`Command already registered: ${type}`);this.#handlers.set(type,definition);return this; }
  validateWith(validator: DocumentValidator<TDocument>): this { this.#validators.push(validator);return this; }
  dispatch<TPayload>(document: TDocument, command: Command<TPayload>, context: CommandContext): CommandDispatchResult<TDocument> {
    const definition=this.#handlers.get(command.type);if(!definition)throw new Error(`Unknown command: ${command.type}`);context.mode.require(definition.capability);
    const patch=definition.createPatch(document,command.payload,context),applied=applyPatchSet(document,patch);for(const validator of this.#validators)validator(applied.document,context);
    return {document:applied.document,patch,inverse:applied.inverse,...(patch.metadata?{metadata:patch.metadata}:{})};
  }
}
