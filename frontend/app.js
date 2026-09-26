const API_BASE = window.RECON_API_BASE || (window.location.port === "8000" ? "" : "http://127.0.0.1:8000");
const state = { view: "overview", case: null, artifacts: [], selectedFile: null, filter: "ALL", sort: "priority" };

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const formatBytes = (bytes) => { if (bytes === null || bytes === undefined) return "Not established"; if (bytes < 1024) return `${bytes} B`; const units = ["KB", "MB", "GB"]; let value = bytes / 1024; let index = 0; while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; } return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`; };
const formatDate = (value) => value ? new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "Not established";
const valueOrUnknown = (value, fallback = "Not established") => value === null || value === undefined ? fallback : value;
const percent = (value) => value === null || value === undefined ? "Not established" : `${Math.round(value * 100)}%`;
const numberValue = (value) => value === null || value === undefined ? "Not established" : Number(value).toFixed(2);

async function api(path, options = {}) {
	const response = await fetch(`${API_BASE}${path}`, options);
	let body = null;
	try { body = await response.json(); } catch (_) { body = null; }
	if (!response.ok) throw new Error(body?.detail || `Request failed (${response.status})`);
	return body;
}

function showToast(message) { const toast = $("#toast"); toast.textContent = message; toast.classList.add("show"); window.clearTimeout(showToast.timer); showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2800); }
function showError(message) { const panel = $("#uploadError"); panel.textContent = message; panel.hidden = false; }
function clearError() { $("#uploadError").hidden = true; }

function statusBadge(status) { const key = String(status || "UNRELIABLE").toLowerCase(); return `<span class="status-badge status-${key}">${escapeHtml(status || "UNKNOWN")}</span>`; }
function confidenceBadge(artifact) { if (artifact.confidence_score === null || artifact.confidence_score === undefined) return `<span class="confidence-badge confidence-na">Not established</span>`; const label = artifact.confidence_label || (artifact.confidence_score >= .85 ? "HIGH" : artifact.confidence_score >= .65 ? "MEDIUM" : artifact.confidence_score >= .4 ? "LOW" : "UNRELIABLE"); return `<span class="confidence-badge confidence-${label.toLowerCase()}">${label}</span>`; }
function metricCell(value, formatter = numberValue) { return value === null || value === undefined ? "Not established" : formatter(value); }

function setLoading(active) {
	$("#loadingState").hidden = !active;
	if (active) $("#loadingStages").innerHTML = ["Hashing", "Scanning", "Carving", "Integrity analysis", "Reconstruction", "Confidence assessment", "Prioritization"].map((stage) => `<div class="loading-stage"><span>${stage}</span><span>PROCESSING</span></div>`).join("");
}

function renderPipeline() {
	const stages = [["01", "Evidence", "Original bytes"], ["02", "Detection", "JPEG signatures"], ["03", "Carving", "Candidate regions"], ["04", "Reconstruction", "Ordered fragments"], ["05", "Integrity", "Structural validation"], ["06", "Confidence", "Evidence quality"], ["07", "Priority", "Review order"]];
	$("#overviewPipeline").innerHTML = stages.map(([number, name, description]) => `<div class="pipeline-stage"><div class="stage-number">${number}</div><strong>${name}</strong><small>${description}</small></div>`).join("");
}

function renderCaseSummary() {
	const result = state.case;
	const summary = result?.summary || {};
	$("#caseChip").textContent = result?.case_id || "NO ACTIVE CASE";
	$("#overviewCaseName").textContent = result?.name || "No evidence loaded";
	$("#overviewFilename").textContent = result?.source?.filename || "Upload an evidence container to begin";
	$("#overviewCaseId").textContent = result?.case_id || "—";
	$("#overviewStatus").textContent = result?.analysis?.status === "COMPLETED" ? "Analysis complete" : (result?.analysis?.status || "Awaiting evidence");
	$("#metricCandidates").textContent = result ? valueOrUnknown(summary.jpeg_candidates, "0") : "—";
	$("#metricRecovered").textContent = result ? valueOrUnknown(summary.recovered, "0") : "—";
	$("#metricPartial").textContent = result ? valueOrUnknown(summary.partially_recovered, "0") : "—";
	$("#metricUncertain").textContent = result ? valueOrUnknown(summary.uncertain, "0") : "—";
}

function artifactRows(artifacts, compact = false) {
	if (!artifacts.length) return `<tr><td colspan="${compact ? 7 : 8}" class="empty-cell"><div class="empty-state"><strong>${state.case ? "No artifacts yet" : "No artifacts yet"}</strong><span>Analyze an evidence image to populate the investigation inventory.</span>${compact ? "" : "<button class=\"text-button empty-nav\" type=\"button\" data-view=\"evidence\">Go to Evidence →</button>"}</div></td></tr>`;
	return artifacts.map((artifact) => `<tr data-artifact-id="${escapeHtml(artifact.artifact_id)}" tabindex="0" role="button"><td>${escapeHtml(artifact.artifact_id)}</td>${compact ? "" : `<td>${escapeHtml(artifact.filename_guess)}</td>`}<td>${statusBadge(artifact.status)}</td><td>${confidenceBadge(artifact)}</td><td>${metricCell(artifact.priority)}</td><td>${metricCell(artifact.recovery_completeness, percent)}</td><td>${artifact.structural_integrity === null || artifact.structural_integrity === undefined ? "Not established" : artifact.structural_integrity ? "Valid" : "Invalid"}</td>${compact ? "<td>→</td>" : "<td><button class=\"text-button row-action\" type=\"button\">Open →</button></td>"}</tr>`).join("");
}

function renderTables() {
	const sortMultiplier = state.sort === "priority" || state.sort === "confidence" || state.sort === "recovery" || state.sort === "integrity" ? -1 : 1;
	const field = { priority: "priority", confidence: "confidence_score", recovery: "recovery_completeness", integrity: "structural_integrity" }[state.sort];
	const filtered = state.artifacts.filter((artifact) => state.filter === "ALL" || artifact.status === state.filter).sort((a, b) => { const av = a[field]; const bv = b[field]; if (av === null || av === undefined) return 1; if (bv === null || bv === undefined) return -1; return (av - bv) * sortMultiplier || a.artifact_id.localeCompare(b.artifact_id); });
	$("#artifactCount").textContent = `${filtered.length} artifact${filtered.length === 1 ? "" : "s"}`;
	$("#artifactTable").innerHTML = artifactRows(filtered);
	$("#priorityTable").innerHTML = artifactRows(state.artifacts.slice(0, 6), true);
	bindArtifactRows();
}

function bindArtifactRows() { $$("[data-artifact-id]").forEach((row) => { row.addEventListener("click", () => openArtifact(row.dataset.artifactId)); row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openArtifact(row.dataset.artifactId); } }); }); }

function renderEvidence() {
	const source = state.case?.source;
	$("#sourceFilename").textContent = source?.filename || "No source loaded";
	$("#sourceType").textContent = source?.filename?.split(".").pop()?.toUpperCase() || "—";
	$("#sourceSize").textContent = formatBytes(source?.size_bytes);
	$("#sourceStatus").textContent = state.case?.analysis?.status || "Awaiting upload";
	$("#sourceCreated").textContent = formatDate(state.case?.created_at);
	$("#sourceHash").textContent = source?.sha256 || "—";
	$("#copyHashButton").disabled = !source?.sha256;
}

function renderAnalysis() {
	const summary = state.case?.summary || {}; const source = state.case?.source;
	const stages = [["Evidence hash", "Complete", source?.sha256 ? `${source.sha256.slice(0, 16)}…` : "Not established"], ["Signature detection", "Complete", summary.regions_detected !== undefined ? `${summary.regions_detected} candidates detected` : "Not established"], ["Fragment carving", "Complete", state.case ? `${summary.recovered || 0} validated / ${summary.uncertain || 0} unreliable` : "Not established"], ["Reconstruction", "Measured", "Controlled ordering only"], ["Integrity validation", "Complete", state.case ? `${summary.recovered || 0} recovered` : "Not established"], ["Recovery completeness", "Measured", "Not established"], ["Confidence assessment", "Measured", "Not established"], ["Evidence prioritization", "Measured", "Not established"]];
	$("#analysisStages").innerHTML = stages.map(([name, status, result], index) => `<div class="analysis-row"><span class="analysis-number">${String(index + 1).padStart(2, "0")}</span><strong>${name}</strong><p>${status}</p><span class="analysis-result">${escapeHtml(result)}</span></div>`).join("");
}

function renderCaseInfo() {
	if (!state.case) {
		$("#caseMetadata").innerHTML = `<div class="case-empty"><strong>No case information yet</strong><p>Upload and analyze evidence to populate the case record.</p><button class="text-button" data-view="evidence" type="button">Go to Evidence →</button></div>`;
		return;
	}
	const source = state.case?.source; const analysis = state.case?.analysis;
	const rows = [["Case ID", state.case?.case_id], ["Case name", state.case?.name], ["Source filename", source?.filename], ["Evidence size", formatBytes(source?.size_bytes)], ["SHA-256", source?.sha256], ["Created time", formatDate(state.case?.created_at)], ["Analysis started", formatDate(analysis?.started_at)], ["Analysis completed", formatDate(analysis?.completed_at)], ["Analysis status", analysis?.status]];
	$("#caseMetadata").innerHTML = rows.map(([label, value]) => `<div class="metadata-row${label === "SHA-256" ? " hash" : ""}"><span>${label}</span><strong>${escapeHtml(valueOrUnknown(value))}</strong></div>`).join("");
}

function renderOverview() { renderCaseSummary(); renderTables(); renderAnalysis(); renderCaseInfo(); renderEvidence(); }

async function openArtifact(artifactId) {
	try { const artifact = await api(`/api/artifacts/${encodeURIComponent(artifactId)}`); renderArtifactDetail(artifact); navigate("detail"); } catch (error) { showToast(error.message); }
}

function renderArtifactDetail(artifact) {
	$("#detailTitle").textContent = artifact.artifact_id;
	$("#detailSubtitle").textContent = `${artifact.filename_guess} · ${artifact.status}`;
	$("#detailStatus").innerHTML = statusBadge(artifact.status);
	$("#summaryArtifactId").textContent = artifact.artifact_id;
	$("#summaryArtifactStatus").innerHTML = statusBadge(artifact.status);
	$("#detailAssessment").textContent = assessmentSentence(artifact);
	renderDecisionSummary(artifact);
	renderHypotheses(artifact);
	$("#previewMeta").textContent = artifact.output_path || "Preview unavailable";
	const stage = $("#previewStage"); stage.innerHTML = "";
	if (artifact.status === "RECOVERED") { const image = document.createElement("img"); image.src = `${API_BASE}/api/artifacts/${encodeURIComponent(artifact.artifact_id)}/preview`; image.alt = `Recovered preview for ${artifact.artifact_id}`; image.onerror = () => { stage.innerHTML = `<div class="preview-empty"><div class="empty-image-icon">▧</div><strong>Preview unavailable</strong><p>RECON-X could not establish a reliable visual reconstruction for this artifact.</p></div>`; }; stage.appendChild(image); } else { stage.innerHTML = `<div class="preview-empty"><div class="empty-image-icon">▧</div><strong>Preview unavailable</strong><p>RECON-X could not establish a reliable visual reconstruction for this artifact.</p></div>`; }
	$("#detailConfidence").textContent = numberValue(artifact.confidence_score); $("#detailConfidenceLabel").textContent = artifact.confidence_score === null || artifact.confidence_score === undefined ? "NOT ESTABLISHED" : (artifact.confidence_label || "MEASURED"); $("#detailPriority").textContent = numberValue(artifact.priority);
	const metrics = [["Classification", artifact.classification_confidence], ["Structural integrity", artifact.structural_integrity], ["Recovery completeness", artifact.recovery_completeness], ["Fragment consistency", artifact.fragment_consistency]];
	$("#detailMetrics").innerHTML = metrics.map(([label, value]) => `<div class="metric-line"><div class="metric-line-head"><span>${label}</span><strong>${percent(value)}</strong></div><div class="progress-track"><div class="progress-fill" style="width:${value === null || value === undefined ? 0 : value * 100}%"></div></div></div>`).join("");
	const states = artifact.evidence_state || {}; $("#evidenceStateGrid").innerHTML = ["observed", "reconstructed", "inferred", "unknown"].map((key) => `<div class="state-panel state-${key}"><h3>${key.toUpperCase()}</h3>${(states[key] || []).length ? states[key].map((item) => `<p>${escapeHtml(item)}</p>`).join("") : "<p>Not established.</p>"}</div>`).join("");
	renderTrail(artifact);
	renderEvidenceMap(artifact);
	const reasons = []; if (artifact.validation?.header_valid) reasons.push("JPEG signature detected."); else reasons.push("JPEG signature was not fully established."); if (artifact.validation?.structure_valid) reasons.push("JPEG structure validated."); else reasons.push("Structural validation failed."); if (artifact.validation?.decodable) reasons.push("JPEG successfully decoded."); else reasons.push("JPEG could not be established as reliably decodable."); if (artifact.reconstruction?.performed) reasons.push("Artifact was produced by controlled fragment reconstruction."); else if (artifact.status === "RECOVERED") reasons.push("Artifact was extracted as a validated candidate."); if (artifact.recovery_completeness === null) reasons.push("Recovery completeness is not established because the expected original size is unavailable."); $("#whyText").textContent = reasons.join(" ");
}

function assessmentSentence(artifact) {
	if (artifact.status === "RECONSTRUCTED") return "Multiple evidence fragments were combined and the resulting artifact passed deterministic validation.";
	if (artifact.status === "UNRELIABLE") return "The recovered bytes are insufficient to establish a trustworthy artifact.";
	if (artifact.status === "PARTIAL") return "Some evidence was recovered, but a complete artifact could not be established.";
	if (artifact.reconstruction?.performed && artifact.validation?.structure_valid) return "Multiple evidence fragments were combined and the resulting artifact passed deterministic validation.";
	if (artifact.validation?.decodable && artifact.recovery_completeness === null) return "The file can be decoded, but exact recovery completeness cannot be established from the available evidence.";
	if (artifact.validation?.structure_valid) return "JPEG structure is valid and the file can be decoded.";
	return "The recovered bytes are insufficient to establish a trustworthy artifact.";
}

function factItem(text, kind = "known") { return `<div class="decision-fact ${kind}"><span aria-hidden="true">${kind === "known" ? "✓" : "?"}</span><p>${escapeHtml(text)}</p></div>`; }

function renderDecisionSummary(artifact) {
	const known = [];
	if (artifact.validation?.header_valid) known.push("JPEG signature detected.");
	if (artifact.validation?.footer_valid) known.push("Candidate boundary detected.");
	if (artifact.validation?.structure_valid) known.push("JPEG structure is valid.");
	if (artifact.validation?.decodable) known.push("File decoded successfully.");
	if (artifact.recovered_size_bytes !== null && artifact.recovered_size_bytes !== undefined) known.push(`Recovered byte size: ${formatBytes(artifact.recovered_size_bytes)}.`);
	if (artifact.evidence_offsets) known.push(`Observed evidence offsets: ${artifact.evidence_offsets.start} → ${artifact.evidence_offsets.end}.`);
	const unknown = [...(artifact.evidence_state?.unknown || [])];
	if (artifact.recovery_completeness === null || artifact.recovery_completeness === undefined) unknown.push("Recovery completeness unavailable.");
	if (artifact.fragment_consistency === null || artifact.fragment_consistency === undefined) unknown.push("Fragment ordering/consistency unavailable.");
	$("#knownFacts").innerHTML = known.length ? known.map((item) => factItem(item)).join("") : factItem("No measured facts available.", "unknown");
	$("#unknownFacts").innerHTML = unknown.length ? [...new Set(unknown)].map((item) => factItem(item, "unknown")).join("") : factItem("No open questions recorded.", "known");
	$("#systemConclusion").textContent = assessmentSentence(artifact);
}

function renderHypotheses(artifact) {
	const hypotheses = artifact.hypotheses || [];
	const section = $("#hypothesisSection");
	section.hidden = hypotheses.length === 0;
	if (!hypotheses.length) return;
	$("#hypothesisList").innerHTML = hypotheses.map((hypothesis) => {
		const statusClass = hypothesis.status.toLowerCase();
		const chain = hypothesis.fragment_ids.map(escapeHtml).join(" → ");
		const explanation = hypothesis.status === "SUPPORTED" ? "Fragments were combined and deterministic validation passed." : hypothesis.status === "PARTIAL" ? "Available evidence could not establish a complete reconstruction." : "Compatibility was insufficient or deterministic validation failed.";
		return `<article class="hypothesis-card hypothesis-${statusClass}"><div class="hypothesis-chain"><strong>${chain}</strong><span class="hypothesis-status">${escapeHtml(hypothesis.status)}</span></div><div class="hypothesis-score">Fragment Compatibility Score: <strong>${Math.round(hypothesis.compatibility_score * 100)}%</strong></div><div class="hypothesis-flow">AI relationship signal <span>↓</span> reconstruction hypothesis <span>↓</span> deterministic validation</div><p>${escapeHtml(explanation)}</p>${hypothesis.contradiction ? `<div class="hypothesis-contradiction">Contradicted: high compatibility did not survive deterministic validation.</div>` : ""}</article>`;
	}).join("");
}

function renderTrail(artifact) {
	const details = artifact.fragment_details || [];
	const observed = [
		...(artifact.evidence_state?.observed || []),
		...details.map((fragment) => `${fragment.fragment_id}: offset ${fragment.offset_start} → ${fragment.offset_end} (${fragment.size_bytes} bytes).`),
		artifact.validation ? `Validation: header ${artifact.validation.header_valid ? "valid" : "invalid"}, footer ${artifact.validation.footer_valid ? "valid" : "invalid"}, decodable ${artifact.validation.decodable ? "yes" : "no"}.` : "",
	].filter(Boolean);
	const reconstruction = artifact.reconstruction?.performed
		? [`Method: ${artifact.reconstruction.method || "Not established"}.`, `Fragments combined: ${artifact.reconstruction.fragment_ids.join(", ") || "Not established"}.`, `Chunk order: ${artifact.reconstruction.chunk_indexes.join(" → ") || "Not established"}.`, `Output size: ${formatBytes(artifact.reconstruction.output_size_bytes)}.`]
		: ["No reconstruction was performed for this artifact.", "Available runtime evidence was retained as an observed carved candidate."];
	const inferred = [`Artifact classification/status: ${artifact.status}.`, artifact.confidence_score !== null && artifact.confidence_score !== undefined ? `Confidence score: ${numberValue(artifact.confidence_score)}.` : "Confidence label: Not established.", artifact.priority !== null && artifact.priority !== undefined ? `Evidence priority: ${numberValue(artifact.priority)}.` : "Evidence priority: Not established."];
	const unknown = artifact.evidence_state?.unknown || [];
	const panels = [["OBSERVED", "Directly measured from evidence.", observed, "trail-observed"], ["RECONSTRUCTED", "Produced by combining available fragments.", reconstruction, "trail-reconstructed"], ["INFERRED", "Conclusions derived from measurements.", inferred, "trail-inferred"], ["UNKNOWN", "Not established by available evidence.", unknown.length ? unknown : ["Not established."], "trail-unknown"]];
	$("#trailGrid").innerHTML = panels.map(([title, subtitle, items, className]) => `<section class="trail-panel ${className}"><h3>${title}</h3><p class="trail-subtitle">${subtitle}</p>${items.map((item) => `<div class="trail-item">${escapeHtml(item)}</div>`).join("")}</section>`).join("");
}

function renderEvidenceMap(artifact) {
	const fragments = (artifact.fragment_details || []).filter((fragment) => Number.isFinite(fragment.offset_start) && Number.isFinite(fragment.offset_end));
	if (!fragments.length) { $("#evidenceMap").innerHTML = `<div class="map-empty">Evidence location not established.</div>`; return; }
	const start = Math.min(...fragments.map((fragment) => fragment.offset_start));
	const end = Math.max(...fragments.map((fragment) => fragment.offset_end));
	const span = Math.max(end - start, 1);
	const regions = fragments.map((fragment) => { const left = ((fragment.offset_start - start) / span) * 100; const width = Math.max(((fragment.offset_end - fragment.offset_start) / span) * 100, 2); return `<div class="map-region ${fragment.status === "VALIDATED" ? "map-valid" : "map-uncertain"}" style="left:${left}%;width:${width}%" title="${escapeHtml(fragment.fragment_id)}: ${fragment.offset_start} to ${fragment.offset_end}"><span>${escapeHtml(fragment.fragment_id)}</span></div>`; }).join("");
	$("#evidenceMap").innerHTML = `<div class="map-label"><span>Evidence image region</span><code>${start} → ${end}</code></div><div class="map-track">${regions}</div><div class="map-legend"><span><i class="legend-region"></i>Observed region</span><span><i class="legend-gap"></i>Unmapped / unknown</span></div><div class="map-caption">Offsets are byte positions in the uploaded evidence. No unobserved regions are interpreted.</div>`;
}

function navigate(view) { state.view = view; $$(".view").forEach((section) => section.classList.toggle("active", section.id === `view-${view}`)); $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view || (view === "detail" && item.dataset.view === "artifacts"))); $("#breadcrumbView").textContent = { overview: "Overview", evidence: "Evidence", artifacts: "Artifacts", detail: "Artifact detail", analysis: "Analysis", case: "Case information" }[view]; $("#sidebar").classList.remove("open"); window.scrollTo({ top: 0, left: 0, behavior: "auto" }); }

async function uploadEvidence(file) { if (!file) return; clearError(); state.selectedFile = file; $("#selectedFile").hidden = false; $("#selectedFile").textContent = `${file.name} · ${formatBytes(file.size)} · ${file.type || "binary evidence"}`; $("#analyzeButton").disabled = true; try { const form = new FormData(); form.append("file", file); const created = await api("/api/cases", { method: "POST", body: form }); state.case = { case_id: created.case_id, name: "RECON-X Case", source: created, analysis: { status: "CREATED" }, summary: {}, artifacts: [] }; renderOverview(); navigate("evidence"); $("#analyzeButton").disabled = false; showToast("Evidence uploaded. Ready for analysis."); } catch (error) { $("#analyzeButton").disabled = true; showError(error.message); } }

async function analyzeCase() { if (!state.case?.case_id) { showError("Upload evidence before starting analysis."); return; } clearError(); setLoading(true); try { state.case = await api(`/api/cases/${encodeURIComponent(state.case.case_id)}/analyze`, { method: "POST" }); const details = await api(`/api/cases/${encodeURIComponent(state.case.case_id)}/artifacts`); state.artifacts = details.artifacts || []; renderOverview(); setLoading(false); navigate("overview"); showToast("Analysis complete."); } catch (error) { setLoading(false); showError(error.message); showToast("Analysis could not be completed."); } }

function bindEvents() {
	document.addEventListener("click", (event) => { const element = event.target.closest("[data-view]"); if (element) navigate(element.dataset.view); });
	$("#menuButton").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
	$("#selectFileButton").addEventListener("click", () => $("#fileInput").click()); $("#dropZone").addEventListener("click", (event) => { if (event.target.closest("button")) return; $("#fileInput").click(); }); $("#dropZone").addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") $("#fileInput").click(); }); $("#fileInput").addEventListener("change", (event) => uploadEvidence(event.target.files[0])); $("#analyzeButton").addEventListener("click", analyzeCase);
	["dragenter", "dragover"].forEach((name) => $("#dropZone").addEventListener(name, (event) => { event.preventDefault(); $("#dropZone").classList.add("dragover"); })); ["dragleave", "drop"].forEach((name) => $("#dropZone").addEventListener(name, (event) => { event.preventDefault(); $("#dropZone").classList.remove("dragover"); })); $("#dropZone").addEventListener("drop", (event) => uploadEvidence(event.dataTransfer.files[0]));
	$$(".filter-button").forEach((button) => button.addEventListener("click", () => { $$(".filter-button").forEach((item) => item.classList.remove("active")); button.classList.add("active"); state.filter = button.dataset.filter; renderTables(); })); $("#sortSelect").addEventListener("change", (event) => { state.sort = event.target.value; renderTables(); });
	$("#copyHashButton").addEventListener("click", async () => { if (!state.case?.source?.sha256) return; await navigator.clipboard.writeText(state.case.source.sha256); $("#copyConfirmation").textContent = "Copied to clipboard"; window.setTimeout(() => { $("#copyConfirmation").textContent = ""; }, 2200); });
}

function init() { $("#topbarDate").textContent = new Date().toLocaleDateString([], { dateStyle: "medium" }); renderPipeline(); bindEvents(); renderOverview(); }
document.addEventListener("DOMContentLoaded", init);
