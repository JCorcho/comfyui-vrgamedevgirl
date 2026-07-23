import { app } from "../../../scripts/app.js";
import { ComfyWidgets } from "../../../scripts/widgets.js";

// The Concept Research nodes return their real data through normal STRING/INT
// outputs. This tiny frontend companion makes the same review-only result
// readable on the canvas without changing those data connections.
const NODE_NAMES = new Set([
  "VRGDG_ConceptResearchCivitai",
  "VRGDG_ConceptResearchViewCandidate",
  "VRGDG_ConceptResearchSaveApproved",
]);
const RESULT_WIDGET_STATE = Symbol("vrgdgConceptResearchResultWidgets");

function firstText(message) {
  const value = message?.text;
  if (Array.isArray(value)) return String(value[0] ?? "");
  return String(value ?? "");
}

function parseResult(message) {
  const raw = firstText(message);
  if (!raw) return { raw, data: null };
  try {
    return { raw, data: JSON.parse(raw) };
  } catch {
    return { raw, data: null };
  }
}

function oneLine(value, fallback = "Not supplied") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function listLoras(loras) {
  if (!Array.isArray(loras) || !loras.length) return "None recorded";
  return loras.map((lora) => {
    const name = oneLine(lora?.name, "Unnamed LoRA");
    const weight = lora?.weight;
    return weight === undefined || weight === null || weight === "" ? name : `${name} @ ${weight}`;
  }).join("\n");
}

