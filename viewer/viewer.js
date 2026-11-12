/* spine2d-master native viewer + QA adapter.
 * Renders with the official Spine WebGL 4.2 runtime (vendored, offline).
 * One file serves three uses: human preview, headless capture (window.spk), single-file export.
 *
 * Config: window.SPK_CONFIG or URL params
 *   json, atlas        asset paths (relative to page) -- required
 *   contract           optional controller contract (*.contract.json)
 *   raw                {path: dataURI} for embedded single-file exports
 *   ui=0               hide the human controls (capture mode)
 *   bg=#rrggbb|transparent
 */
(function () {
  'use strict';
  const S = window.spine;
  const params = new URLSearchParams(location.search);
  const cfg = Object.assign({ json: null, atlas: null, contract: null, raw: null, ui: true, bg: '#1b2430' }, window.SPK_CONFIG || {});
  for (const k of ['json', 'atlas', 'contract', 'bg']) if (params.get(k)) cfg[k] = params.get(k);
  if (params.get('ui') === '0') cfg.ui = false;

  const $ = (sel) => document.querySelector(sel);
  const canvas = $('#stage');
  const api = (window.spk = { ready: false, error: null });

  function fail(e) {
    api.error = String(e && e.stack ? e.stack : e);
    const el = $('#status');
    if (el) el.textContent = 'ERROR: ' + String(e);
    console.error(e);
  }

  function hexToRgb(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    if (!m) return null;
    const n = parseInt(m[1], 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  }

  async function boot() {
    if (!S) throw new Error('Spine runtime not loaded');
    if (!cfg.json || !cfg.atlas) throw new Error('Missing json/atlas (use ?json=...&atlas=...)');
    const ctx = new S.ManagedWebGLRenderingContext(canvas, { alpha: true, premultipliedAlpha: true, preserveDrawingBuffer: true, antialias: true });
    const gl = ctx.gl;
    const renderer = new S.SceneRenderer(canvas, ctx, true);
    const assets = new S.AssetManager(ctx, '');
    if (cfg.raw) for (const k of Object.keys(cfg.raw)) assets.setRawDataURI(k, cfg.raw[k]);
    assets.loadText(cfg.json);
    assets.loadText(cfg.atlas);
    if (cfg.contract) assets.loadText(cfg.contract);
    await assets.loadAll();
    if (assets.hasErrors()) throw new Error('Asset load failed: ' + JSON.stringify(assets.getErrors()));
    // Embedded (base64) text comes back from the runtime's downloader as Latin-1; restore UTF-8 so non-ASCII names survive.
    const text = (key) => {
      const v = assets.require(key);
      if (!(cfg.raw && cfg.raw[key])) return v;
      try { return new TextDecoder('utf-8', { fatal: true }).decode(Uint8Array.from(v, (ch) => ch.charCodeAt(0))); } catch (e) { return v; }
    };
    const atlas = new S.TextureAtlas(text(cfg.atlas));
    const base = cfg.atlas.includes('/') ? cfg.atlas.slice(0, cfg.atlas.lastIndexOf('/') + 1) : '';
    // Bind through the success callback: for embedded data URIs the runtime files the texture under the URI, not the name.
    for (const page of atlas.pages) assets.loadTexture(base + page.name, (_, texture) => page.setTexture(texture));
    await assets.loadAll();
    if (assets.hasErrors()) throw new Error('Texture load failed: ' + JSON.stringify(assets.getErrors()));
    for (const page of atlas.pages) if (!page.texture) throw new Error('Atlas page not loaded: ' + page.name);
    const pma = !!(atlas.pages[0] && atlas.pages[0].pma);
    const rawJson = JSON.parse(text(cfg.json));
    const data = new S.SkeletonJson(new S.AtlasAttachmentLoader(atlas)).readSkeletonData(rawJson);
    let contract = {};
    if (cfg.contract) { try { contract = JSON.parse(text(cfg.contract)); } catch (e) { console.warn('contract parse failed', e); } }
    const animMeta = contract.animations || {};
    const defaultMix = contract.mix && contract.mix.default != null ? contract.mix.default : 0.2;

    const skeleton = new S.Skeleton(data);
    skeleton.setToSetupPose();
    skeleton.updateWorldTransform(S.Physics.reset);
    const stateData = new S.AnimationStateData(data);
    stateData.defaultMix = defaultMix;
    if (contract.mix && contract.mix.pairs) for (const p of contract.mix.pairs) if (data.findAnimation(p[0]) && data.findAnimation(p[1])) stateData.setMix(p[0], p[1], p[2]);
    // contract.mix.attachmentThreshold (opt-in): keep the outgoing clip's attachments (e.g. fists) for that fraction of a blend
    const attThr = contract.mix && contract.mix.attachmentThreshold != null ? contract.mix.attachmentThreshold : null;
    const withThreshold = (st) => { if (attThr != null) st.addListener({ start: (e) => { e.mixAttachmentThreshold = attThr; } }); return st; };
    let state = withThreshold(new S.AnimationState(stateData));

    // ---------------------------------------------------------------- view
    const setupBounds = (() => { const o = new S.Vector2(), s = new S.Vector2(); skeleton.getBounds(o, s, []); return { x: o.x, y: o.y, width: s.x, height: s.y }; })();
    const dataFrame = data.width > 0 && data.height > 0 ? { x: data.x, y: data.y, width: data.width, height: data.height } : setupBounds;
    const view = { frame: contract.frame || dataFrame, bg: (cfg.ui && !params.get('bg') && contract.background) || cfg.bg, bones: false, mesh: false, pad: 0 };
    if (cfg.ui) document.body.dataset.bg = view.bg;
    const dbg = renderer.skeletonDebugRenderer;
    dbg.drawRegionAttachments = false; dbg.drawBoundingBoxes = false; dbg.drawPaths = false; dbg.drawClipping = false; dbg.drawSkeletonXY = false;

    function fitCanvas() {
      const dpr = cfg.ui ? Math.min(window.devicePixelRatio || 1, 2) : 1;
      const w = Math.max(2, Math.round(canvas.clientWidth * dpr)), h = Math.max(2, Math.round(canvas.clientHeight * dpr));
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    }
    function render() {
      fitCanvas();
      const portrait = cfg.ui && !view.custom && canvas.height > canvas.width * 1.15 && contract.frame_portrait;
      const f = portrait ? contract.frame_portrait : view.frame, cam = renderer.camera;
      gl.viewport(0, 0, canvas.width, canvas.height);
      cam.setViewport(canvas.width, canvas.height);
      cam.zoom = Math.max((f.width + view.pad * 2) / canvas.width, (f.height + view.pad * 2) / canvas.height);
      cam.position.set(f.x + f.width / 2, f.y + f.height / 2, 0);
      const rgb = hexToRgb(view.bg);
      if (rgb) gl.clearColor(rgb[0], rgb[1], rgb[2], 1); else gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      renderer.begin();
      renderer.drawSkeleton(skeleton, pma);
      if (view.bones || view.mesh) {
        dbg.drawBones = view.bones; dbg.drawMeshHull = view.mesh; dbg.drawMeshTriangles = view.mesh;
        renderer.drawSkeletonDebug(skeleton, pma);
      }
      renderer.end();
    }

    // ---------------------------------------------------------- controllers
    // contract.controllers.<name> = {bone, unit, kind:"translate"}: a normalized [-1,1] 2D input moves a bone.
    const controllers = {};
    for (const [name, c] of Object.entries(contract.controllers || {})) {
      const bone = skeleton.findBone(c.bone);
      if (bone) controllers[name] = { def: c, bone, value: [0, 0], target: [0, 0] };
    }
    function applyControllers(dt) {
      for (const c of Object.values(controllers)) {
        const k = dt == null ? 1 : 1 - Math.exp(-dt * (c.def.speed || 9));
        c.value[0] += (c.target[0] - c.value[0]) * k; c.value[1] += (c.target[1] - c.value[1]) * k;
        const u = c.def.unit || 1;
        c.bone.x += c.value[0] * u; c.bone.y += c.value[1] * u;
      }
    }
    function applyPose(pose) {
      // pose = {boneName: {rot, x, y, sx, sy}} -- additive on top of the current local pose (rot/x/y), multiplicative scale.
      for (const [name, p] of Object.entries(pose || {})) {
        const b = skeleton.findBone(name);
        if (!b) throw new Error('pose: unknown bone ' + name);
        if (p.rot) b.rotation += p.rot;
        if (p.x) b.x += p.x;
        if (p.y) b.y += p.y;
        if (p.sx != null) b.scaleX *= p.sx;
        if (p.sy != null) b.scaleY *= p.sy;
      }
    }
    function applySlots(slots) {
      // slots = {slotName: attachmentName|null}
      for (const [name, att] of Object.entries(slots || {})) {
        const s = skeleton.findSlot(name);
        if (!s) throw new Error('slots: unknown slot ' + name);
        s.setAttachment(att ? skeleton.getAttachment(s.data.index, att) : null);
      }
    }

    // ------------------------------------------------------------ playback
    let mode = 'live', speed = 1, physicsOn = (contract.physics !== false) && data.physicsConstraints.length > 0;
    let firedEvents = [];
    // contract.events.<name>.action === 'toggle_facing': the animation asks the controller to mirror the skeleton
    // (facing is controller state -- skeleton.scaleX -- not something a clip can own).
    let physicsResetPending = false;
    const eventActions = contract.events || {};
    // Facing.  mode "flip": the skeleton is mirrored (skeleton.scaleX).  mode "clips": the body is asymmetric and must not
    // be mirrored, so every clip exists twice (name and name + suffix) and the controller picks by facing.
    const facingMode = (contract.facing && contract.facing.mode) || 'flip';
    const suffix = (contract.facing && contract.facing.suffix) || '_L';
    let facing = 1;
    const facingSign = () => (facingMode === 'clips' ? facing : Math.sign(skeleton.scaleX));
    const variant = (name, f) => (facingMode === 'clips' && f < 0 && data.findAnimation(name + suffix) ? name + suffix : name);
    const baseName = (name) => (facingMode === 'clips' && name.endsWith(suffix) && animMeta[name] && animMeta[name].alias ? animMeta[name].alias : name);
    // Live parameters (contract.parameters): each is a clip whose time means "value".  It is held on its own track at the
    // time for the current value with additive blending, so it lays over whatever plays on track 0.
    var lives = (contract.parameters || []).map((q) => Object.assign({ value: q.default, target: q.default }, q));
    var P = Object.fromEntries(lives.map((q) => [q.id, q]));
    function applyParams(st, dt) {
      for (const q of lives) {
        if (dt != null) q.value += (q.target - q.value) * Math.min(1, dt * (q.id === 'Blink' ? 60 : 14)); else q.value = q.target;
        const anim = data.findAnimation(q.clip); if (!anim) continue;
        let e = st.getCurrent(q.track);
        if (!e || e.animation !== anim) { e = st.setAnimation(q.track, q.clip, false); e.mixDuration = 0; e.timeScale = 0; e.mixBlend = S.MixBlend.add; e.alpha = 1; }
        e.trackTime = anim.duration * Math.max(0, Math.min(1, (q.value - q.min) / (q.max - q.min)));
      }
    }
    // What drives the parameters in the live preview: the pointer, an idle wander, automatic blinks, a talking mouth, a set expression.
    var drive = { follow: false, auto: lives.length > 0, talk: false, expr: null, blinkAt: 2, blinkT: -1, px: 0, py: 0, t: 0 };
    function driveParams(dt) {
      if (!lives.length) return;
      drive.t += dt; const t = drive.t;
      const set = (id, val) => { if (P[id]) P[id].target = Math.max(P[id].min, Math.min(P[id].max, val)); };
      if (drive.follow) { set('AngleX', drive.px * 30); set('AngleY', drive.py * 20); set('AngleZ', drive.px * -6); set('BodyAngleX', drive.px * 9); set('EyeBallX', drive.px); set('EyeBallY', drive.py); }
      else if (drive.auto) { set('AngleX', 13 * Math.sin(0.6 * t) + 6 * Math.sin(1.7 * t + 1)); set('AngleY', 6 * Math.sin(0.9 * t + 2)); set('AngleZ', 5 * Math.sin(0.5 * t)); set('BodyAngleX', 5 * Math.sin(0.4 * t)); set('BodyAngleZ', 3 * Math.sin(0.33 * t + 1)); set('EyeBallX', 0.35 * Math.sin(1.1 * t)); set('EyeBallY', 0.2 * Math.sin(0.7 * t + 1)); }
      else { for (const id of ['AngleX', 'AngleY', 'AngleZ', 'BodyAngleX', 'BodyAngleZ', 'EyeBallX', 'EyeBallY']) set(id, 0); }
      drive.blinkAt -= dt;
      if (drive.blinkAt <= 0) { drive.blinkT = 0; drive.blinkAt = 2 + Math.random() * 3; }
      if (drive.blinkT >= 0) { drive.blinkT += dt; const u = drive.blinkT / 0.17; set('Blink', u < 1 ? Math.sin(Math.PI * u) : 0); if (u >= 1) drive.blinkT = -1; }
      const mouth = drive.talk ? Math.abs(Math.sin(7.3 * t) * Math.sin(2.3 * t + 1)) * (0.6 + 0.4 * Math.sin(0.9 * t)) * 1.3 : 0;
      const ex = { smile: { Smile: 1, Cheek: 0.8, BrowY: 0.4 }, surprise: { BrowY: 1, MouthOpen: 0.9 }, angry: { BrowY: -1 } }[drive.expr] || {};
      set('Smile', ex.Smile || 0); set('Cheek', ex.Cheek || 0); set('BrowY', ex.BrowY || 0); set('MouthOpen', Math.max(mouth, ex.MouthOpen || 0));
    }
    function listen(st) {
      st.addListener({ event: (entry, ev) => {
        firedEvents.push({ name: ev.data.name, animation: entry.animation.name, trackTime: entry.trackTime });
        const act = eventActions[ev.data.name];
        if (act && act.action === 'toggle_facing') { if (facingMode === 'clips') facing = -facing; else { skeleton.scaleX *= -1; physicsResetPending = true; } }
      } });
    }
    // animations.<name>.speed (px/s): the clip is authored in place; the controller moves the skeleton.
    function locomote(dt) {
      const e = state.getCurrent(0);
      if (!e || !e.animation) return;
      const m = animMeta[e.animation.name];
      if (m && m.speed) skeleton.x += m.speed * dt * (m.facing === 'left' ? -1 : facingSign()) * (e.mixDuration > 0 ? Math.min(1, e.mixTime / e.mixDuration) : 1);
    }
    listen(state);
    function trackSnapshot(st) {
      const out = [];
      for (let i = 0; i < st.tracks.length; i++) {
        const e = st.tracks[i];
        if (!e) continue;
        out.push({ track: i, animation: e.animation.name, trackTime: e.trackTime, animationTime: e.getAnimationTime(), duration: e.animation.duration, loop: e.loop, mixTime: e.mixTime, mixDuration: e.mixDuration, mixingFrom: e.mixingFrom ? e.mixingFrom.animation.name : null });
      }
      return out;
    }
    function snapshot(extra) {
      return Object.assign({ mode, frozen: mode !== 'live', tracks: trackSnapshot(state), events: firedEvents.slice(), physics: physicsOn, facing: facingSign(), x: skeleton.x, renderer: 'spine-webgl-4.2.119', canvas: [canvas.width, canvas.height], frame: view.frame }, extra || {});
    }
    function tick(dt, physics) {
      driveParams(dt); applyParams(state, dt);
      state.update(dt);
      state.apply(skeleton);
      locomote(dt);
      patrol();
      applyControllers(dt);
      skeleton.update(dt);
      skeleton.updateWorldTransform(physicsResetPending && physics !== S.Physics.none ? S.Physics.reset : physics);
      physicsResetPending = false;
    }
    // contract.patrol = {walk, turn, min, max}: walk to an edge, turn, walk back (live demo of locomotion + facing).
    let patrolOn = false;
    function patrol() {
      const p = contract.patrol;
      if (!patrolOn || !p) return;
      const e = state.getCurrent(0);
      if (!e || !e.animation) return;
      const dir = facingSign();
      if (baseName(e.animation.name) !== p.walk) return;
      const b = (canvas.height > canvas.width * 1.15 && p.portrait) ? p.portrait : p;
      if ((dir > 0 && skeleton.x > b.max) || (dir < 0 && skeleton.x < b.min)) { state.setAnimation(0, variant(p.turn, dir), false); state.addAnimation(0, variant(p.walk, -dir), true, 0); }
    }

    // live loop (human preview)
    let last = performance.now(), blinkTimer = 2;
    function frame(now) {
      const dt = Math.min((now - last) / 1000, 0.1) * speed; last = now;
      if (mode === 'live') {
        autoOverlay(dt);
        tick(dt, physicsOn ? S.Physics.update : S.Physics.none);
        wrapLive();
        render();
      }
      requestAnimationFrame(frame);
    }
    // live preview only: a locomotion clip that leaves the camera frame re-enters from the other side
    function wrapLive() {
      const lim = dataFrame.width * 0.75;
      if (Math.abs(skeleton.x) > lim) { skeleton.x = -Math.sign(skeleton.x) * lim; physicsResetPending = true; }
      const e0 = state.getCurrent(0), m0 = e0 && e0.animation ? animMeta[e0.animation.name] : null;
      if (!(m0 && m0.speed) && !(e0 && e0.mixingFrom) && Math.abs(skeleton.x) > dataFrame.width * 0.3) { skeleton.x = 0; physicsResetPending = true; }
    }
    function autoOverlay(dt) {
      for (const [name, m] of Object.entries(animMeta)) {
        if (!m.auto || !ui.auto[name] || !data.findAnimation(name)) continue;
        m._t = (m._t == null ? m.auto.min : m._t) - dt;
        if (m._t <= 0) { const tr = m.track || 1; state.setEmptyAnimation(tr, 0); const e = state.addAnimation(tr, name, false, 0); e.mixDuration = 0.04; state.addEmptyAnimation(tr, 0.1, 0); m._t = m.auto.min + Math.random() * (m.auto.max - m.auto.min); }
      }
    }
    const ui = { auto: {} };
    for (const [name, m] of Object.entries(animMeta)) if (m.auto) ui.auto[name] = true;

    function playLive(name) {
      const m = animMeta[name] || {};
      if (!data.findAnimation(name)) throw new Error('Unknown animation ' + name);
      mode = 'live';
      const track = m.track || 0;
      if (m.role === 'overlay') {
        const cur = state.getCurrent(track);
        if (cur && cur.animation && cur.animation.name === name && (m.loop || m.hold)) { state.setEmptyAnimation(track, defaultMix); return 'off'; }
        if (!cur) state.setEmptyAnimation(track, 0);
        const e = state.addAnimation(track, name, !!m.loop, 0);
        e.mixDuration = m.mixIn != null ? m.mixIn : defaultMix;
        if (!m.loop && !m.hold) state.addEmptyAnimation(track, m.mixOut != null ? m.mixOut : defaultMix, 0);
        return 'on';
      }
      const loop = m.loop != null ? m.loop : true;
      const f = facingSign();
      state.setAnimation(track, variant(name, f), loop);
      if (!loop) state.addAnimation(track, variant(m.return || home, m.turns ? -f : f), true, 0);     // a turn ends facing the other way
      return 'on';
    }
    const home = contract.home || (data.findAnimation('idle') ? 'idle' : (data.animations[0] && data.animations[0].name));

    // ------------------------------------------------------- QA: frozen seek
    function resetAll() {
      firedEvents = [];
      state.clearListeners();
      state = withThreshold(new S.AnimationState(stateData));
      listen(state);
      skeleton.setToSetupPose();
      skeleton.scaleX = 1; skeleton.x = 0; physicsResetPending = false; facing = 1;
      for (const q of (lives || [])) { q.value = q.target = q.default; }       // (resetAll also runs once before the parameters are set up)
      for (const c of Object.values(controllers)) { c.value = [0, 0]; c.target = [0, 0]; }
    }
    /* seek({tracks:[{track,anim,time,loop}], physics:'none'|'simulate', preroll, dt, pose, slots, look:{name:[x,y]}})
     * Frozen, deterministic pose. physics:'simulate' steps real time from (time - span) so physics constraints settle. */
    api._debug = () => ({ skeleton, state, S });      // for tests: reach into the live skeleton
    api.seek = function (o) {
      o = o || {};
      mode = 'frozen';
      resetAll();
      const tracks = o.tracks || [];
      if (o.facing) skeleton.scaleX = o.facing < 0 ? -1 : 1;
      if (o.x) skeleton.x = o.x;
      for (const [name, v] of Object.entries(o.look || {})) if (controllers[name]) { controllers[name].value = v.slice(); controllers[name].target = v.slice(); }
      for (const q of lives) q.target = q.value = (o.params && o.params[q.id] != null) ? o.params[q.id] : q.default;
      applyParams(state, null);
      const simulate = o.physics === 'simulate' && data.physicsConstraints.length > 0;
      if (!simulate) {
        for (const t of tracks) {
          if (!data.findAnimation(t.anim)) throw new Error('Unknown animation ' + t.anim);
          const e = state.setAnimation(t.track || 0, t.anim, !!t.loop);
          e.mixDuration = 0; e.trackTime = t.time || 0;
        }
        state.apply(skeleton);
        applyControllers(null);
        applyPose(o.pose); applySlots(o.slots);
        skeleton.updateWorldTransform(S.Physics.none);
      } else {
        const dt = o.dt || 1 / 60;
        const maxT = Math.max(0, ...tracks.map((t) => t.time || 0));
        const span = maxT + (o.preroll != null ? o.preroll : 1.0);
        const steps = Math.max(1, Math.round(span / dt));
        for (const t of tracks) {
          if (!data.findAnimation(t.anim)) throw new Error('Unknown animation ' + t.anim);
          const anim = data.findAnimation(t.anim);
          const e = state.setAnimation(t.track || 0, t.anim, !!t.loop);
          e.mixDuration = 0;
          let start = (t.time || 0) - steps * dt;
          if (t.loop && anim.duration > 0) { start = ((start % anim.duration) + anim.duration) % anim.duration; e.trackTime = start; }
          else { e.trackTime = 0; e.delay = Math.max(0, -start); if (start > 0) e.trackTime = start; }
        }
        state.apply(skeleton); applyControllers(null); applyPose(o.pose); applySlots(o.slots);
        skeleton.updateWorldTransform(S.Physics.reset);
        for (let i = 0; i < steps; i++) {
          state.update(dt); state.apply(skeleton); applyControllers(null); applyPose(o.pose); applySlots(o.slots);
          skeleton.update(dt); skeleton.updateWorldTransform(S.Physics.update);
        }
      }
      render();
      return snapshot({ requested: o });
    };

    /* Deterministic real playback (true AnimationState mixing/queue/events, fixed dt):
     *   begin({cues:[{at, track, anim, loop, mix, empty}], physics:true|false, look:{name:[[t,x,y],...]}})
     *   advance(dt) -> snapshot   (renders one frame)                                              */
    let script = null;
    api.begin = function (o) {
      mode = 'script';
      resetAll();
      skeleton.x = o.startX || 0;
      if (o.facing) { if (facingMode === 'clips') facing = o.facing < 0 ? -1 : 1; else skeleton.scaleX = o.facing < 0 ? -1 : 1; }
      script = { clock: 0, cues: (o.cues || []).slice().sort((a, b) => a.at - b.at), i: 0, physics: o.physics !== false && data.physicsConstraints.length > 0, look: o.look || {}, first: true };
      return api.advance(0);
    };
    function lookAt(keys, t) {
      if (!keys.length) return [0, 0];
      if (t <= keys[0][0]) return [keys[0][1], keys[0][2]];
      for (let i = 1; i < keys.length; i++) if (t <= keys[i][0]) { const a = keys[i - 1], b = keys[i], u = (t - a[0]) / Math.max(1e-6, b[0] - a[0]), s = u * u * (3 - 2 * u); return [a[1] + (b[1] - a[1]) * s, a[2] + (b[2] - a[2]) * s]; }
      const l = keys[keys.length - 1]; return [l[1], l[2]];
    }
    api.advance = function (dt) {
      if (!script) throw new Error('call begin() first');
      script.clock += dt;
      applyParams(state, dt || null);
      state.update(dt);
      // A cue at time T starts its animation at trackTime 0 on the frame whose clock == T.
      while (script.i < script.cues.length && script.cues[script.i].at <= script.clock + 1e-9) {
        const c = script.cues[script.i++], track = c.track || 0;
        let e;
        if (c.empty) e = state.setEmptyAnimation(track, c.mix != null ? c.mix : defaultMix);
        else { if (!data.findAnimation(c.anim)) throw new Error('Unknown animation ' + c.anim); e = state.setAnimation(track, c.anim, !!c.loop); if (c.mix != null) e.mixDuration = c.mix; }
      }
      for (const [name, keys] of Object.entries(script.look)) if (controllers[name]) controllers[name].target = lookAt(keys, script.clock);
      state.apply(skeleton); locomote(dt); applyControllers(dt || null);
      skeleton.update(dt);
      skeleton.updateWorldTransform(script.physics ? (script.first || physicsResetPending ? S.Physics.reset : S.Physics.update) : S.Physics.none);
      script.first = false; physicsResetPending = false;
      render();
      return snapshot({ clock: script.clock });
    };

    // ------------------------------------------------------------- QA misc
    api.info = () => ({
      version: data.version, runtime: 'spine-webgl-4.2.119', pma,
      bones: data.bones.map((b) => b.name), slots: data.slots.map((s) => s.name), skins: data.skins.map((s) => s.name),
      animations: data.animations.map((a) => ({ name: a.name, duration: a.duration })),
      constraints: { ik: data.ikConstraints.length, transform: data.transformConstraints.length, path: data.pathConstraints.length, physics: data.physicsConstraints.length },
      frame: view.frame, setupBounds, contract: Object.keys(contract).length ? contract : null,
    });
    api.view = (o) => { Object.assign(view, o || {}); render(); return Object.assign({}, view); };
    api.bounds = () => { const o = new S.Vector2(), s = new S.Vector2(); skeleton.getBounds(o, s, []); return { x: o.x, y: o.y, width: s.x, height: s.y }; };
    api.png = () => { render(); return canvas.toDataURL('image/png'); };
    api.snapshot = () => snapshot();
    api.play = (name) => { const r = playLive(name); if (ui.refresh) ui.refresh(); return r; };
    api.live = () => { mode = 'live'; last = performance.now(); };
    api.look = (name, x, y) => { if (controllers[name]) controllers[name].target = [x, y]; };
    api.bonesWorld = (names) => (names || data.bones.map((b) => b.name)).map((n) => { const b = skeleton.findBone(n); return { name: n, x: b.worldX, y: b.worldY, rot: b.getWorldRotationX() }; });

    // ---------------------------------------------------------- human UI
    if (cfg.ui) buildUi(); else document.body.classList.add('noui');
    function buildUi() {
      const bar = $('#controls');
      const mk = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text) el.textContent = text; return el; };
      const groups = { base: mk('div', 'row'), action: mk('div', 'row'), overlay: mk('div', 'row') };
      const buttons = {};
      for (const a of data.animations) {
        const m = animMeta[a.name] || {};
        if (m.hidden) continue;
        const role = m.role || (m.loop === false ? 'action' : 'base');
        const b = mk('button', 'chip ' + role, m.label || a.name);
        b.onclick = () => { api.play(a.name); };
        buttons[a.name] = b; (groups[role] || groups.base).append(b);
      }
      for (const [name, m] of Object.entries(animMeta)) if (m.auto && buttons[name]) {
        const t = mk('button', 'chip toggle on', '自動' + (m.label || name));
        t.onclick = () => { ui.auto[name] = !ui.auto[name]; t.classList.toggle('on', ui.auto[name]); };
        groups.overlay.append(t);
      }
      const tools = mk('div', 'row tools');
      const toggle = (label, get, set) => { const b = mk('button', 'chip toggle', label); b.classList.toggle('on', get()); b.onclick = () => { set(!get()); b.classList.toggle('on', get()); }; tools.append(b); return b; };
      if (lives.length) {
        toggle('跟隨手指', () => drive.follow, (val) => { drive.follow = val; });
        toggle('自動擺動', () => drive.auto, (val) => { drive.auto = val; });
        toggle('說話', () => drive.talk, (val) => { drive.talk = val; });
        const exs = [null, 'smile', 'surprise', 'angry'], exl = ['表情', '微笑', '驚訝', '生氣']; let ei = 0;
        const eb = mk('button', 'chip', exl[0]); eb.onclick = () => { ei = (ei + 1) % exs.length; drive.expr = exs[ei]; eb.textContent = exl[ei]; eb.classList.toggle('on', ei > 0); }; tools.append(eb);
      }
      if (contract.frames) {
        const names = Object.keys(contract.frames); let fi = 0;
        const fb = mk('button', 'chip', '鏡頭：' + names[0]); fb.onclick = () => { fi = (fi + 1) % names.length; view.frame = contract.frames[names[fi]]; view.custom = fi > 0; fb.textContent = '鏡頭：' + names[fi]; }; tools.append(fb);
      }
      if (contract.patrol) toggle('巡邏', () => patrolOn, (v) => { patrolOn = v; state.setAnimation(0, variant(v ? contract.patrol.walk : home, facingSign()), true); });
      if (Object.keys(controllers).length) toggle('視線跟隨', () => ui.follow, (v) => { ui.follow = v; if (!v) for (const c of Object.values(controllers)) c.target = [0, 0]; });
      if (data.physicsConstraints.length) toggle('物理', () => physicsOn, (v) => { physicsOn = v; });
      toggle('骨架', () => view.bones, (v) => { view.bones = v; });
      toggle('網格', () => view.mesh, (v) => { view.mesh = v; });
      const bgs = [view.bg, '#1b2430', '#e9edf2', '#3f6f5a', 'transparent'].filter((v, i, arr) => arr.indexOf(v) === i); let bi = 0;
      const bgBtn = mk('button', 'chip', '背景'); bgBtn.onclick = () => { bi = (bi + 1) % bgs.length; view.bg = bgs[bi]; document.body.dataset.bg = bgs[bi]; }; tools.append(bgBtn);
      const sp = mk('button', 'chip', '1×'); const speeds = [1, 0.5, 0.25, 2]; let si = 0;
      sp.onclick = () => { si = (si + 1) % speeds.length; speed = speeds[si]; sp.textContent = speeds[si] + '×'; }; tools.append(sp);
      for (const g of [groups.base, groups.action, groups.overlay, tools]) if (g.children.length) bar.append(g);
      ui.follow = Object.keys(controllers).length > 0 && contract.follow !== false;
      ui.refresh = () => {
        const cur = state.getCurrent(0);
        for (const [n, b] of Object.entries(buttons)) { const m = animMeta[n] || {}; const e = state.getCurrent(m.track || 0); b.classList.toggle('on', !!e && !!e.animation && baseName(e.animation.name) === n); }
        $('#status').textContent = cur ? cur.animation.name : '';
      };
      setInterval(ui.refresh, 200);
      const point = (ev) => {
        if (!ui.follow && !drive.follow) return;
        const r = canvas.getBoundingClientRect(), p = ev.touches ? ev.touches[0] : ev;
        if (!p) return;
        const x = ((p.clientX - r.left) / r.width) * 2 - 1, y = -(((p.clientY - r.top) / r.height) * 2 - 1);
        drive.px = Math.max(-1, Math.min(1, x * 1.5)); drive.py = Math.max(-1, Math.min(1, (y - 0.3) * 1.8));
        if (!ui.follow) return;
        const fx = x * facingSign();
        for (const c of Object.values(controllers)) if (!c.def.manual) c.target = [Math.max(-1, Math.min(1, fx * 1.4)), Math.max(-1, Math.min(1, (y - 0.25) * 1.6))];
      };
      canvas.addEventListener('pointermove', point); canvas.addEventListener('pointerdown', point);
      canvas.addEventListener('pointerleave', () => { for (const c of Object.values(controllers)) c.target = [0, 0]; });
      const title = $('#title'); if (title) title.textContent = (contract.title || contract.name || 'Spine') + ' · ' + data.bones.length + ' bones · ' + data.slots.length + ' slots · Spine ' + data.version;
    }

    if (home && data.findAnimation(home)) state.setAnimation(0, home, true);
    window.addEventListener('resize', () => { if (mode !== 'live') render(); });
    tick(0, S.Physics.reset); render();
    api.ready = true;
    requestAnimationFrame(frame);
  }

  boot().catch(fail);
})();
