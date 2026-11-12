const DEFAULT_KEY='zhuda-spine:editor-recovery:v1';

function clone(value){
  if(typeof structuredClone==='function')return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

export function createEditorRecovery({storage=globalThis.localStorage,key=DEFAULT_KEY,now=()=>Date.now(),delay=450}={}){
  let timer=null,pending=null,lastError=null;
  const readRaw=()=>{try{return storage?.getItem?.(key)||null}catch(error){lastError=error;return null}};
  const writeRaw=value=>{try{storage?.setItem?.(key,value);lastError=null;return true}catch(error){lastError=error;return false}};
  const removeRaw=()=>{try{storage?.removeItem?.(key);lastError=null;return true}catch(error){lastError=error;return false}};
  function load(projectKey=null){
    const raw=readRaw();if(!raw)return null;
    try{
      const parsed=JSON.parse(raw);
      if(parsed?.format!=='zhuda-editor-recovery'||parsed?.version!==1||!parsed.projectKey||!parsed.document)return null;
      if(projectKey&&parsed.projectKey!==projectKey)return null;
      return clone(parsed);
    }catch(error){lastError=error;return null;}
  }
  function save(payload){
    if(!payload?.projectKey||!payload?.document)throw new Error('Recovery save requires projectKey and document');
    const record={format:'zhuda-editor-recovery',version:1,projectKey:String(payload.projectKey),projectName:String(payload.projectName||''),savedAt:Number(payload.savedAt||now()),context:clone(payload.context||{}),document:clone(payload.document)};
    const ok=writeRaw(JSON.stringify(record));return ok?record:null;
  }
  function clear(projectKey=null){
    cancel();if(projectKey){const record=load();if(record&&record.projectKey!==projectKey)return false;}return removeRaw();
  }
  function cancel(){if(timer)clearTimeout(timer);timer=null;pending=null;}
  function flush(){
    if(timer)clearTimeout(timer);timer=null;const value=pending;pending=null;return value?save(value):null;
  }
  function schedule(payload,{wait=delay}={}){
    if(timer)clearTimeout(timer);pending=clone(payload);timer=setTimeout(()=>{timer=null;const value=pending;pending=null;if(value)save(value);},Math.max(0,Number(wait)||0));return true;
  }
  return {load,save,clear,cancel,flush,schedule,get lastError(){return lastError;},key};
}

export default createEditorRecovery;