function usableHttpUrl(value) {
  try {
    const url = new URL(String(value || "").trim());
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch {
    return "";
  }
}

function connectedTargets(searchNode, comfyClass) {
  const graph = searchNode.graph || app.graph;
  const output = searchNode.outputs?.find((item) => item?.name === "candidates_json");
  const links = Array.isArray(output?.links) ? output.links : [];
  return links.map((linkId) => {
    const link = graph?.links?.[linkId];
    const targetId = Array.isArray(link) ? link[3] : link?.target_id;
    return graph?.getNodeById?.(targetId);
  }).filter((node) => node?.comfyClass === comfyClass);
}

function reviewTargets(searchNode) {
  return connectedTargets(searchNode, "VRGDG_ConceptResearchViewCandidate");
}

function saveTargets(searchNode) {
  return connectedTargets(searchNode, "VRGDG_ConceptResearchSaveApproved");
}

function setNodeWidgetValue(node, name, value) {
  const widget = node?.widgets?.find((item) => item?.name === name);
  if (!widget) return false;
  widget.value = value;
  if (widget.inputEl) widget.inputEl.value = String(value);
  widget.callback?.(value);
  node.setDirtyCanvas?.(true, true);
  return true;
}

function showReviewToast(payload) {
  if (app.extensionManager?.toast?.add) {
    app.extensionManager.toast.add(payload);
  } else {
    console.info(payload.summary, payload.detail);
  }
}

function addSearchCandidateActions(node, candidates) {
  const reviews = reviewTargets(node);
  const saves = saveTargets(node);
  for (const [index, candidate] of candidates.entries()) {
    const ordinal = index + 1;
    const candidateId = oneLine(candidate?.candidate_id, "");
    const imageUrl = usableHttpUrl(candidate?.image_preview_url) || usableHttpUrl(candidate?.source_url);
    if (imageUrl) {
      node.addWidget("button", `Open image #${ordinal}`, imageUrl, () => {
        window.open(imageUrl, "_blank", "noopener,noreferrer");
      });
    }
    if (reviews.length) {
      node.addWidget("button", `Review result #${ordinal}`, candidateId, () => {
        for (const target of reviews) {
          setNodeWidgetValue(target, "candidate_id", candidateId);
          setNodeWidgetValue(target, "candidate_number", ordinal);
        }
        showReviewToast({
          severity: "success",
          summary: `Selected result #${ordinal}`,
          detail: "Queue the workflow to load its complete recipe details.",
          life: 3500,
        });
      });
    }
    if (saves.length) {
      node.addWidget("button", `Prepare save #${ordinal}`, candidateId, () => {
        for (const target of saves) {
          setNodeWidgetValue(target, "candidate_ids", candidateId);
        }
        showReviewToast({
          severity: "success",
          summary: `Prepared result #${ordinal} for saving`,
          detail: "Set the concept name and quality score, then queue to save explicitly.",
          life: 4500,
        });
      });
    }
  }
}

function candidateSummary(candidate, ordinal) {
  return [
    `#${ordinal}: ${oneLine(candidate?.candidate_id)}`,
    `Model: ${oneLine(candidate?.model_name)}`,
    `Settings: ${oneLine(candidate?.sampler)}, ${oneLine(candidate?.steps)} steps, CFG ${oneLine(candidate?.cfg)}`,
    `Score: ${oneLine(candidate?.candidate_score)} | Metadata: ${oneLine(candidate?.metadata_completeness?.core_fields_present)}/${oneLine(candidate?.metadata_completeness?.core_fields_total)}`,
    `Civitai: ${oneLine(candidate?.source_url)}`,
  ].join("\n");
}

function resultWidgets(nodeClass, message) {
  const { raw, data } = parseResult(message);
  if (!data || typeof data !== "object") {
    return [["Research result", raw || "No review data was returned."]];
  }

  if (nodeClass === "VRGDG_ConceptResearchCivitai") {
    const candidates = Array.isArray(data.candidates) ? data.candidates : [];
    const count = Number.isFinite(Number(data.candidate_count)) ? Number(data.candidate_count) : candidates.length;
    const summary = [
      `Found ${count} candidate${count === 1 ? "" : "s"}.`,
      `Query: ${oneLine(data.query)}`,
      `Base model: ${oneLine(data.base_model_filter)}`,
      `Content mode: ${data.safe_only === false ? "adult allowed" : "safe only"}`,
      `Endpoint: ${oneLine(data.api_endpoint)}`,
      "",
      "Use Open image to inspect a result. Connected Review or Save nodes receive their matching action buttons below; the Save action only prepares the choice and never saves automatically.",
    ].join("\n");
    const directory = candidates.length
      ? candidates.map((candidate, index) => candidateSummary(candidate, index + 1)).join("\n\n")
      : "No matching candidates were returned. Try a broader concept or select Any as the base model.";
    return [["Search summary", summary], ["Candidate directory", directory], ["__candidate_actions__", candidates]];
  }

  if (nodeClass === "VRGDG_ConceptResearchViewCandidate") {
    if (data.action_required) {
      const warnings = Array.isArray(data.warnings) && data.warnings.length
        ? `\n\n${data.warnings.join("\n")}`
        : "";
      return [["Review status", `${data.action_required}${warnings}`]];
    }
    const overview = [
      `Candidate ID: ${oneLine(data.candidate_id)}`,
      `Model: ${oneLine(data.model_name)}`,
      `Base model: ${oneLine(data.base_model)}`,
      `Settings: ${oneLine(data.sampler)}, ${oneLine(data.steps)} steps, CFG ${oneLine(data.cfg)}, Seed ${oneLine(data.seed)}`,
      `Selected by: ${oneLine(data.selection_mode)}`,
      `Civitai: ${oneLine(data.source_url)}`,
      `Post: ${oneLine(data.post_url)}`,
    ].join("\n");
    return [
      ["Selected candidate", overview],
      ["Positive prompt", oneLine(data.positive_prompt)],
      ["Negative prompt", oneLine(data.negative_prompt)],
      ["LoRAs", listLoras(data.loras)],
      ["Research notes", oneLine(data.notes)],
    ];
  }

  const saved = Array.isArray(data.saved) ? data.saved : [];
  const saveSummary = [
    `Saved recipes: ${oneLine(data.saved_count, "0")}`,
    data.action_required ? `Next step: ${data.action_required}` : "",
    saved.length ? "\n" + saved.map((entry) => `${oneLine(entry.candidate_id)} — ${oneLine(entry.action)}`).join("\n") : "",
  ].filter(Boolean).join("\n");
  return [["Approval result", saveSummary || raw]];
}

function clearResultWidgets(node) {
  const state = node[RESULT_WIDGET_STATE];
  if (!state || !node.widgets) return;
  while (node.widgets.length > state.baseWidgetCount) {
    node.widgets.pop()?.onRemove?.();
  }
}

function renderResultWidgets(node, message) {
  const state = node[RESULT_WIDGET_STATE] ?? { baseWidgetCount: node.widgets?.length ?? 0 };
  node[RESULT_WIDGET_STATE] = state;
  clearResultWidgets(node);

  for (const [label, value] of resultWidgets(node.comfyClass, message)) {
    if (label === "__candidate_actions__") {
      addSearchCandidateActions(node, Array.isArray(value) ? value : []);
      continue;
    }
    const widget = ComfyWidgets.STRING(
      node,
      label,
      ["STRING", { multiline: true }],
      app,
    ).widget;
    widget.inputEl.readOnly = true;
    widget.inputEl.style.opacity = 0.82;
    widget.value = String(value ?? "");
  }

  requestAnimationFrame(() => {
    const size = node.computeSize();
    size[0] = Math.max(size[0], node.size[0]);
    size[1] = Math.max(size[1], node.size[1]);
    node.onResize?.(size);
    app.graph.setDirtyCanvas(true, false);
  });
}

app.registerExtension({
  name: "vrgdg.ConceptResearchResults",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!NODE_NAMES.has(nodeData.name)) return;

    const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = originalOnNodeCreated?.apply(this, arguments);
      this[RESULT_WIDGET_STATE] = { baseWidgetCount: this.widgets?.length ?? 0 };
      return result;
    };

    const originalOnExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      originalOnExecuted?.apply(this, arguments);
      renderResultWidgets(this, message);
    };
  },
});
