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
    .vrgdg-film-recipe-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:10px; }
    .vrgdg-film-recipe-card { padding:10px; border:1px solid #365a7a; border-radius:7px; background:#0a1828; display:grid; gap:7px; }
    .vrgdg-film-recipe-card strong { color:#cffafe; }
    .vrgdg-film-recipe-meta { font-size:12px; color:#bae6fd; line-height:1.4; }
    .vrgdg-film-recipe-preview { font-size:12px; line-height:1.45; color:#cbd5e1; white-space:pre-wrap; }
    .vrgdg-film-research-candidate { padding:9px; border:1px solid #334155; border-radius:7px; display:grid; gap:6px; overflow:hidden; }
    .vrgdg-film-research-candidate input[type="checkbox"] { width:auto; margin-right:6px; }
    .vrgdg-film-candidate-media { min-height:210px; max-height:330px; border:1px solid #365a7a; border-radius:6px; overflow:hidden; display:grid; place-items:center; background:#020617; }
    .vrgdg-film-candidate-image { width:100%; height:100%; min-height:210px; max-height:330px; object-fit:contain; display:block; background:#020617; }
    .vrgdg-film-candidate-image-fallback { padding:12px; font-size:12px; line-height:1.4; color:#94a3b8; text-align:center; }
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

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function isTransientPlannerPollError(error) {
  const message = errorMessage(error).toLowerCase();
  return [
    "502",
    "503",
    "504",
    "bad gateway",
    "gateway timeout",
    "service unavailable",
    "failed to fetch",
    "networkerror",
    "network error",
    "load failed",
  ].some((marker) => message.includes(marker));
}

async function requestPromptPlan(payload, onProgress = null) {
  const accepted = await requestJson("/vrgdg/script_to_film/create_prompt_plan", "POST", payload);
  if (Array.isArray(accepted.scenes)) return accepted;
  const jobId = String(accepted.job_id || "").trim();
  if (!jobId) throw new Error("Film Prompt Creator did not return a job ID.");
  // Local GGUF prompt creators can legitimately take several minutes. A transient
  // gateway response during polling must not cancel the server-side job.
  const deadline = Date.now() + (20 * 60 * 1000);
  let elapsedSeconds = 0;
  let transientPollFailures = 0;
  while (Date.now() < deadline) {
    await delay(1500);
    elapsedSeconds += 1.5;
    let status;
    try {
      status = await requestJson(`/vrgdg/script_to_film/create_prompt_plan_status?job_id=${encodeURIComponent(jobId)}`);
      transientPollFailures = 0;
    } catch (error) {
      if (!isTransientPlannerPollError(error) || Date.now() >= deadline) throw error;
      transientPollFailures += 1;
      const retryDelay = Math.min(5000, 750 * (2 ** Math.min(transientPollFailures - 1, 3)));
      onProgress?.("temporarily disconnected; retrying", elapsedSeconds);
      await delay(retryDelay);
      continue;
    }
    if (status.status === "complete" && Array.isArray(status.scenes)) return status;
    onProgress?.(status.status || "running", elapsedSeconds);
  }
  throw new Error("Film Prompt Creator timed out after 20 minutes. The server job may still finish; check ComfyUI logs before retrying.");
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

function normalizeLoraNames(value) {
  const raw = Array.isArray(value) ? value : String(value || "").split(/[\n,;]/);
  const seen = new Set();
  return raw.map((item) => String(item || "").trim().replaceAll("\\", "/"))
    .filter(Boolean)
    .filter((item) => {
      const key = item.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function normalizeFilmKeyframeModel(value) {
  return String(value || "").trim().toLowerCase() === "anima" ? "anima" : "pony";
}

function filmKeyframeModelLabel(value) {
  return normalizeFilmKeyframeModel(value) === "anima" ? "Anima" : "Pony";
}

function jsonArray(value, label) {
  const parsed = JSON.parse(String(value || "[]"));
  if (!Array.isArray(parsed)) throw new Error(`${label} must be a JSON array.`);
  return parsed;
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
  const emitChange = () => onChange(control.type === "number" ? Number(control.value) : control.value);
  if (options.commitOnly) {
    // Some handlers rebuild the planner or begin async work. Do not replace the
    // active control while the user is still composing a value.
    control.title = options.commitHint || "Press Enter or click outside this field to apply the change.";
    control.addEventListener("change", emitChange);
    if (!options.multiline && !options.select) {
      control.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          control.blur();
        }
      });
    }
  } else {
    control.addEventListener("input", emitChange);
    control.addEventListener("change", emitChange);
  }
  wrap.appendChild(control);
  return wrap;
}

function candidatePreviewUrl(candidate) {
  try {
    const url = new URL(String(candidate?.image_preview_url || "").trim());
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function createCandidatePreview(candidate) {
  const media = document.createElement("div");
  media.className = "vrgdg-film-candidate-media";
  const previewUrl = candidatePreviewUrl(candidate);
  if (!previewUrl) {
    media.append(Object.assign(document.createElement("div"), {
      className: "vrgdg-film-candidate-image-fallback",
      textContent: "Civitai did not provide an embeddable preview for this candidate.",
    }));
    return media;
  }
  const image = document.createElement("img");
  image.className = "vrgdg-film-candidate-image";
  image.src = previewUrl;
  image.alt = `Civitai candidate ${String(candidate?.candidate_id || "preview")}`;
  image.loading = "lazy";
  image.decoding = "async";
  image.onerror = () => {
    media.replaceChildren(Object.assign(document.createElement("div"), {
      className: "vrgdg-film-candidate-image-fallback",
      textContent: "Civitai preview could not be loaded in the Planner. The recipe metadata is still available for review.",
    }));
  };
  media.append(image);
  return media;
}

export function openScriptToFilmPlanner(config) {
  injectStyles();
  const state = clone(config.snapshot?.() || {});
  state.projectMode = "script_to_film";
  state.scriptToFilm = state.scriptToFilm || {};
  state.scriptToFilm.fps = Number(state.scriptToFilm.fps || 25);
  state.scriptToFilm.script = String(state.scriptToFilm.script || "");
  state.scriptToFilm.lora_knowledge_loras = normalizeLoraNames(state.scriptToFilm.lora_knowledge_loras);
  state.scriptToFilm.style_profile_path = String(state.scriptToFilm.style_profile_path || "").trim();
  state.scriptToFilm.keyframe_model = normalizeFilmKeyframeModel(state.scriptToFilm.keyframe_model);
  const promptCreatorModels = promptCreatorModelChoices(state);
  state.scriptToFilm.prompt_creator_model = String(
    state.scriptToFilm.prompt_creator_model
    || state.scriptToFilm.last_prompt_creator_model
    || state.textGemmaModel
    || promptCreatorModels[0]
    || "",
  ).trim();
  state.segments = Array.isArray(state.segments) ? state.segments : [];
  let loraKnowledge = { entries: [], installed_loras: [], last_refreshed: "", store_path: "" };
  let selectedKnowledgeLora = "";
  const attemptedCivitaiDetection = new Set();
  const activeCivitaiDetection = new Set();
  const conceptSuggestions = new Map();
  const activeSuggestionRequests = new Set();
  const conceptResearchReviews = new Map();
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
    const plan = await requestJson("/vrgdg/script_to_film/plan", "POST", {
      fps: state.scriptToFilm.fps,
      scenes: state.segments,
      keyframe_model: state.scriptToFilm.keyframe_model,
      lora_knowledge_loras: state.scriptToFilm.lora_knowledge_loras,
      style_profile_path: state.scriptToFilm.style_profile_path,
    });
    state.segments = ensureStableSceneIds(plan.scenes);
    state.scriptToFilm.lora_knowledge_loras = normalizeLoraNames(plan.lora_knowledge_loras || state.scriptToFilm.lora_knowledge_loras);
    state.scriptToFilm.style_profile_path = String(plan.style_profile_path || state.scriptToFilm.style_profile_path || "").trim();
    state.scriptToFilm.keyframe_model = normalizeFilmKeyframeModel(plan.keyframe_model || state.scriptToFilm.keyframe_model);
    apply(`Timeline reflowed: ${Number(plan.total_duration_seconds || 0).toFixed(2)} seconds.`);
  };
  const suggestionRequestKey = (scene) => [
    String(scene?.id || ""),
    normalizeFilmKeyframeModel(state.scriptToFilm.keyframe_model),
    String(scene?.concept_key || scene?.pose_concept || scene?.concept || "").trim().toLowerCase(),
  ].join("|");
  const loadSceneSuggestions = async (scene, { force = false } = {}) => {
    if (!scene || typeof scene !== "object") return null;
    const sceneId = String(scene.id || "").trim();
    if (!sceneId) return null;
    const requestKey = suggestionRequestKey(scene);
    const current = conceptSuggestions.get(sceneId);
    if (!force && current?.requestKey === requestKey) return current.data;
    if (activeSuggestionRequests.has(requestKey)) return null;
    activeSuggestionRequests.add(requestKey);
    try {
      const data = await requestJson("/vrgdg/script_to_film/concept_intelligence/suggest", "POST", {
        scene,
        base_model: filmKeyframeModelLabel(state.scriptToFilm.keyframe_model),
        limit: 3,
      });
      conceptSuggestions.set(sceneId, { requestKey, data });
      if (document.body.contains(backdrop)) render();
      return data;
    } catch (error) {
      const data = { recipes: [], message: `Local recipe suggestions are unavailable: ${errorMessage(error)}`, concept: { concept_key: "" } };
      conceptSuggestions.set(sceneId, { requestKey, data });
      if (document.body.contains(backdrop)) render();
      return data;
    } finally {
      activeSuggestionRequests.delete(requestKey);
    }
  };
  const autoDetectCivitaiForSelection = async (loraName, { force = false } = {}) => {
    const name = String(loraName || "").trim();
    if (!name) return null;
    const key = name.toLowerCase();
    if (activeCivitaiDetection.has(key) || (!force && attemptedCivitaiDetection.has(key))) return null;
    activeCivitaiDetection.add(key);
    attemptedCivitaiDetection.add(key);
    try {
      const researched = await requestJson("/vrgdg/script_to_film/lora_knowledge/research_civitai", "POST", { lora_name: name });
      if (researched?.entry?.lora_name) {
        loraKnowledge.entries = (loraKnowledge.entries || []).map((item) => item.lora_name === researched.entry.lora_name ? researched.entry : item);
      }
      if (researched?.found) {
        const detail = researched.researched && researched.civitai_name ? `: ${researched.civitai_name}` : "";
        const triggerCount = Array.isArray(researched?.entry?.civitai_trigger_words) ? researched.entry.civitai_trigger_words.length : 0;
        status.textContent = researched.researched
          ? `Civitai metadata refreshed for ${name}${detail}; ${triggerCount} trigger word${triggerCount === 1 ? "" : "s"} imported.`
          : `Civitai model ID auto-filled for ${name}${detail}.`;
      } else {
        status.textContent = `No verified Civitai match was available for ${name}; its local metadata remains usable.`;
      }
      if (document.body.contains(backdrop) && selectedKnowledgeLora === name) render();
      return researched;
    } catch (error) {
      // A temporary Civitai outage must not make the selected local LoRA look
      // invalid or block Film rendering. The user can retry the explicit button.
      status.textContent = `Civitai auto-detection is temporarily unavailable for ${name}; local metadata remains usable.`;
      return null;
    } finally {
      activeCivitaiDetection.delete(key);
    }
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
      field("Character Style Profile JSON (optional)", state.scriptToFilm.style_profile_path, (value) => {
        state.scriptToFilm.style_profile_path = String(value || "").trim();
        apply("Character Style Profile link updated. It is separate from the Character Bible.");
      }),
      field("Keyframe base model", state.scriptToFilm.keyframe_model, (value) => {
        state.scriptToFilm.keyframe_model = normalizeFilmKeyframeModel(value);
        conceptSuggestions.clear();
        apply(`${filmKeyframeModelLabel(state.scriptToFilm.keyframe_model)} is now the Film keyframe model; local recipe suggestions were refreshed for that base model.`);
        render();
      }, { select: [
        { value: "pony", label: "Pony (VioletsT2I workflow)" },
        { value: "anima", label: "Anima (VioletsT2I workflow)" },
      ] }),
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
        const plan = await requestPromptPlan({
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
          lora_knowledge_loras: state.scriptToFilm.lora_knowledge_loras,
          style_profile_path: state.scriptToFilm.style_profile_path,
          keyframe_model: state.scriptToFilm.keyframe_model,
        }, (jobStatus, elapsedSeconds) => {
          status.textContent = `Film Prompt Creator is still running (${jobStatus}, ${Math.floor(elapsedSeconds)}s): ${selectedModel || state.text_gemma_runner}…`;
        });
        if (!Array.isArray(plan?.scenes) || !plan.scenes.length) throw new Error("The Prompt Creator returned no Film scenes.");
        state.segments = ensureStableSceneIds(plan.scenes);
        state.scriptToFilm.last_prompt_creator_model = plan.used_model || selectedModel;
        state.scriptToFilm.system_prompt_path = plan.system_prompt_path || "";
        state.scriptToFilm.lora_knowledge_loras = normalizeLoraNames(plan.lora_knowledge_loras || state.scriptToFilm.lora_knowledge_loras);
        state.scriptToFilm.style_profile_path = String(plan.style_profile_path || state.scriptToFilm.style_profile_path || "").trim();
        state.scriptToFilm.keyframe_model = normalizeFilmKeyframeModel(plan.keyframe_model || state.scriptToFilm.keyframe_model);
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

    const knowledgeCard = document.createElement("section");
    knowledgeCard.className = "vrgdg-film-card";
    knowledgeCard.append(
      Object.assign(document.createElement("h3"), { textContent: "2. LoRA Knowledge Base (technical generation metadata)" }),
      Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: "This store owns trigger maps, compatibility, weights, and prompt examples. Character Bible stays identity-only; it never stores trigger words or LoRA technical details. Selecting a LoRA automatically looks up its Civitai model ID from embedded data, an exact file hash, or a high-confidence filename match." }),
    );
    const knowledgeActions = document.createElement("div");
    knowledgeActions.className = "vrgdg-film-actions";
    const refreshKnowledge = Object.assign(document.createElement("button"), { className: "vrgdg-film-button", textContent: "Import / Refresh LoRA Metadata" });
    refreshKnowledge.onclick = async () => {
      try {
        refreshKnowledge.disabled = true;
        loraKnowledge = await requestJson("/vrgdg/script_to_film/lora_knowledge/refresh", "POST", {});
        if (!selectedKnowledgeLora) selectedKnowledgeLora = loraKnowledge.entries?.[0]?.lora_name || "";
        apply(`LoRA Knowledge Base refreshed: ${Number(loraKnowledge.created_count || 0)} imported, ${Number(loraKnowledge.updated_count || 0)} updated.`);
        render();
      } catch (error) {
        status.textContent = `LoRA metadata import error: ${errorMessage(error)}`;
      } finally { refreshKnowledge.disabled = false; }
    };
    const reloadKnowledge = Object.assign(document.createElement("button"), { className: "vrgdg-film-button secondary", textContent: "Reload Knowledge Base" });
    reloadKnowledge.onclick = async () => {
      try {
        reloadKnowledge.disabled = true;
        loraKnowledge = await requestJson("/vrgdg/script_to_film/lora_knowledge");
        if (!selectedKnowledgeLora) selectedKnowledgeLora = loraKnowledge.entries?.[0]?.lora_name || "";
        render();
      } catch (error) { status.textContent = `LoRA Knowledge Base error: ${errorMessage(error)}`; }
      finally { reloadKnowledge.disabled = false; }
    };
    knowledgeActions.append(refreshKnowledge, reloadKnowledge);
    knowledgeCard.append(knowledgeActions);
    const availableEntries = Array.isArray(loraKnowledge.entries) ? loraKnowledge.entries : [];
    if (!availableEntries.length) {
      knowledgeCard.append(Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: "No metadata records are loaded yet. Choose Import / Refresh to scan installed LoRA headers without downloading anything." }));
    } else {
      const activeWrap = document.createElement("label");
      activeWrap.className = "vrgdg-film-label";
      activeWrap.textContent = "Active LoRA knowledge for this Film project (Ctrl/Cmd-click for multiple)";
      const activeSelect = document.createElement("select");
      activeSelect.className = "vrgdg-film-select";
      activeSelect.multiple = true;
      activeSelect.size = Math.min(8, Math.max(3, availableEntries.length));
      const activeNames = new Set(normalizeLoraNames(state.scriptToFilm.lora_knowledge_loras).map((name) => name.toLowerCase()));
      for (const entry of availableEntries) {
        const option = document.createElement("option");
        option.value = entry.lora_name;
        option.textContent = `${entry.lora_name} · ${entry.base_model_recommendation || "unknown"} · ${entry.installed ? "installed" : "not installed"}`;
        option.selected = activeNames.has(String(entry.lora_name || "").toLowerCase());
        activeSelect.appendChild(option);
      }
      activeSelect.onchange = () => {
        state.scriptToFilm.lora_knowledge_loras = Array.from(activeSelect.selectedOptions).map((option) => option.value);
        apply("Active Film LoRA knowledge updated. Matching triggers will resolve per shot at render time.");
        for (const loraName of state.scriptToFilm.lora_knowledge_loras) void autoDetectCivitaiForSelection(loraName);
      };
      activeWrap.appendChild(activeSelect);
      knowledgeCard.append(activeWrap);

      if (!selectedKnowledgeLora || !availableEntries.some((entry) => entry.lora_name === selectedKnowledgeLora)) selectedKnowledgeLora = availableEntries[0].lora_name;
      const entry = availableEntries.find((item) => item.lora_name === selectedKnowledgeLora) || availableEntries[0];
      const editor = document.createElement("div");
      editor.className = "vrgdg-film-grid";
      const editorSelect = field("Edit LoRA metadata", selectedKnowledgeLora, (value) => {
        selectedKnowledgeLora = value;
        render();
        void autoDetectCivitaiForSelection(value);
      }, { select: availableEntries.map((item) => ({ value: item.lora_name, label: item.lora_name })) });
      const civitai = field("Civitai model ID (automatically detected; optional override)", entry.civitai_model_id || "", () => {});
      const baseModel = field("Base model recommendation", entry.base_model_recommendation || "unknown", () => {});
      const recommendedWeight = field("Recommended weight", entry.recommended_weight ?? 1, () => {}, { type: "number" });
      const triggerMap = field("Trigger map JSON", JSON.stringify(entry.trigger_map || {}, null, 2), () => {}, { multiline: true });
      const civitaiWords = field("Civitai trigger words (auto-imported)", (entry.civitai_trigger_words || []).join(", "), () => {}, { multiline: true });
      civitaiWords.querySelector("textarea")?.setAttribute("readonly", "readonly");
      const positives = field("Positive patterns JSON", JSON.stringify(entry.example_positive_patterns || [], null, 2), () => {}, { multiline: true });
      const negatives = field("Negative patterns JSON", JSON.stringify(entry.example_negative_patterns || [], null, 2), () => {}, { multiline: true });
      const notes = field("Notes", entry.notes || "", () => {}, { multiline: true });
      editor.append(editorSelect, civitai, baseModel, recommendedWeight, triggerMap, civitaiWords, positives, negatives, notes);
      knowledgeCard.append(editor);
      const editorActions = document.createElement("div");
      editorActions.className = "vrgdg-film-actions";
      const saveEntry = Object.assign(document.createElement("button"), { className: "vrgdg-film-button secondary", textContent: "Save LoRA Metadata" });
      const saveCurrentEntry = async () => {
        const triggerValue = JSON.parse(String(triggerMap.querySelector("textarea")?.value || "{}"));
        if (!triggerValue || Array.isArray(triggerValue) || typeof triggerValue !== "object") throw new Error("Trigger map must be a JSON object.");
        const saved = await requestJson("/vrgdg/script_to_film/lora_knowledge/upsert", "POST", {
          entry: {
            ...entry,
            lora_name: entry.lora_name,
            civitai_model_id: civitai.querySelector("input")?.value || "",
            base_model_recommendation: baseModel.querySelector("input")?.value || "unknown",
            recommended_weight: Number(recommendedWeight.querySelector("input")?.value || 1),
            trigger_map: triggerValue,
            example_positive_patterns: jsonArray(positives.querySelector("textarea")?.value, "Positive patterns"),
            example_negative_patterns: jsonArray(negatives.querySelector("textarea")?.value, "Negative patterns"),
            notes: notes.querySelector("textarea")?.value || "",
          },
        });
        loraKnowledge = saved;
        selectedKnowledgeLora = entry.lora_name;
        return saved;
      };
      saveEntry.onclick = async () => {
        try {
          await saveCurrentEntry();
          status.textContent = `Saved LoRA metadata: ${entry.lora_name}`;
          render();
        } catch (error) { status.textContent = `LoRA metadata save error: ${errorMessage(error)}`; }
      };
      const research = Object.assign(document.createElement("button"), { className: "vrgdg-film-button secondary", textContent: "Auto-detect / Refresh Civitai Metadata" });
      research.onclick = async () => {
        try {
          research.disabled = true;
          const stagedId = String(civitai.querySelector("input")?.value || "").trim();
          if (stagedId !== String(entry.civitai_model_id || "")) {
            await saveCurrentEntry();
          }
          const researched = await autoDetectCivitaiForSelection(entry.lora_name, { force: true });
          if (researched?.found) return;
          if (researched) status.textContent = `No verified Civitai match was available for ${entry.lora_name}; local metadata remains usable.`;
        } catch (error) { status.textContent = `Civitai metadata lookup error: ${errorMessage(error)}`; }
        finally { research.disabled = false; }
      };
      editorActions.append(saveEntry, research);
      knowledgeCard.append(editorActions);
      void autoDetectCivitaiForSelection(entry.lora_name);
    }
    body.append(knowledgeCard);

    const scenesCard = document.createElement("section");
    scenesCard.className = "vrgdg-film-card";
    scenesCard.append(Object.assign(document.createElement("h3"), { textContent: `3. Film scenes (${state.segments.length})` }), Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: `Use Pure T2AV for unconditioned establishing shots. Use I2V/T2AV + Character Ref for ${filmKeyframeModelLabel(state.scriptToFilm.keyframe_model)} keyframes or character locking. The selected Violets LTX FP8 profile supplies DMD 1.0, JoyAI 0.5, and the shared Audio Text Encoder / sampler controls.` }));
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
        field("Target duration (seconds)", scene.target_duration_seconds, (value) => { scene.target_duration_seconds = Math.max(.1, Number(value || 4)); scene.actual_duration_seconds = 0; apply("Duration changed; LTX frame count snapped."); render(); }, { type: "number", commitOnly: true }),
        field("Render mode", scene.film_render_mode || "i2v_t2av", (value) => { scene.film_render_mode = value; apply(); }, { select: [{ value: "i2v_t2av", label: "I2V/T2AV + Character Ref" }, { value: "t2av", label: "Pure T2AV establishing shot" }] }),
        field(`Character / ${filmKeyframeModelLabel(state.scriptToFilm.keyframe_model)} keyframe image`, scene.character_reference_path || scene.ref_image_path || "", (value) => { scene.character_reference_path = value; scene.ref_image_path = value; apply(); }),
        field("Concept / pose (optional override)", scene.concept_key || scene.pose_concept || scene.concept || "", (value) => {
          scene.concept_key = String(value || "").trim();
          conceptSuggestions.delete(String(scene.id || ""));
          conceptResearchReviews.delete(String(scene.id || ""));
          apply("Concept / pose updated. Matching local recipes are being checked.");
          void loadSceneSuggestions(scene, { force: true });
        }, { commitOnly: true }),
        field("Scene LoRA metadata refs (optional)", normalizeLoraNames(scene.lora_knowledge_refs).join(", "), (value) => { scene.lora_knowledge_refs = normalizeLoraNames(value); apply("Scene LoRA refs updated; blank uses the project selection."); }),
        field("Transition cut", scene.transition_cut_type || "auto", (value) => { scene.transition_cut_type = value; apply(); }, { select: [{ value: "auto", label: "Carry ambience when requested" }, { value: "hard_cut", label: "Hard cut: no ambience overlap" }] }),
        field("Ambience overlap (seconds)", scene.transition_overlap_seconds ?? .25, (value) => { scene.transition_overlap_seconds = Math.max(0, Math.min(2, Number(value || 0))); apply(); }, { type: "number" }),
      );
      sceneBody.append(core);
      const prompts = document.createElement("div"); prompts.className = "vrgdg-film-grid";
      prompts.append(
        field(`${filmKeyframeModelLabel(state.scriptToFilm.keyframe_model)} keyframe prompt`, scene.t2i_prompt, (value) => { scene.t2i_prompt = value; scene.keyframe_prompt = value; apply(); }, { multiline: true }),
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
      const intelligence = document.createElement("section");
      intelligence.className = "vrgdg-film-recipe-card";
      intelligence.append(
        Object.assign(document.createElement("strong"), { textContent: "Concept / Pose recipe suggestions" }),
        Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: `Local ${filmKeyframeModelLabel(state.scriptToFilm.keyframe_model)} recipes are ranked by the existing Knowledge Base quality score. An explicit Concept / pose overrides automatic matching from the scene text.` }),
      );
      const sceneId = String(scene.id || "");
      const suggestionEntry = conceptSuggestions.get(sceneId);
      if (!suggestionEntry) {
        intelligence.append(Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: "Checking local recipes for this scene…" }));
        void loadSceneSuggestions(scene);
      } else {
        const suggestions = suggestionEntry.data || {};
        const inferred = suggestions.concept || {};
        const inferredText = inferred.concept_key
          ? `${inferred.inference === "explicit" ? "Using" : "Inferred"} concept: ${inferred.display_name || inferred.concept_key}.`
          : "No local concept could be inferred yet.";
        intelligence.append(Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: inferredText }));
        const recipeList = Array.isArray(suggestions.recipes) ? suggestions.recipes : [];
        if (recipeList.length) {
          const cards = document.createElement("div");
          cards.className = "vrgdg-film-recipe-grid";
          for (const recipe of recipeList) {
            const card = document.createElement("article");
            card.className = "vrgdg-film-recipe-card";
            const loraText = (Array.isArray(recipe.loras) ? recipe.loras : []).map((item) => `${item.name || "LoRA"} @ ${Number(item.weight ?? 1)}`).join("; ") || "none";
            card.append(
              Object.assign(document.createElement("strong"), { textContent: `Quality ${Number(recipe.quality_score || 0).toFixed(1)} · ${recipe.recipe_id}` }),
              Object.assign(document.createElement("div"), { className: "vrgdg-film-recipe-meta", textContent: `Seed ${recipe.seed || "—"} · CFG ${recipe.cfg ?? "—"} · ${recipe.steps ?? "—"} steps · ${recipe.sampler || "sampler unspecified"}` }),
              Object.assign(document.createElement("div"), { className: "vrgdg-film-recipe-meta", textContent: `LoRAs: ${loraText}` }),
              Object.assign(document.createElement("div"), { className: "vrgdg-film-recipe-preview", textContent: recipe.positive_prompt_preview || "No positive prompt stored." }),
            );
            const applyRecipe = Object.assign(document.createElement("button"), { className: "vrgdg-film-button", textContent: "Apply recipe to this scene" });
            applyRecipe.onclick = async () => {
              try {
                applyRecipe.disabled = true;
                const applied = await requestJson("/vrgdg/script_to_film/concept_intelligence/apply", "POST", {
                  scene,
                  concept_key: inferred.concept_key,
                  recipe_id: recipe.recipe_id,
                  base_model: filmKeyframeModelLabel(state.scriptToFilm.keyframe_model),
                });
                Object.assign(scene, applied.scene || {});
                conceptSuggestions.delete(sceneId);
                apply(`Applied ${recipe.recipe_id}: positive fragment, negative fragment, recipe LoRAs, seed, CFG, steps, and sampler were copied into this Film scene.`);
                render();
              } catch (error) {
                status.textContent = `Recipe apply error: ${errorMessage(error)}`;
              } finally { applyRecipe.disabled = false; }
            };
            card.append(applyRecipe);
            cards.append(card);
          }
          intelligence.append(cards);
        } else {
          intelligence.append(Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: suggestions.message || "No matching local recipes are available yet." }));
        }
        const appliedRecipe = scene.applied_concept_recipe || {};
        if (appliedRecipe.recipe_id) {
          const settings = scene.concept_recipe_settings || {};
          intelligence.append(Object.assign(document.createElement("p"), {
            className: "vrgdg-film-note",
            textContent: `Applied recipe: ${appliedRecipe.recipe_id} · saved seed ${settings.seed || "—"}, CFG ${settings.cfg ?? "—"}, ${settings.steps ?? "—"} steps, ${settings.sampler || "sampler unspecified"}. Its negative fragment and LoRA list are preserved in this scene record; workflow-managed negative conditioning and LoRA loading are never silently overwritten.`,
          }));
        }
        const refreshSuggestions = Object.assign(document.createElement("button"), { className: "vrgdg-film-button secondary", textContent: "Refresh local suggestions" });
        refreshSuggestions.onclick = async () => {
          try {
            refreshSuggestions.disabled = true;
            await loadSceneSuggestions(scene, { force: true });
            status.textContent = "Local recipe suggestions refreshed.";
          } catch (error) { status.textContent = `Suggestion refresh error: ${errorMessage(error)}`; }
          finally { refreshSuggestions.disabled = false; }
        };
        const researchMore = Object.assign(document.createElement("button"), { className: "vrgdg-film-button secondary", textContent: "Research more for this concept" });
        const runConceptResearch = async () => {
          try {
            researchMore.disabled = true;
            const latest = await loadSceneSuggestions(scene, { force: true });
            const conceptKey = String(latest?.concept?.concept_key || scene.concept_key || "").trim();
            if (!conceptKey) throw new Error("Add a Concept / pose value before researching more recipes.");
            const review = conceptResearchReviews.get(sceneId) || { safe_only: true, max_candidates: 8, quality_score: 6 };
            const contentMode = review.safe_only === false ? "adult-allowed" : "safe-only";
            status.textContent = `Researching ${contentMode} Civitai results for ${conceptKey}; results will require review before they are saved.`;
            const result = await requestJson("/vrgdg/script_to_film/concept_intelligence/research", "POST", {
              concept_query: conceptKey,
              base_model: filmKeyframeModelLabel(state.scriptToFilm.keyframe_model),
              max_candidates: Number(review.max_candidates || 8),
              safe_only: review.safe_only !== false,
            });
            conceptResearchReviews.set(sceneId, { ...review, result, selected_ids: [] });
            status.textContent = `Civitai returned ${Number(result.candidate_count || 0)} review candidate(s) for ${conceptKey}.`;
            render();
          } catch (error) { status.textContent = `Concept research error: ${errorMessage(error)}`; }
          finally { researchMore.disabled = false; }
        };
        researchMore.onclick = () => { void runConceptResearch(); };
        const recipeActions = document.createElement("div");
        recipeActions.className = "vrgdg-film-actions";
        recipeActions.append(refreshSuggestions, researchMore);
        intelligence.append(recipeActions);
        const review = conceptResearchReviews.get(sceneId);
        if (review) {
          const reviewCard = document.createElement("section");
          reviewCard.className = "vrgdg-film-recipe-card";
          reviewCard.append(Object.assign(document.createElement("strong"), { textContent: `Civitai review · ${Number(review.result?.candidate_count || 0)} candidate(s)` }));
          const reviewControls = document.createElement("div");
          reviewControls.className = "vrgdg-film-actions";
          const safeWrap = document.createElement("label");
          safeWrap.className = "vrgdg-film-label";
          const safeOnly = document.createElement("input");
          safeOnly.type = "checkbox";
          safeOnly.checked = review.safe_only !== false;
          safeOnly.onchange = () => {
            review.safe_only = safeOnly.checked;
            review.selected_ids = [];
            conceptResearchReviews.set(sceneId, review);
            status.textContent = `Content mode changed to ${safeOnly.checked ? "safe-only" : "adult-allowed"}; refreshing Civitai results now.`;
            void runConceptResearch();
          };
          safeWrap.append(safeOnly, document.createTextNode(" Safe-only research (clear for adult-allowed)"));
          const candidateLimit = field("Maximum candidates", review.max_candidates || 8, (value) => { review.max_candidates = Math.max(1, Math.min(20, Number(value || 8))); }, { type: "number" });
          const qualityScore = field("Quality score when saving", review.quality_score ?? 6, (value) => { review.quality_score = Math.max(0, Math.min(10, Number(value || 0))); }, { type: "number" });
          reviewControls.append(safeWrap, candidateLimit, qualityScore);
          reviewCard.append(reviewControls);
          const candidates = Array.isArray(review.result?.candidates) ? review.result.candidates : [];
          if (!candidates.length) {
            reviewCard.append(Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: (review.result?.warnings || ["No review candidates were returned."]).join(" ") }));
          } else {
            const candidatesList = document.createElement("div");
            candidatesList.className = "vrgdg-film-recipe-grid";
            for (const candidate of candidates) {
              const candidateId = String(candidate.candidate_id || "");
              const candidateCard = document.createElement("label");
              candidateCard.className = "vrgdg-film-research-candidate";
              const select = document.createElement("input");
              select.type = "checkbox";
              select.checked = Array.isArray(review.selected_ids) && review.selected_ids.includes(candidateId);
              select.onchange = () => {
                const picked = new Set(Array.isArray(review.selected_ids) ? review.selected_ids : []);
                if (select.checked) picked.add(candidateId); else picked.delete(candidateId);
                review.selected_ids = Array.from(picked);
              };
              const label = document.createElement("span");
              label.append(select, document.createTextNode(` Review ${candidateId}`));
              const loras = (Array.isArray(candidate.loras) ? candidate.loras : []).map((item) => `${item.name || "LoRA"} @ ${Number(item.weight ?? 1)}`).join("; ") || "none";
              candidateCard.append(
                label,
                createCandidatePreview(candidate),
                Object.assign(document.createElement("div"), { className: "vrgdg-film-recipe-meta", textContent: `Seed ${candidate.seed || "—"} · CFG ${candidate.cfg ?? "—"} · ${candidate.steps ?? "—"} steps · ${candidate.sampler || "sampler unspecified"}` }),
                Object.assign(document.createElement("div"), { className: "vrgdg-film-recipe-meta", textContent: `LoRAs: ${loras}` }),
                Object.assign(document.createElement("div"), { className: "vrgdg-film-recipe-preview", textContent: String(candidate.positive_prompt || "").slice(0, 320) || "No positive prompt stored." }),
              );
              candidatesList.append(candidateCard);
            }
            reviewCard.append(candidatesList);
          }
          const saveReviewed = Object.assign(document.createElement("button"), { className: "vrgdg-film-button", textContent: "Approve selected and save to local recipes" });
          saveReviewed.onclick = async () => {
            try {
              const selectedIds = Array.isArray(review.selected_ids) ? review.selected_ids.filter(Boolean) : [];
              if (!selectedIds.length) throw new Error("Check one or more candidates after reviewing them before saving.");
              saveReviewed.disabled = true;
              const conceptKey = String(review.result?.query || suggestions.concept?.concept_key || scene.concept_key || "").trim();
              const saved = await requestJson("/vrgdg/script_to_film/concept_intelligence/save_research", "POST", {
                candidates_payload: review.result,
                candidate_ids: selectedIds.join(","),
                concept_key: conceptKey,
                base_model: filmKeyframeModelLabel(state.scriptToFilm.keyframe_model),
                quality_score: Number(review.quality_score ?? 6),
              });
              conceptResearchReviews.delete(sceneId);
              conceptSuggestions.delete(sceneId);
              await loadSceneSuggestions(scene, { force: true });
              apply(`Saved ${Number(saved.saved_count || 0)} reviewed recipe(s) locally. The refreshed suggestions now include them.`);
            } catch (error) { status.textContent = `Recipe save error: ${errorMessage(error)}`; }
            finally { saveReviewed.disabled = false; }
          };
          reviewCard.append(saveReviewed, Object.assign(document.createElement("p"), { className: "vrgdg-film-note", textContent: "Civitai candidates are never auto-saved. Check each one you want only after reviewing its prompt, LoRAs, and settings." }));
          intelligence.append(reviewCard);
        }
      }
      sceneBody.append(intelligence);
      const resolved = scene.resolved_lora_triggers || {};
      const keyframeKeys = (resolved.keyframe || []).flatMap((item) => item.keys || []);
      const ltxKeys = (resolved.ltx || []).flatMap((item) => item.keys || []);
      if (keyframeKeys.length || ltxKeys.length) {
        sceneBody.append(Object.assign(document.createElement("p"), {
          className: "vrgdg-film-note",
          textContent: `Resolved LoRA trigger keys — ${filmKeyframeModelLabel(state.scriptToFilm.keyframe_model)}: ${keyframeKeys.join(", ") || "none"}; LTX: ${ltxKeys.join(", ") || "none"}. Triggers are kept out of Character Bible.`,
        }));
      }
      details.append(sceneBody);
      scenesCard.append(details);
    }
    body.append(scenesCard);
  };

  const save = Object.assign(document.createElement("button"), { className: "vrgdg-film-button secondary", textContent: "Save Film plan" });
  save.onclick = async () => {
    try {
      const plan = await requestJson("/vrgdg/script_to_film/save_plan", "POST", {
        project_folder: state.projectFolder,
        fps: state.scriptToFilm.fps,
        scenes: state.segments,
        keyframe_model: state.scriptToFilm.keyframe_model,
        lora_knowledge_loras: state.scriptToFilm.lora_knowledge_loras,
        style_profile_path: state.scriptToFilm.style_profile_path,
      });
      state.segments = plan.scenes;
      state.scriptToFilm.lora_knowledge_loras = normalizeLoraNames(plan.lora_knowledge_loras || state.scriptToFilm.lora_knowledge_loras);
      state.scriptToFilm.style_profile_path = String(plan.style_profile_path || state.scriptToFilm.style_profile_path || "").trim();
      state.scriptToFilm.keyframe_model = normalizeFilmKeyframeModel(plan.keyframe_model || state.scriptToFilm.keyframe_model);
      apply(`Saved Film plan: ${plan.plan_path}`);
    } catch (error) { status.textContent = String(error?.message || error); }
  };
  const build = Object.assign(document.createElement("button"), { className: "vrgdg-film-button", textContent: "Build T2I → I2V Film" });
  build.onclick = async () => {
    try {
      build.disabled = true;
      apply("Launching Script-to-Film build… See the progress window for live render status.");
      const result = await config.build?.();
      const finalPath = String(result?.final_video_path || "").trim();
      status.textContent = finalPath
        ? `Script-to-Film build complete: ${finalPath}`
        : "Script-to-Film build complete. See the project output folder for the final video.";
    } catch (error) {
      status.textContent = `Script-to-Film build failed: ${String(error?.message || error || "Unknown build error")}`.slice(0, 2000);
    } finally {
      build.disabled = false;
    }
  };
  footer.append(Object.assign(document.createElement("span"), { className: "vrgdg-film-note", textContent: "Film controls are shared by Builder and Wizard." }), Object.assign(document.createElement("div"), { className: "vrgdg-film-actions" }));
  footer.lastChild.append(save, build);
  backdrop.onclick = (event) => { if (event.target === backdrop) backdrop.remove(); };
  document.body.appendChild(backdrop);
  render();
  apply("Film mode is active. Create or edit the duration-first shot plan.");
  // The store is intentionally lazy: opening the modal never writes metadata.
  // The explicit Import / Refresh action performs the installed-LoRA scan.
  void requestJson("/vrgdg/script_to_film/lora_knowledge")
    .then((data) => {
      loraKnowledge = data;
      if (!selectedKnowledgeLora) selectedKnowledgeLora = data.entries?.[0]?.lora_name || "";
      if (document.body.contains(backdrop)) render();
    })
    .catch((error) => {
      if (document.body.contains(backdrop)) status.textContent = `LoRA Knowledge Base unavailable: ${errorMessage(error)}`;
    });
  return { close: () => backdrop.remove(), refresh: render };
}
