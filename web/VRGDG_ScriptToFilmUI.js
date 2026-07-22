import { api } from "../../scripts/api.js";

const STYLE_ID = "vrgdg-script-to-film-style";
const REQUIRED_FIELDS = [
  "character_bible",
  "physical_state_progression",
  "position_continuity_notes",
  "action_intensity_curve",
  "camera_language",
  "sound_design_prompt",
  "optional_music_bed_path",
  "ducking_level",
  "transition_ambience_notes",
];

function injectStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .vrgdg-film-backdrop { position:fixed; inset:0; z-index:100030; display:flex; align-items:center; justify-content:center; background:rgba(2,6,23,.76); }
    .vrgdg-film-modal { width:min(1440px,calc(100vw - 36px)); height:min(92vh,1120px); display:grid; grid-template-rows:auto minmax(0,1fr) auto; background:#0b1324; color:#e2e8f0; border:1px solid #0ea5e9; border-radius:12px; overflow:hidden; box-shadow:0 24px 90px rgba(0,0,0,.66); }
    .vrgdg-film-head, .vrgdg-film-foot { padding:14px 18px; border-bottom:1px solid #1e3a5f; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
    .vrgdg-film-foot { border-top:1px solid #1e3a5f; border-bottom:0; justify-content:space-between; }
    .vrgdg-film-title { font-size:20px; font-weight:900; color:#cffafe; }
    .vrgdg-film-subtitle { font-size:12px; color:#94a3b8; flex:1 1 360px; }
    .vrgdg-film-body { overflow:auto; padding:16px 18px 30px; display:grid; gap:16px; align-content:start; }
    .vrgdg-film-card { padding:14px; border:1px solid #1e3a5f; border-radius:9px; background:#0f1d32; }
    .vrgdg-film-card h3 { margin:0 0 8px; font-size:15px; color:#a5f3fc; }
    .vrgdg-film-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:10px; }
    .vrgdg-film-label { display:grid; gap:5px; font-size:12px; color:#cbd5e1; }
    .vrgdg-film-input, .vrgdg-film-textarea, .vrgdg-film-select { width:100%; box-sizing:border-box; border:1px solid #334155; border-radius:6px; background:#020617; color:#f8fafc; padding:8px; font:inherit; }
    .vrgdg-film-textarea { min-height:86px; resize:vertical; line-height:1.38; }
    .vrgdg-film-script { min-height:180px; }
    .vrgdg-film-actions { display:flex; gap:8px; flex-wrap:wrap; }
    .vrgdg-film-button { border:1px solid #0e7490; border-radius:7px; background:#0f766e; color:#ecfeff; padding:9px 12px; font-weight:800; cursor:pointer; }
    .vrgdg-film-button.secondary { border-color:#475569; background:#1e293b; color:#e2e8f0; }
    .vrgdg-film-button.danger { border-color:#be123c; background:#881337; }
    .vrgdg-film-button:disabled { opacity:.55; cursor:wait; }
    .vrgdg-film-scene { border:1px solid #334155; border-radius:8px; overflow:hidden; background:#08111f; }
    .vrgdg-film-scene summary { cursor:pointer; padding:10px 12px; color:#e0f2fe; font-weight:800; background:#11223a; }
    .vrgdg-film-scene-body { padding:12px; display:grid; gap:10px; }
    .vrgdg-film-note { font-size:12px; line-height:1.45; color:#94a3b8; }
    .vrgdg-film-status { font-size:12px; color:#67e8f9; }
  `;
  document.head.appendChild(style);
}

async function requestJson(path, method = "GET", payload = null) {
  const response = await api.fetchApi(path, payload == null ? { method } : {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data?.ok) throw new Error(String(data?.error || `Film request failed (${response.status})`));
  return data;
}

function errorMessage(error) {
  const name = String(error?.name || "").trim();
  const message = String(error?.message || error || "Unknown browser error").trim();
  return `${name && name !== "Error" ? `${name}: ` : ""}${message}`.slice(0, 2000);
}

async function reportClientError(stage, error) {
  const message = errorMessage(error);
  console.error(`[VRGDG Script-to-Film] ${stage}`, error);
  try {
    await api.fetchApi("/vrgdg/script_to_film/client_error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Never send the script or LLM response in diagnostic telemetry.
      body: JSON.stringify({ stage: String(stage || "unknown").slice(0, 160), message }),
    });
  } catch (reportingError) {
    console.warn("[VRGDG Script-to-Film] Could not report Planner client error", reportingError);
  }
  return message;
}

function ensureStableSceneIds(scenes) {
  const seen = new Set();
  return (Array.isArray(scenes) ? scenes : []).map((scene, index) => {
    const target = scene && typeof scene === "object" ? scene : {};
    const sceneNumber = Math.max(1, Number(target.scene_number || index + 1) || index + 1);
    const baseId = String(target.id || "").trim() || `film_scene_${String(sceneNumber).padStart(4, "0")}`;
    let sceneId = baseId;
    let duplicateNumber = 2;
    while (seen.has(sceneId)) {
      sceneId = `${baseId}_${duplicateNumber}`;
      duplicateNumber += 1;
    }
    target.id = sceneId;
    seen.add(sceneId);
    return target;
  });
}

function promptCreatorModelChoices(state) {
  const choices = [
    state?.scriptToFilm?.prompt_creator_model,
    state?.scriptToFilm?.last_prompt_creator_model,
    state?.textGemmaModel,
    ...(Array.isArray(state?.textGemmaModels) ? state.textGemmaModels : []),
  ].map((value) => String(value || "").trim()).filter(Boolean);
  return Array.from(new Set(choices));
}

function clone(value) {
  return JSON.parse(JSON.stringify(value || {}));
}

function framesForDuration(seconds, fps) {
  const raw = Math.max(9, Math.round(Number(seconds || 4) * Number(fps || 25)) + 1);
  return Math.max(9, Math.round((raw - 1) / 8) * 8 + 1);
}

function reflowLocally(scenes, fps) {
  let cursor = 0;
  for (const [index, scene] of scenes.entries()) {
    scene.scene_number = index + 1;
    scene.planned_frames = framesForDuration(scene.target_duration_seconds, fps);
    scene.target_duration_seconds = (scene.planned_frames - 1) / fps;
    const duration = Number(scene.actual_duration_seconds || scene.target_duration_seconds);
    scene.start = cursor;
    scene.end = cursor + duration;
    scene.timeline_duration_seconds = duration;
    cursor = scene.end;
  }
}

function field(label, value, onChange, options = {}) {
  const wrap = document.createElement("label");
  wrap.className = "vrgdg-film-label";
  wrap.textContent = label;
  const control = options.select ? document.createElement("select") : document.createElement(options.multiline ? "textarea" : "input");
  control.className = options.multiline ? "vrgdg-film-textarea" : (options.select ? "vrgdg-film-select" : "vrgdg-film-input");
  if (options.multiline) control.value = String(value || "");
  else if (!options.select) { control.type = options.type || "text"; control.value = value ?? ""; }
  if (options.select) {
    for (const choice of options.select) {
      const option = document.createElement("option");
      option.value = choice.value;
      option.textContent = choice.label;
      if (String(choice.value) === String(value)) option.selected = true;
      control.appendChild(option);
    }
  }
  control.addEventListener("input", () => onChange(control.type === "number" ? Number(control.value) : control.value));
  control.addEventListener("change", () => onChange(control.type === "number" ? Number(control.value) : control.value));
  wrap.appendChild(control);
  return wrap;
}

export function openScriptToFilmPlanner(config) {
  injectStyles();
  const state = clone(config.snapshot?.() || {});
  state.projectMode = "script_to_film";
  state.scriptToFilm = state.scriptToFilm || {};
  state.scriptToFilm.fps = Number(state.scriptToFilm.fps || 25);
  state.scriptToFilm.script = String(state.scriptToFilm.script || "");
  const promptCreatorModels = promptCreatorModelChoices(state);
  state.scriptToFilm.prompt_creator_model = String(
    state.scriptToFilm.prompt_creator_model
    || state.scriptToFilm.last_prompt_creator_model
    || state.textGemmaModel
    || promptCreatorModels[0]
    || "",
  ).trim();
  state.segments = Array.isArray(state.segments) ? state.segments : [];
  const backdrop = document.createElement("div");
  backdrop.className = "vrgdg-film-backdrop";
  const modal = document.createElement("section");
  modal.className = "vrgdg-film-modal";
  backdrop.appendChild(modal);
  const header = document.createElement("header");
  header.className = "vrgdg-film-head";
  const body = document.createElement("main");
  body.className = "vrgdg-film-body";
  const footer = document.createElement("footer");
  footer.className = "vrgdg-film-foot";
  modal.append(header, body, footer);
  const status = document.createElement("span");
  status.className = "vrgdg-film-status";
  const close = document.createElement("button");
  close.className = "vrgdg-film-button secondary";
  close.textContent = "Close";
  close.onclick = () => backdrop.remove();
  header.append(Object.assign(document.createElement("div"), { className: "vrgdg-film-title", textContent: "Script-to-Film Planner" }), Object.assign(document.createElement("div"), { className: "vrgdg-film-subtitle", textContent: "Duration-first T2I → LTX native-audio shots. This is a separate film pipeline; Music Video settings are not changed." }), status, close);

  const apply = (message = "Film plan ready.") => {
    if (typeof config.applyPlan !== "function") throw new Error("The Film Planner was opened without a Builder/Wizard handoff.");
    state.segments = ensureStableSceneIds(state.segments);
    reflowLocally(state.segments, state.scriptToFilm.fps);
    config.applyPlan({ project_mode: "script_to_film", fps: state.scriptToFilm.fps, script_to_film: state.scriptToFilm, scenes: state.segments });
    status.textContent = message;
  };
  const syncPlan = async () => {
    const plan = await requestJson("/vrgdg/script_to_film/plan", "POST", { fps: state.scriptToFilm.fps, scenes: state.segments });
    state.segments = ensureStableSceneIds(plan.scenes);
    apply(`Timeline reflowed: ${Number(plan.total_duration_seconds || 0).toFixed(2)} seconds.`);
  };
  const render = () => {
    body.replaceChildren();
    const source = document.createElement("section");
    source.className = "vrgdg-film-card";
    source.append(Object.assign(document.createElement("h3"), { textContent: "1. Film source and duration plan" }));
    const sourceGrid = document.createElement("div");
    sourceGrid.className = "vrgdg-film-grid";
    sourceGrid.append(
      field("Frame rate", state.scriptToFilm.fps, (value) => { state.scriptToFilm.fps = Math.max(1, Math.min(120, Number(value || 25))); apply("Frame rate updated; durations will snap on reflow."); }, { type: "number" }),
      field("Default shot duration (seconds)", state.scriptToFilm.default_target_duration_seconds || 4, (value) => { state.scriptToFilm.default_target_duration_seconds = Math.max(.1, Number(value || 4)); }, { type: "number" }),
      field("Film Prompt Creator model", state.scriptToFilm.prompt_creator_model, (value) => {
        state.scriptToFilm.prompt_creator_model = String(value || "").trim();
        apply(`Film Prompt Creator model set to ${state.scriptToFilm.prompt_creator_model || "none"}.`);
      }, { select: promptCreatorModels.map((model) => ({ value: model, label: model })) }),
      field("Keyframe image mode", "pony", () => {}, { select: [{ value: "pony", label: "Pony (VioletsT2I)" }] }),
      field("LTX profile", "film_t2av_character_ref", () => {}, { select: [{ value: "film_t2av_character_ref", label: "Film/T2AV + Character Ref" }] }),
    );
    const script = field("Script", state.scriptToFilm.script, (value) => { state.scriptToFilm.script = value; }, { multiline: true });
    script.querySelector("textarea").classList.add("vrgdg-film-script");
    const actions = document.createElement("div");
    actions.className = "vrgdg-film-actions";
    const create = Object.assign(document.createElement("button"), { className: "vrgdg-film-button", textContent: "Create structured film scenes" });
    create.onclick = async () => {
      try {
        create.disabled = true;
        const selectedModel = String(state.scriptToFilm.prompt_creator_model || state.textGemmaModel || "").trim();
        if (!selectedModel && !["lm_studio", "llm_api"].includes(String(state.text_gemma_runner || "builtin"))) {
          throw new Error("Choose a Film Prompt Creator model before creating Film scenes.");
        }
        status.textContent = `The selected Film Prompt Creator model is planning Film scenes: ${selectedModel || state.text_gemma_runner}…`;
        const plan = await requestJson("/vrgdg/script_to_film/create_prompt_plan", "POST", {
          script: state.scriptToFilm.script,
          fps: state.scriptToFilm.fps,
          model_file: selectedModel,
          llm_settings: state.llmSettings || {},
          text_gemma_runner: state.text_gemma_runner || "builtin",
          lm_studio_base_url: state.lm_studio_base_url || "",
          lm_studio_model: state.lm_studio_model || "",
          lm_studio_api_key: state.lm_studio_api_key || "",
          llm_api_provider: state.llm_api_provider || "",
          llm_api_model: state.llm_api_model || "",
        });
        if (!Array.isArray(plan?.scenes) || !plan.scenes.length) throw new Error("The Prompt Creator returned no Film scenes.");
        state.segments = ensureStableSceneIds(plan.scenes);
        state.scriptToFilm.last_prompt_creator_model = plan.used_model || selectedModel;
        state.scriptToFilm.system_prompt_path = plan.system_prompt_path || "";
        const recovery = String(plan.recovery_message || "").trim();
        try {
          apply(`Created ${plan.scenes.length} duration-snapped Film shots with ${plan.used_model || "the selected model"}.${recovery ? ` ${recovery}` : ""}`);
          render();
        } catch (handoffError) {
          const detail = await reportClientError("applying generated Film plan", handoffError);
          status.textContent = `Film scenes were created, but the Builder/Wizard handoff failed: ${detail}`;
        }
      } catch (error) {
        const detail = await reportClientError("creating Film scenes", error);
        status.textContent = `Prompt Creator error: ${detail}`;
      } finally { create.disabled = false; }
    };
    const reflow = Object.assign(document.createElement("button"), { className: "vrgdg-film-button secondary", textContent: "Reflow durations" });
    reflow.onclick = async () => {
      try { await syncPlan(); render(); }
      catch (error) {
        const detail = await reportClientError("reflowing Film scenes", error);
        status.textContent = `Film reflow error: ${detail}`;
      }
    };
    actions.append(create, reflow);
    source.append(sourceGrid, script, actions, Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: "Target duration is authoritative. It snaps to LTX’s valid (frames − 1) % 8 = 0 frame rule. Rendered media duration replaces the target duration and shifts every following scene automatically." }));
    body.append(source);

    const scenesCard = document.createElement("section");
    scenesCard.className = "vrgdg-film-card";
    scenesCard.append(Object.assign(document.createElement("h3"), { textContent: `2. Film scenes (${state.segments.length})` }), Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: "Use Pure T2AV for unconditioned establishing shots. Use I2V/T2AV + Character Ref for Pony keyframes or character locking. The selected Violets LTX FP8 profile supplies DMD 1.0, JoyAI 0.5, and the shared Audio Text Encoder / sampler controls." }));
    for (const [index, scene] of state.segments.entries()) {
      const details = document.createElement("details");
      details.className = "vrgdg-film-scene";
      if (index === 0) details.open = true;
      const title = scene.label || `Film shot ${index + 1}`;
      details.append(Object.assign(document.createElement("summary"), { textContent: `${index + 1}. ${title} · ${Number(scene.target_duration_seconds || 0).toFixed(2)}s · ${scene.planned_frames || framesForDuration(scene.target_duration_seconds, state.scriptToFilm.fps)} frames` }));
      const sceneBody = document.createElement("div");
      sceneBody.className = "vrgdg-film-scene-body";
      const core = document.createElement("div"); core.className = "vrgdg-film-grid";
      core.append(
        field("Shot label", scene.label, (value) => { scene.label = value; apply(); }, {}),
        field("Target duration (seconds)", scene.target_duration_seconds, (value) => { scene.target_duration_seconds = Math.max(.1, Number(value || 4)); scene.actual_duration_seconds = 0; apply("Duration changed; LTX frame count snapped."); render(); }, { type: "number" }),
        field("Render mode", scene.film_render_mode || "i2v_t2av", (value) => { scene.film_render_mode = value; apply(); }, { select: [{ value: "i2v_t2av", label: "I2V/T2AV + Character Ref" }, { value: "t2av", label: "Pure T2AV establishing shot" }] }),
        field("Character / Pony keyframe image", scene.character_reference_path || scene.ref_image_path || "", (value) => { scene.character_reference_path = value; scene.ref_image_path = value; apply(); }),
        field("Transition cut", scene.transition_cut_type || "auto", (value) => { scene.transition_cut_type = value; apply(); }, { select: [{ value: "auto", label: "Carry ambience when requested" }, { value: "hard_cut", label: "Hard cut: no ambience overlap" }] }),
        field("Ambience overlap (seconds)", scene.transition_overlap_seconds ?? .25, (value) => { scene.transition_overlap_seconds = Math.max(0, Math.min(2, Number(value || 0))); apply(); }, { type: "number" }),
      );
      sceneBody.append(core);
      const prompts = document.createElement("div"); prompts.className = "vrgdg-film-grid";
      prompts.append(
        field("Pony keyframe prompt", scene.t2i_prompt, (value) => { scene.t2i_prompt = value; apply(); }, { multiline: true }),
        field("Unified natural-language LTX visual + audio prompt", scene.unified_ltx_prompt || scene.i2v_prompt, (value) => { scene.unified_ltx_prompt = value; scene.i2v_prompt = value; apply(); }, { multiline: true }),
        field("Dialogue / spoken content", scene.dialogue, (value) => { scene.dialogue = value; apply(); }, { multiline: true }),
      );
      sceneBody.append(prompts);
      const continuity = document.createElement("div"); continuity.className = "vrgdg-film-grid";
      for (const name of REQUIRED_FIELDS) {
        const label = name.replaceAll("_", " ");
        const structured = name === "character_bible" || name === "action_intensity_curve";
        const displayed = structured ? JSON.stringify(scene[name] || {}, null, 2) : scene[name];
        continuity.append(field(label, displayed, (value) => {
          if (structured) {
            try { scene[name] = JSON.parse(String(value || "{}")); }
            catch { status.textContent = `${label} must be valid JSON; the previous structured value is still retained.`; return; }
          } else scene[name] = value;
          apply();
        }, { multiline: name !== "ducking_level", type: name === "ducking_level" ? "number" : "text" }));
      }
      sceneBody.append(continuity);
      details.append(sceneBody);
      scenesCard.append(details);
    }
    body.append(scenesCard);
  };

  const save = Object.assign(document.createElement("button"), { className: "vrgdg-film-button secondary", textContent: "Save Film plan" });
  save.onclick = async () => {
    try {
      const plan = await requestJson("/vrgdg/script_to_film/save_plan", "POST", { project_folder: state.projectFolder, fps: state.scriptToFilm.fps, scenes: state.segments });
      state.segments = plan.scenes;
      apply(`Saved Film plan: ${plan.plan_path}`);
    } catch (error) { status.textContent = String(error?.message || error); }
  };
  const build = Object.assign(document.createElement("button"), { className: "vrgdg-film-button", textContent: "Build T2I → I2V Film" });
  build.onclick = async () => { apply("Launching Script-to-Film build…"); await config.build?.(); };
  footer.append(Object.assign(document.createElement("span"), { className: "vrgdg-film-note", textContent: "Film controls are shared by Builder and Wizard." }), Object.assign(document.createElement("div"), { className: "vrgdg-film-actions" }));
  footer.lastChild.append(save, build);
  backdrop.onclick = (event) => { if (event.target === backdrop) backdrop.remove(); };
  document.body.appendChild(backdrop);
  render();
  apply("Film mode is active. Create or edit the duration-first shot plan.");
  return { close: () => backdrop.remove(), refresh: render };
}
