const API = "http://127.0.0.1:8000/api";
const AUTH_TOKEN_KEY = "infobank_access_token";
const AUTH_USER_KEY = "infobank_user_id";

let CURRENT_USER_ID = "";
let ACCESS_TOKEN = "";
const DOCUMENT_CAPABILITIES = new Map();
let AUTHORIZED_SOURCE_OBJECT_URL = null;

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function authHeaders(extra = {}) {
    return { ...extra, 'Authorization': `Bearer ${ACCESS_TOKEN}` };
}

async function readApiResponse(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const normalized = InfoBankAuthValidation.normalizeApiError(data, response.status);
        const suffix = normalized.errorId ? ` (error ID: ${normalized.errorId})` : '';
        const error = new Error(normalized.message + suffix);
        error.fieldErrors = normalized.fieldErrors;
        error.status = response.status;
        throw error;
    }
    return data;
}

function saveSession(userId, token) {
    CURRENT_USER_ID = userId;
    ACCESS_TOKEN = token;
    sessionStorage.setItem(AUTH_USER_KEY, userId);
    sessionStorage.setItem(AUTH_TOKEN_KEY, token);
}

function clearSession() {
    CURRENT_USER_ID = "";
    ACCESS_TOKEN = "";
    sessionStorage.removeItem(AUTH_USER_KEY);
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    resetSessionScopedUI();
}

function resetChatView() {
    const chat = document.getElementById('view-chat');
    if (!chat) return;
    chat.innerHTML = `
        <div class="flex justify-start w-full">
            <div class="bg-gray-100 border border-gray-200 p-4 rounded-2xl rounded-tl-none max-w-[80%] md:max-w-2xl text-gray-700 shadow-sm text-sm">
                Hello! I am your InfoBank Assistant. I only answer based on your uploaded documents. How can I help?
            </div>
        </div>`;
}

function resetSessionScopedUI() {
    DOCUMENT_CAPABILITIES.clear();
    lastPolicyTargetUserId = null;
    document.body.classList.remove('reviewer-evidence-mode');
    for (const id of [
        'log-email', 'log-pass', 'reg-name', 'reg-email', 'reg-pass',
        'prof-full-name', 'prof-email', 'prof-avatar-url',
        'policy-doc-id', 'policy-target-username', 'policy-valid-from', 'policy-valid-until',
        'transferDocId', 'transferUsernameInput',
    ]) {
        const element = document.getElementById(id);
        if (element) element.value = '';
    }
    const purpose = document.getElementById('policy-purpose');
    if (purpose) purpose.value = 'grounded_question_answering';
    const policyMode = document.getElementById('policy-access-mode');
    if (policyMode) policyMode.value = 'Full';
    const grantType = document.getElementById('policy-grant-type');
    if (grantType) grantType.value = 'Reader';
    const uploadPermission = document.getElementById('upload-permission');
    if (uploadPermission) uploadPermission.value = 'Owner';
    const docsBody = document.getElementById('docs-tbody');
    if (docsBody) docsBody.innerHTML = '';
    const policyResult = document.getElementById('policy-review-output');
    if (policyResult) policyResult.textContent = 'Select a document from the Documents screen or enter its UUID.';
    const actionResult = document.getElementById('action-review-output');
    if (actionResult) actionResult.textContent = 'No evidence loaded.';
    const transferResults = document.getElementById('transferResults');
    if (transferResults) {
        transferResults.innerHTML = '';
        transferResults.classList.add('hidden');
    }
    const profileModal = document.getElementById('profile-modal');
    if (profileModal) profileModal.classList.add('hidden');
    const transferModal = document.getElementById('transferModal');
    if (transferModal) transferModal.classList.add('hidden');
    closeAuthorizedSource();
    const username = document.getElementById('sidebar-display-username');
    if (username) username.innerText = 'Username';
    const fullname = document.getElementById('sidebar-display-fullname');
    if (fullname) {
        fullname.innerText = 'Full Name';
        fullname.classList.add('hidden');
    }
    if (document.getElementById('upload-file')) resetUploadUX();
    resetChatView();
    syncPolicyEditorForDocument();
}

function showAppShell() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('app-wrapper').classList.remove('hidden');
}

function showLoginScreen() {
    document.getElementById('app-wrapper').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
}

function normalizeRightsUI() {
    const uploadSelect = document.getElementById('upload-permission');
    if (uploadSelect) {
        const readerOption = uploadSelect.querySelector('option[value="Reader"]');
        if (readerOption) readerOption.remove();
    }
}

async function restoreSession() {
    normalizeRightsUI();

    if (await loadReviewerDemoSeed()) return;

    const legacyLogoutBtn = document.querySelector('button[onclick="location.reload()"]');
    if (legacyLogoutBtn) legacyLogoutBtn.onclick = logout;

    const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
    const userId = sessionStorage.getItem(AUTH_USER_KEY);
    if (!token || !userId) {
        clearSession();
        showLoginScreen();
        return;
    }

    CURRENT_USER_ID = userId;
    ACCESS_TOKEN = token;
    const ok = await loadProfile();
    if (ok) {
        await loadDocs();
        switchView('chat');
        showAppShell();
    }
    else {
        clearSession();
        showLoginScreen();
    }
}

function logout() {
    clearSession();
    showLoginScreen();
}

function roleBadge(role) {
    const normalized = role || 'contextual';
    const classes = {
        'primary': 'bg-green-50 text-green-700 border-green-200',
        'aggregate-only': 'bg-amber-50 text-amber-700 border-amber-200',
        'contextual': 'bg-blue-50 text-blue-700 border-blue-200',
        'analogical': 'bg-purple-50 text-purple-700 border-purple-200',
        'contrastive': 'bg-gray-100 text-gray-700 border-gray-300',
        'governance-excluded': 'bg-red-50 text-red-700 border-red-200'
    };
    return `<span class="px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-wide ${classes[normalized] || classes.contextual}">${escapeHtml(normalized)}</span>`;
}

function renderRoleSummary(summary) {
    if (!summary || Object.keys(summary).length === 0) return '';
    return Object.entries(summary).map(([role, count]) => `${roleBadge(role)}<span class="text-[10px] text-gray-400 ml-1 mr-2">x${count}</span>`).join('');
}

function levelLabel(level) { return String(level).replaceAll('_', '/'); }

function renderLevelSummary(summary) {
    if (!summary || Object.keys(summary).length === 0) return '<span class="text-gray-400">N/A</span>';
    return Object.entries(summary).map(([level, score]) => {
        const pct = Math.round(Number(score || 0) * 100);
        return `
            <div class="flex items-center gap-2">
                <span class="w-28 capitalize">${escapeHtml(levelLabel(level))}</span>
                <div class="flex-1 h-1.5 rounded-full bg-slate-200 overflow-hidden">
                    <div class="h-full bg-slate-500" style="width:${pct}%"></div>
                </div>
                <span class="w-8 text-right text-slate-500">${pct}</span>
            </div>`;
    }).join('');
}

function renderSourceProfile(profile) {
    if (!profile) return '';
    const genres = (profile.genre || []).join(', ') || 'N/A';
    const speechActs = (profile.speech_acts || []).join(', ') || 'N/A';
    const temporal = (profile.temporal_status || []).join(', ') || 'N/A';
    const warnings = (profile.evidence_warnings || []).join(', ') || 'none';
    const levels = renderLevelSummary(profile.levels || {});
    return `
        <details class="mt-2 bg-white/70 border border-slate-200 rounded-lg p-2">
            <summary class="cursor-pointer text-[10px] font-bold text-slate-500 uppercase tracking-wide">Full usable relevance profile</summary>
            <div class="mt-2 grid gap-1 text-[10px] text-slate-600">
                <div><b>Genre:</b> ${escapeHtml(genres)}</div>
                <div><b>Speech act / perlocutionary:</b> ${escapeHtml(speechActs)}</div>
                <div><b>Temporal/status:</b> ${escapeHtml(temporal)}</div>
                <div><b>Evidence warnings:</b> ${escapeHtml(warnings)}</div>
                <div class="mt-2 space-y-1">${levels}</div>
            </div>
        </details>`;
}

function humanizeTraceValue(value) {
    return String(value || 'not recorded').replaceAll('_', ' ').toLowerCase();
}

function routingPresentation(res) {
    const profile = res.query_profile || {};
    const trace = profile.routing_trace || res.governance?.routing_trace || {};
    const selector = profile.keyword_selection_trace || {};
    const mode = trace.mode || 'NOT_RUN';
    const fallbackUsed = trace.fallback_used === true;
    let effectivePath = 'NOT_RUN';
    if (fallbackUsed) effectivePath = 'PERMITTED_CORPUS_FALLBACK';
    else if (mode === 'ROUTING_OFF') effectivePath = 'FULL_PERMITTED_CORPUS';
    else if (mode === 'KEYWORD_ROUTING') effectivePath = 'KEYWORD_NARROWING';

    const selectedKeywords = Array.isArray(trace.selected_keywords)
        ? trace.selected_keywords
        : (Array.isArray(res.extracted_keywords) ? res.extracted_keywords : []);
    const governedCount = Number(trace.governed_input_count);
    const candidateCount = Number(trace.candidate_set_size);
    const hasCandidateCounts = Number.isFinite(governedCount) && Number.isFinite(candidateCount);
    const candidateEffect = hasCandidateCounts
        ? `${candidateCount}/${governedCount} retained${candidateCount === governedCount ? ' (no reduction)' : ''}`
        : 'not recorded';
    return {
        mode,
        effectivePath,
        selectedKeywords: selectedKeywords.length ? selectedKeywords.join(', ') : 'none selected',
        candidateEffect,
        fallbackReason: fallbackUsed ? humanizeTraceValue(trace.fallback_reason) : 'not applicable',
        selectorOutcome: humanizeTraceValue(selector.outcome),
    };
}

function renderGovernanceTrace(res) {
    const profile = res.query_profile || {};
    const gov = res.governance || {};
    const roleSummary = renderRoleSummary(res.source_role_summary);
    const lexicalTerms = (profile.lexical_terms || []).join(', ') || 'N/A';
    const semanticTags = (profile.semantic_tags || []).join(', ') || 'N/A';
    const expectedGenres = (profile.expected_genres || []).join(', ') || 'N/A';
    const taskIntent = profile.task_intent || 'general_document_question';
    const retrievalStrategy = profile.retrieval_strategy || 'N/A';
    const routing = routingPresentation(res);
    const metadataCount = Number.isFinite(Number(gov.metadata_only_source_count))
        ? Number(gov.metadata_only_source_count)
        : (gov.metadata_only_doc_ids || []).length;
    const levelSummary = renderLevelSummary(res.relevance_level_summary);
    return `
        <div class="mt-4 bg-slate-50 border border-slate-200 rounded-xl p-3 text-[11px] text-slate-600">
            <div class="font-bold text-slate-700 mb-2 flex items-center gap-2">
                <i class="fas fa-shield-alt text-blue-500"></i>
                Usable Relevance Trace
            </div>
            <div class="grid gap-1">
                <div><b>Task intent:</b> ${escapeHtml(taskIntent)}</div>
                <div><b>Retrieval strategy:</b> ${escapeHtml(retrievalStrategy)}</div>
                <div><b>Routing configured:</b> ${escapeHtml(routing.mode)}</div>
                <div><b>Effective routing path:</b> ${escapeHtml(routing.effectivePath)}</div>
                <div><b>Candidate-set effect:</b> ${escapeHtml(routing.candidateEffect)}</div>
                <div><b>Fallback reason:</b> ${escapeHtml(routing.fallbackReason)}</div>
                <div><b>Keyword selector outcome:</b> ${escapeHtml(routing.selectorOutcome)}</div>
                <div><b>Lexical signals:</b> ${escapeHtml(lexicalTerms)}</div>
                <div><b>Semantic tags:</b> ${escapeHtml(semanticTags)}</div>
                <div><b>Expected genres:</b> ${escapeHtml(expectedGenres)}</div>
                <div><b>Source roles:</b> ${roleSummary || '<span class="text-gray-400">N/A</span>'}</div>
                <div><b>Metadata-only sources:</b> ${metadataCount}</div>
                <div><b>Governance:</b> enforced; restricted-source details withheld</div>
                <details class="mt-2">
                    <summary class="cursor-pointer font-bold text-slate-500">Nine-level relevance summary</summary>
                    <div class="mt-2 space-y-1">${levelSummary}</div>
                </details>
            </div>
        </div>`;
}

function renderAnswerReviewHeader(res) {
    const evidence = res.evidence_check || {};
    const failure = res.controlled_failure || evidence.controlled_failure || {};
    const nextStep = (failure.nextSteps || [])[0] || 'Open a cited source page before relying on the answer.';
    return `<div class="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3 text-[10px]" data-reviewer-field="answer-audit-summary">
        <span class="bg-indigo-50 text-indigo-800 rounded px-2 py-1"><b>Output:</b> ${escapeHtml(res.output_mode || 'UNCLASSIFIED')}</span>
        <span class="bg-emerald-50 text-emerald-800 rounded px-2 py-1"><b>Evidence:</b> ${escapeHtml(evidence.decision || 'not evaluated')}</span>
        <span class="bg-slate-100 text-slate-700 rounded px-2 py-1"><b>Audit:</b> ${escapeHtml(res.audit_id || 'N/A')}</span>
        <span class="bg-amber-50 text-amber-800 rounded px-2 py-1"><b>Next:</b> ${escapeHtml(nextStep)}</span>
    </div>`;
}

function renderSourceBlocks(sources, expanded = false) {
    if (!sources || sources.length === 0) return '';
    const srcBlocks = sources.map(src => `
        <div class="bg-gray-50 p-3 rounded-lg text-xs text-gray-600 border border-gray-200 shadow-sm">
            <div class="font-bold text-gray-700 mb-1 flex items-center gap-2 flex-wrap">
                <i class="far fa-file-pdf text-red-500"></i> ${escapeHtml(src.file_name)}
                ${roleBadge(src.role)}
                <span class="px-2 py-0.5 rounded-full bg-white border text-[10px] text-gray-500 uppercase" data-reviewer-field="permission-badge">${escapeHtml(src.use_decision || src.citation?.effective_use_decision || 'unknown')}</span>
            </div>
            <div class="text-[10px] text-slate-500 mb-1" data-reviewer-field="page-message-citation">Document ${escapeHtml(src.citation?.document_id || src.document_id || 'N/A')} · page/message ${escapeHtml(src.citation?.page_number || 'N/A')} · chunk ${escapeHtml(src.citation?.chunk_id || 'N/A')}</div>
            ${src.citation?.source_view_url && src.use_decision !== 'aggregate' ? `<button onclick="openAuthorizedSource('${escapeHtml(src.citation.source_view_url)}')" class="mb-2 text-blue-600 font-bold" aria-label="Open cited source page">Open cited source page</button>` : ''}
            <div class="italic leading-relaxed max-h-24 overflow-y-auto pr-1 text-[11px] whitespace-pre-wrap">${escapeHtml(src.text)}</div>
            ${renderSourceProfile(src.usable_relevance)}
        </div>`).join('');
    return `<div class="mt-4 pt-3 border-t border-gray-100"><details class="group" ${expanded ? 'open' : ''}><summary class="text-xs text-blue-500 font-bold cursor-pointer list-none flex items-center gap-1 hover:text-blue-700 transition"><i class="fas fa-chevron-down transition-transform duration-300 group-open:rotate-180"></i>View Retrieved Sources & Roles</summary><div class="mt-3 space-y-2">${srcBlocks}</div></details></div>`;
}

function renderAssistantExchange(question, res, { expandedSources = false, replace = false, includeQuestion = true } = {}) {
    const box = document.getElementById('view-chat');
    const formattedText = escapeHtml(res.answer).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    const routing = routingPresentation(res);
    const questionHtml = includeQuestion ? `<div class="flex justify-end w-full mb-2"><div class="bg-blue-600 text-white p-3 px-5 rounded-2xl rounded-tr-none max-w-[80%] md:max-w-3xl shadow-sm text-sm" data-reviewer-field="complete-question">${escapeHtml(question)}</div></div>` : '';
    const exchange = `
        ${questionHtml}
        <div class="flex justify-start w-full mb-2"><div class="bg-white border border-gray-200 p-5 rounded-2xl rounded-tl-none max-w-[80%] md:max-w-3xl text-gray-800 shadow-sm text-sm leading-relaxed">
            ${renderAnswerReviewHeader(res)}
            <div class="flex items-start gap-2 mb-3 pb-3 border-b border-gray-100 text-[10px] text-gray-500 uppercase tracking-widest font-bold" data-reviewer-field="routing-summary"><i class="fas fa-filter text-blue-500 mt-0.5"></i><span>Routing: ${escapeHtml(routing.mode)} → ${escapeHtml(routing.effectivePath)} · selected keywords: ${escapeHtml(routing.selectedKeywords)} · candidate set: ${escapeHtml(routing.candidateEffect)} · fallback: ${escapeHtml(routing.fallbackReason)} · selector: ${escapeHtml(routing.selectorOutcome)}</span></div>
            <p style="white-space: pre-wrap;">${formattedText}</p>${renderGovernanceTrace(res)}${renderSourceBlocks(res.sources, expandedSources)}
        </div></div>`;
    if (replace) box.innerHTML = exchange;
    else box.innerHTML += exchange;
}

const REGISTRATION_FIELDS = {
    username: {inputId: 'reg-name', errorId: 'reg-name-error'},
    email: {inputId: 'reg-email', errorId: 'reg-email-error'},
    password: {inputId: 'reg-pass', errorId: 'reg-pass-error'},
};

function showAuthFeedback(message, type = 'error') {
    const feedback = document.getElementById('auth-feedback');
    if (!feedback) return;
    feedback.textContent = String(message || '');
    feedback.className = `mb-4 rounded-lg border px-4 py-3 text-sm ${
        type === 'success'
            ? 'border-green-200 bg-green-50 text-green-800'
            : 'border-red-200 bg-red-50 text-red-800'
    }`;
    feedback.setAttribute('role', type === 'success' ? 'status' : 'alert');
    feedback.setAttribute('aria-live', type === 'success' ? 'polite' : 'assertive');
}

function clearAuthFeedback() {
    const feedback = document.getElementById('auth-feedback');
    if (!feedback) return;
    feedback.textContent = '';
    feedback.className = 'hidden mb-4 rounded-lg border px-4 py-3 text-sm';
    feedback.setAttribute('role', 'status');
    feedback.setAttribute('aria-live', 'polite');
}

function clearRegistrationFieldError(field) {
    const config = REGISTRATION_FIELDS[field];
    if (!config) return;
    const input = document.getElementById(config.inputId);
    const error = document.getElementById(config.errorId);
    if (input) {
        input.setAttribute('aria-invalid', 'false');
        input.classList.remove('border-red-500', 'focus:ring-red-500');
        input.classList.add('focus:ring-blue-500');
    }
    if (error) {
        error.textContent = '';
        error.classList.add('hidden');
    }
}

function clearRegistrationErrors({clearFeedback = true} = {}) {
    Object.keys(REGISTRATION_FIELDS).forEach(clearRegistrationFieldError);
    if (clearFeedback) clearAuthFeedback();
}

function renderRegistrationErrors(fieldErrors, summary = 'Please correct the highlighted fields.') {
    let firstInvalidInput = null;
    Object.entries(fieldErrors || {}).forEach(([field, messages]) => {
        const config = REGISTRATION_FIELDS[field];
        if (!config || !Array.isArray(messages) || messages.length === 0) return;
        const input = document.getElementById(config.inputId);
        const error = document.getElementById(config.errorId);
        if (input) {
            input.setAttribute('aria-invalid', 'true');
            input.classList.remove('focus:ring-blue-500');
            input.classList.add('border-red-500', 'focus:ring-red-500');
            if (!firstInvalidInput) firstInvalidInput = input;
        }
        if (error) {
            error.textContent = messages.join(' ');
            error.classList.remove('hidden');
        }
    });
    showAuthFeedback(summary, 'error');
    firstInvalidInput?.focus();
}

function prepareRegistrationValidation() {
    document.getElementById('form-register')?.addEventListener('submit', event => {
        event.preventDefault();
        void doRegister();
    });
    Object.entries(REGISTRATION_FIELDS).forEach(([field, config]) => {
        document.getElementById(config.inputId)?.addEventListener('input', () => {
            clearRegistrationFieldError(field);
            if (!document.querySelector('#form-register [aria-invalid="true"]')) clearAuthFeedback();
        });
    });
}

async function doRegister(event) {
    event?.preventDefault();
    const d = {
        username: document.getElementById('reg-name').value.trim(),
        email: document.getElementById('reg-email').value.trim(),
        password: document.getElementById('reg-pass').value
    };
    clearRegistrationErrors();
    const clientErrors = InfoBankAuthValidation.validateRegistration(d);
    if (Object.keys(clientErrors).length) {
        renderRegistrationErrors(clientErrors);
        return false;
    }
    try {
        const r = await fetch(`${API}/register`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(d) });
        await readApiResponse(r);
        toggleAuth();
        showAuthFeedback('Registration successful! You can now log in.', 'success');
    } catch (e) {
        if (e.fieldErrors && Object.keys(e.fieldErrors).length) {
            renderRegistrationErrors(e.fieldErrors);
        } else {
            showAuthFeedback(e.message || 'Registration failed.', 'error');
        }
    }
    return false;
}

async function doLogin() {
    const d = { email: document.getElementById('log-email').value, password: document.getElementById('log-pass').value };
    try {
        const r = await fetch(`${API}/login`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(d) });
        const res = await readApiResponse(r);
        saveSession(res.user_id, res.access_token);
        const profileLoaded = await loadProfile();
        if (!profileLoaded) throw new Error('The authenticated profile could not be loaded.');
        await loadDocs();
        switchView('chat');
        showAppShell();
    } catch (e) {
        if (ACCESS_TOKEN) clearSession();
        showLoginScreen();
        alert(e.message || "Login failed");
    }
}

async function loadProfile() {
    try {
        if (!ACCESS_TOKEN) return false;
        const r = await fetch(`${API}/profile/me`, { headers: authHeaders() });
        const user = await readApiResponse(r);
        document.getElementById('sidebar-display-username').innerText = user.username;
        if(user.full_name) {
            document.getElementById('sidebar-display-fullname').innerText = user.full_name;
            document.getElementById('sidebar-display-fullname').classList.remove('hidden');
        } else {
            document.getElementById('sidebar-display-fullname').classList.add('hidden');
        }
        renderAvatar('sidebar-avatar-container', user.avatar_url, user.username);
        return true;
    } catch(e) {
        console.error("Profile load failed", e);
        return false;
    }
}

async function saveProfile() {
    const btn = document.getElementById('btn-save-profile');
    const data = {
        full_name: document.getElementById('prof-full-name').value,
        email: document.getElementById('prof-email').value,
        avatar_url: document.getElementById('prof-avatar-url').value
    };
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Saving...';
    try {
        const r = await fetch(`${API}/profile/update`, { method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(data) });
        await readApiResponse(r);
        alert("Profile updated successfully!");
        closeProfileModal();
        loadProfile();
    } catch(e) {
        alert("Update failed: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save"></i><span>Save Changes</span>';
    }
}

async function askQuestion() {
    const input = document.getElementById('chat-input');
    const box = document.getElementById('view-chat');
    const btn = document.getElementById('btn-send-chat');
    const q = input.value.trim();
    if(!q) return;

    box.innerHTML += `<div class="flex justify-end w-full mb-2"><div class="bg-blue-600 text-white p-3 px-5 rounded-2xl rounded-tr-none max-w-[80%] md:max-w-3xl shadow-sm text-sm" data-reviewer-field="complete-question">${escapeHtml(q)}</div></div>`;
    input.value = "";
    input.disabled = true;
    btn.disabled = true;
    box.scrollTop = box.scrollHeight;
    showTyping();

    const fd = new FormData();
    fd.append("question", q);
    try {
        const r = await fetch(`${API}/ask`, { method: 'POST', headers: authHeaders(), body: fd });
        const res = await readApiResponse(r);
        removeTyping();
        if (res.status === "success") {
            renderAssistantExchange(q, res, {includeQuestion: false});
        } else if (res.status === "controlled_failure") {
            const trace = renderGovernanceTrace(res);
            box.innerHTML += `<div class="flex justify-start w-full mb-2"><div class="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-2xl max-w-[80%] md:max-w-xl text-red-800 shadow-sm text-sm">${renderAnswerReviewHeader(res)}<h3 class="font-bold mb-1"><i class="fas fa-shield-alt mr-2"></i>Governance Control</h3><p>${escapeHtml(res.message)}</p>${trace}</div></div>`;
        }
    } catch(e) {
        removeTyping();
        box.innerHTML += `<div class="flex justify-start w-full mb-2"><div class="bg-red-50 text-red-800 p-3 rounded-2xl max-w-xl text-sm">Error: ${escapeHtml(e.message || 'Connection Error.')}</div></div>`;
    } finally {
        input.disabled = false;
        btn.disabled = false;
        input.focus();
        box.scrollTop = box.scrollHeight;
    }
}

async function uploadDocument() {
    const fd = new FormData();
    const fileInput = document.getElementById('upload-file');
    if(!fileInput.files[0]) return alert("Please select a file first.");
    fd.append("file", fileInput.files[0]);
    fd.append("permission_type", document.getElementById('upload-permission').value);
    const btn = document.getElementById('btn-upload');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Ingesting...';
    try {
        const r = await fetch(`${API}/upload`, { method: 'POST', headers: authHeaders(), body: fd });
        await readApiResponse(r);
        alert("Document vectorized successfully!");
        await loadDocs();
    } catch(e) {
        alert("Upload failed: " + e.message);
    } finally {
        resetUploadUX();
    }
}

function rightsOptions(currentValue, isOwner) {
    const modes = [
        { value: 'Owner', label: 'Owner / Private' },
        { value: 'Aggregate', label: 'Aggregate' },
        { value: 'Metadata', label: 'Metadata Only' },
    ];
    return modes.map(mode => `<option value="${mode.value}" ${currentValue === mode.value ? 'selected' : ''}>${mode.label}</option>`).join('');
}

async function loadDocs() {
    try {
        const r = await fetch(`${API}/documents/me`, { headers: authHeaders() });
        const data = await readApiResponse(r);
        DOCUMENT_CAPABILITIES.clear();
        data.documents.forEach(doc => DOCUMENT_CAPABILITIES.set(doc.document_id, {
            isOwner: doc.is_owner === true,
            permission: doc.permission,
            visibility: doc.visibility,
        }));
        const tbody = document.getElementById('docs-tbody');
        tbody.innerHTML = "";
        data.documents.forEach(doc => {
            const isOwner = doc.is_owner === true;
            const iconClass = isOwner ? 'fa-trash-alt' : 'fa-unlink';
            const iconTitle = isOwner ? 'Permanent Delete' : 'Unsubscribe';
            const transferBtn = isOwner ? `<button onclick="openTransferModal('${doc.document_id}')" class="text-blue-500 hover:text-blue-700 transition ml-2" title="Transfer ownership" aria-label="Transfer ownership"><i class="fas fa-exchange-alt"></i></button>` : '';
            const lifecycleButtons = isOwner ? `<button onclick="reindexDoc('${doc.document_id}')" class="text-indigo-500 ml-2" title="Re-index document" aria-label="Re-index document"><i class="fas fa-sync"></i></button><button onclick="archiveDoc('${doc.document_id}')" class="text-amber-600 ml-2" title="Archive document" aria-label="Archive document"><i class="fas fa-archive"></i></button><button onclick="restoreDoc('${doc.document_id}')" class="text-green-600 ml-2" title="Restore document" aria-label="Restore document"><i class="fas fa-trash-restore"></i></button>` : '';
            const keywordEditor = isOwner
                ? `<div class="flex items-center space-x-2"><input type="text" id="kw-${doc.document_id}" value="${escapeHtml((doc.keywords || []).join(', '))}" class="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-xs outline-none focus:ring-2 focus:ring-blue-400"><button onclick="saveKW('${doc.document_id}')" class="text-white bg-blue-500 hover:bg-blue-600 rounded-md p-1.5 transition" title="Save reviewed keywords" aria-label="Save reviewed keywords"><i class="fas fa-save"></i></button></div>`
                : `<input type="text" id="kw-${doc.document_id}" value="${escapeHtml((doc.keywords || []).join(', '))}" readonly aria-readonly="true" class="w-full border border-gray-200 bg-gray-100 text-gray-600 rounded-md px-3 py-1.5 text-xs cursor-not-allowed"><div class="mt-1 text-[10px] text-amber-700" data-owner-only="true">Owner review only</div>`;
            const sourceAction = !isOwner && doc.permission === 'Aggregate'
                ? `<span class="text-amber-700" title="Individual source withheld by Aggregate policy" aria-label="Individual source withheld by Aggregate policy"><i class="fas fa-eye-slash"></i></span>`
                : `<button onclick="openAuthorizedSource('/api/documents/${doc.document_id}/source?page=1')" class="text-blue-600" title="${!isOwner && doc.permission === 'Metadata' ? 'Open permitted metadata' : 'Open page 1'}" aria-label="${!isOwner && doc.permission === 'Metadata' ? 'Open permitted metadata' : 'Open page 1'}"><i class="fas fa-external-link-alt"></i></button>`;
            const policyTitle = isOwner ? 'Manage permissions' : 'Resolve effective access';
            const selectId = `perm-${doc.document_id}`;
            const provenance = (doc.provenance || []).map(item => `${item.field}:${item.type}`).slice(0, 4).join(' · ');
            tbody.innerHTML += `
                <tr class="hover:bg-gray-50 transition">
                    <td class="px-6 py-4 text-gray-800"><div class="font-medium"><i class="far fa-file-pdf text-red-500 mr-2"></i>${escapeHtml(doc.file_name)}</div><div class="mt-1 text-[10px] font-mono text-gray-500" data-reviewer-field="document-uuid-hash">UUID ${escapeHtml(doc.document_id)}<br>SHA ${escapeHtml(doc.source_sha256 || 'N/A')}</div><div class="mt-1 text-[10px]">${escapeHtml(doc.processing_status)} · ${escapeHtml(doc.source_status)} · ${escapeHtml(doc.page_count ?? 0)} page · ${escapeHtml(doc.chunk_count ?? 0)} chunk</div></td>
                    <td class="px-6 py-4">${keywordEditor}<div class="text-[10px] text-gray-400 mt-1" data-reviewer-field="provenance">${escapeHtml(provenance || 'No provenance')}</div></td>
                    <td class="px-6 py-4"><select id="${selectId}" data-current="${escapeHtml(doc.permission)}" onchange="savePerm('${doc.document_id}', this.value, this)" ${!isOwner?'disabled':''} class="text-xs border border-gray-300 rounded-md p-2 outline-none ${!isOwner?'opacity-50 cursor-not-allowed bg-gray-100':'bg-white focus:ring-2 focus:ring-blue-400'}">${rightsOptions(doc.permission, isOwner)}</select></td>
                    <td class="px-6 py-4 text-center whitespace-nowrap">${sourceAction}<button onclick="selectPolicyDocument('${doc.document_id}')" class="text-purple-600 ml-2" title="${policyTitle}" aria-label="${policyTitle}"><i class="fas fa-user-shield"></i></button>${lifecycleButtons}<button onclick="deleteDoc('${doc.document_id}', '${isOwner}')" class="text-gray-400 hover:text-red-600 transition ml-2" title="${iconTitle}" aria-label="${iconTitle}"><i class="fas ${iconClass}"></i></button>${transferBtn}</td>
                </tr>`;
        });
        syncPolicyEditorForDocument();
        return true;
    } catch (e) {
        alert("Document list failed: " + e.message);
        DOCUMENT_CAPABILITIES.clear();
        syncPolicyEditorForDocument();
        return false;
    }
}

async function saveKW(id) {
    if (!DOCUMENT_CAPABILITIES.get(id)?.isOwner) return alert('Only the Owner can review document keywords.');
    const fd = new FormData();
    fd.append("doc_id", id);
    fd.append("keywords", document.getElementById('kw-'+id).value);
    try {
        const r = await fetch(`${API}/documents/update-keywords`, { method: 'POST', headers: authHeaders(), body: fd });
        await readApiResponse(r);
        alert("Keywords updated!");
    } catch (e) {
        alert("Keyword update failed: " + e.message);
    }
}

async function savePerm(id, p, selectEl = null) {
    if (!DOCUMENT_CAPABILITIES.get(id)?.isOwner) return alert('Only the Owner can change document visibility.');
    const previous = selectEl?.dataset.current || null;
    if (selectEl) selectEl.disabled = true;
    const fd = new FormData();
    fd.append("doc_id", id);
    fd.append("new_perm", p);
    try {
        const r = await fetch(`${API}/documents/update-permission`, { method: 'POST', headers: authHeaders(), body: fd });
        const data = await readApiResponse(r);
        if (selectEl) selectEl.dataset.current = data.visibility === 'Private' ? 'Owner' : data.visibility;
        alert(`Rights updated to ${data.visibility === 'Private' ? 'Owner / Private' : data.visibility}.`);
        await loadDocs();
    } catch (e) {
        if (selectEl && previous) selectEl.value = previous;
        alert("Permission update failed: " + e.message);
        await loadDocs();
    } finally {
        if (selectEl) selectEl.disabled = false;
    }
}

async function deleteDoc(id, isOwnerStr) {
    const isOwner = isOwnerStr === 'true';
    if (!confirm(isOwner ? "WARNING: Permanently delete document and AI vectors?" : "Unsubscribe from document?")) return;
    const fd = new FormData();
    fd.append("doc_id", id);
    try {
        const r = await fetch(`${API}/documents/delete`, { method: 'DELETE', headers: authHeaders(), body: fd });
        await readApiResponse(r);
        await loadDocs();
        loadMap();
    } catch(e) {
        alert("Delete failed: " + e.message);
    }
}

async function documentLifecycle(id, action) {
    try {
        const r = await fetch(`${API}/documents/${id}/${action}`, {method: 'POST', headers: authHeaders()});
        await readApiResponse(r);
        await loadDocs();
    } catch (e) { alert(`${action} failed: ${e.message}`); }
}

function reindexDoc(id) { return documentLifecycle(id, 'reindex'); }
function archiveDoc(id) { return documentLifecycle(id, 'archive'); }
function restoreDoc(id) { return documentLifecycle(id, 'restore'); }

function closeAuthorizedSource() {
    const modal = document.getElementById('source-viewer-modal');
    const frame = document.getElementById('source-viewer-frame');
    if (frame) {
        frame.removeAttribute('src');
        frame.classList.add('hidden');
    }
    if (AUTHORIZED_SOURCE_OBJECT_URL) {
        URL.revokeObjectURL(AUTHORIZED_SOURCE_OBJECT_URL);
        AUTHORIZED_SOURCE_OBJECT_URL = null;
    }
    if (modal) modal.classList.add('hidden');
}

async function openAuthorizedSource(path) {
    const modal = document.getElementById('source-viewer-modal');
    const loading = document.getElementById('source-viewer-loading');
    const textView = document.getElementById('source-viewer-text');
    const frame = document.getElementById('source-viewer-frame');
    if (!modal || !loading || !textView || !frame) return alert('The authorized source viewer is unavailable.');
    closeAuthorizedSource();
    modal.classList.remove('hidden');
    loading.classList.remove('hidden');
    textView.classList.add('hidden');
    textView.textContent = '';
    try {
        const url = path.startsWith('/api/') ? `${API.replace('/api', '')}${path}` : `${API}${path}`;
        const r = await fetch(url, {headers: authHeaders()});
        if (!r.ok) {
            const data = await r.json().catch(() => ({}));
            throw new Error(data.error?.message || data.detail || `HTTP ${r.status}`);
        }
        const type = r.headers.get('content-type') || '';
        if (type.includes('application/json')) {
            const data = await r.json();
            textView.textContent = data.text || JSON.stringify(data, null, 2);
            textView.classList.remove('hidden');
        } else {
            AUTHORIZED_SOURCE_OBJECT_URL = URL.createObjectURL(await r.blob());
            frame.src = AUTHORIZED_SOURCE_OBJECT_URL;
            frame.classList.remove('hidden');
        }
    } catch (e) {
        textView.textContent = `Source open failed: ${e.message}`;
        textView.classList.remove('hidden');
    } finally {
        loading.classList.add('hidden');
    }
}

let lastPolicyTargetUserId = null;

function selectPolicyDocument(id) {
    document.getElementById('policy-doc-id').value = id;
    lastPolicyTargetUserId = null;
    syncPolicyEditorForDocument();
    switchView('policy');
}

function handlePolicyDocumentChange() {
    lastPolicyTargetUserId = null;
    syncPolicyEditorForDocument();
}

function selectedPolicyCapability() {
    const docId = document.getElementById('policy-doc-id')?.value.trim();
    return docId ? DOCUMENT_CAPABILITIES.get(docId) : null;
}

function syncPolicyEditorForDocument() {
    const docId = document.getElementById('policy-doc-id')?.value.trim() || '';
    const capability = selectedPolicyCapability();
    const isOwner = capability?.isOwner === true;
    for (const id of ['policy-owner-permission-editor', 'policy-owner-rule-editor']) {
        const panel = document.getElementById(id);
        if (panel) panel.classList.toggle('hidden', !isOwner);
    }
    const context = document.getElementById('policy-role-context');
    if (!context) return;
    if (!docId) {
        context.textContent = 'Select a document from the Documents screen. Owner-only editors remain hidden until ownership is verified from the current session.';
    } else if (isOwner) {
        context.textContent = 'Owner context verified for this document. Persistent grants, scoped rules, and effective-access resolution are available.';
    } else if (capability) {
        context.textContent = `${capability.permission || 'Reader'} context. You may resolve your effective access; persistent grants and scoped policy edits are Owner-only.`;
    } else {
        context.textContent = 'Ownership is not verified for this document in the current session. Effective access can be resolved, but Owner-only editors remain hidden.';
    }
}

function requireOwnerPolicyContext() {
    if (selectedPolicyCapability()?.isOwner) return true;
    policyOutput({error: 'Only the verified document Owner can change persistent permissions or scoped policy rules.'});
    syncPolicyEditorForDocument();
    return false;
}

function policyOutput(data) {
    document.getElementById('policy-review-output').textContent = JSON.stringify(data, null, 2);
}

async function grantReviewerPermission() {
    if (!requireOwnerPolicyContext()) return;
    const docId = document.getElementById('policy-doc-id').value.trim();
    const fd = new FormData();
    fd.append('target_username', document.getElementById('policy-target-username').value.trim());
    fd.append('permission_type', document.getElementById('policy-grant-type').value);
    try {
        const r = await fetch(`${API}/policy/documents/${docId}/permissions`, {method:'POST', headers:authHeaders(), body:fd});
        const data = await readApiResponse(r);
        lastPolicyTargetUserId = data.target_user_id;
        policyOutput(data);
    } catch(e) { policyOutput({error:e.message}); }
}

async function revokeReviewerPermission() {
    if (!requireOwnerPolicyContext()) return;
    const docId = document.getElementById('policy-doc-id').value.trim();
    if (!lastPolicyTargetUserId) return policyOutput({error:'Grant or change a target first so its opaque user ID is known.'});
    try {
        const r = await fetch(`${API}/policy/documents/${docId}/permissions/${lastPolicyTargetUserId}`, {method:'DELETE', headers:authHeaders()});
        policyOutput(await readApiResponse(r));
    } catch(e) { policyOutput({error:e.message}); }
}

async function resolveReviewerPolicy(showEmpty = true) {
    const docId = document.getElementById('policy-doc-id')?.value.trim();
    if (!docId) { if(showEmpty) policyOutput({status:'Select a document UUID.'}); return; }
    const purpose = encodeURIComponent(document.getElementById('policy-purpose').value || 'grounded_question_answering');
    try {
        const r = await fetch(`${API}/policy/resolve/document/${docId}?purpose=${purpose}`, {headers:authHeaders()});
        policyOutput(await readApiResponse(r));
    } catch(e) { policyOutput({error:e.message}); }
}

async function createReviewerPolicyRule() {
    if (!requireOwnerPolicyContext()) return;
    const fd = new FormData();
    fd.append('target_type', 'Document');
    fd.append('target_id', document.getElementById('policy-doc-id').value.trim());
    fd.append('purpose', document.getElementById('policy-purpose').value || 'any');
    fd.append('access_mode', document.getElementById('policy-access-mode').value);
    const from = document.getElementById('policy-valid-from').value;
    const until = document.getElementById('policy-valid-until').value;
    if(from) fd.append('valid_from', from);
    if(until) fd.append('valid_until', until);
    try {
        const r = await fetch(`${API}/policy/rules`, {method:'POST', headers:authHeaders(), body:fd});
        policyOutput(await readApiResponse(r));
    } catch(e) { policyOutput({error:e.message}); }
}

async function loadReviewerActions() {
    const output = document.getElementById('action-review-output');
    if (!output || !ACCESS_TOKEN) return;
    try {
        const r = await fetch(`${API}/evidence/action-list`, {headers:authHeaders()});
        const data = await readApiResponse(r);
        renderActionEvidencePanel({
            engine_version: data.engine_version,
            closure_states: data.closure_states,
            browser_only_rule: 'contextual evidence cannot create an action by itself',
            counts: data.counts,
            actions: data.actions,
            open_items: data.open_items,
            closed_items: data.closed_items,
            contextual_only: data.contextual_only,
            evidence_roles: ['primary','contextual','contrastive'],
            audit_and_correction: 'Evidence-unit IDs and controlled-failure feedback preserve reviewer traceability.'
        });
    } catch(e) { output.textContent = JSON.stringify({error:e.message}, null, 2); }
}

function renderActionEvidencePanel(data) {
    const output = document.getElementById('action-review-output');
    const actions = data.actions || [...(data.open_items || []), ...(data.closed_items || [])];
    const actionCards = actions.map(item => `
        <div class="rounded-lg border border-slate-700 bg-slate-800 p-3">
            <div class="flex items-center justify-between gap-2"><b>${escapeHtml(item.status || 'UNKNOWN')}</b><span class="text-slate-400">${escapeHtml(item.action_id || item.id || 'N/A')}</span></div>
            <div class="mt-1 text-slate-200">${escapeHtml(item.normalized_action_key || item.action || 'Action evidence')}</div>
            <div class="mt-1 text-slate-400">thread/evidence: ${escapeHtml((item.linked_evidence_ids || item.E || []).join(', ') || item.request_evidence_id || 'N/A')}</div>
            <div class="mt-1 text-slate-400">roles: ${escapeHtml(JSON.stringify(item.R || item.evidence_roles || {}))} · events: ${escapeHtml((item.event_types || []).join(', ') || 'N/A')}</div>
        </div>`).join('');
    const contextual = data.contextual_only || data.contextual_only_evidence_ids || [];
    output.innerHTML = `
        <div class="mb-3 flex flex-wrap gap-2"><span class="rounded bg-green-900/50 px-2 py-1">primary evidence</span><span class="rounded bg-red-900/50 px-2 py-1">contrastive evidence</span><span class="rounded bg-blue-900/50 px-2 py-1">contextual · browser-only · no action</span></div>
        <div class="grid md:grid-cols-2 gap-3">${actionCards || '<div>No action evidence.</div>'}</div>
        <div class="mt-3 border-t border-slate-700 pt-3 text-slate-300"><b>Contextual-only evidence:</b> ${escapeHtml(contextual.map(item => item.id || item).join(', ') || 'none')} · browser-only false actions: ${escapeHtml(data.browser_only_false_actions ?? 0)}</div>
        <div class="mt-1 text-slate-400"><b>Correction / audit trail:</b> ${escapeHtml(data.audit_and_correction || 'Evidence IDs and engine version preserve correction traceability.')} · engine ${escapeHtml(data.engine_version || 'runtime')}</div>`;
}

function renderReviewerDemoDocuments(documents) {
    const tbody = document.getElementById('docs-tbody');
    tbody.innerHTML = '';
    documents.forEach(doc => {
        const provenance = (doc.provenance || []).map(item => `${item.field}:${item.type}`).join(' · ');
        tbody.innerHTML += `<tr class="hover:bg-gray-50 transition">
            <td class="px-6 py-4 text-gray-800"><div class="font-medium">${escapeHtml(doc.file_name)}</div><div class="mt-1 text-[10px] font-mono text-gray-500" data-reviewer-field="document-uuid-hash">UUID ${escapeHtml(doc.document_id)}<br>SHA ${escapeHtml(doc.source_sha256)}</div><div class="mt-1 text-[10px]">${escapeHtml(doc.processing_status)} · ${escapeHtml(doc.source_status)} · ${escapeHtml(doc.page_count)} page · ${escapeHtml(doc.chunk_count)} chunk</div></td>
            <td class="px-6 py-4"><div>${escapeHtml(doc.keywords.join(', '))}</div><div class="text-[10px] text-gray-400 mt-1" data-reviewer-field="provenance">${escapeHtml(provenance)}</div></td>
            <td class="px-6 py-4"><span class="rounded bg-blue-50 px-2 py-1 text-blue-800">${escapeHtml(doc.permission)}</span></td>
            <td class="px-6 py-4 text-center whitespace-nowrap"><button class="text-blue-600" title="Open page 1" aria-label="Open page 1">source</button><button class="text-purple-600 ml-2" title="Review permissions" aria-label="Review permissions">policy</button><button class="text-indigo-600 ml-2" title="Re-index document" aria-label="Re-index document">re-index</button><button class="text-amber-600 ml-2" title="Archive document" aria-label="Archive document">archive</button><button class="text-green-600 ml-2" title="Restore document" aria-label="Restore document">restore</button></td>
        </tr>`;
    });
}

async function loadReviewerDemoSeed() {
    const params = new URLSearchParams(window.location.search);
    const seedPath = params.get('reviewer_demo');
    if (!seedPath || !['127.0.0.1', 'localhost'].includes(window.location.hostname)) return false;
    const response = await fetch(seedPath);
    if (!response.ok) throw new Error(`Reviewer demo seed failed: HTTP ${response.status}`);
    const seed = await response.json();
    document.body.classList.add('reviewer-evidence-mode');
    CURRENT_USER_ID = 'reviewer-demo';
    ACCESS_TOKEN = 'local-demo-no-api';
    showAppShell();
    document.getElementById('sidebar-display-username').innerText = 'reviewer-demo';
    renderAvatar('sidebar-avatar-container', '', 'reviewer-demo');
    renderAssistantExchange(seed.assistant.question, seed.assistant.response, {expandedSources: true, replace: true});
    renderReviewerDemoDocuments(seed.documents);
    DOCUMENT_CAPABILITIES.clear();
    seed.documents.forEach(doc => DOCUMENT_CAPABILITIES.set(doc.document_id, {
        isOwner: true,
        permission: doc.permission,
        visibility: doc.permission,
    }));
    document.getElementById('policy-doc-id').value = seed.policy.document_id;
    document.getElementById('policy-target-username').value = seed.policy.target_username;
    document.getElementById('policy-grant-type').value = seed.policy.persistent_permission;
    document.getElementById('policy-purpose').value = seed.policy.purpose;
    document.getElementById('policy-access-mode').value = seed.policy.selected_rule;
    document.getElementById('policy-valid-from').value = seed.policy.valid_from;
    document.getElementById('policy-valid-until').value = seed.policy.valid_until;
    syncPolicyEditorForDocument();
    policyOutput(seed.policy.effective_resolution);
    renderActionEvidencePanel(seed.actions);
    window.__INFOBANK_REVIEWER_DEMO__ = {version: seed.demo_seed_version, privacy_safe: seed.privacy_safe, source_trace_sha256: seed.source_trace_sha256};
    return true;
}

async function submitTransfer() {
    const docId = document.getElementById('transferDocId').value;
    const newUsername = document.getElementById('transferUsernameInput').value;
    if (!newUsername) return alert("Please select a new owner!");
    if (!confirm(`Are you sure you want to transfer this document to ${newUsername}? This cannot be undone!`)) return;

    const btn = document.getElementById('btn-submit-transfer');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Transferring...';
    const formData = new FormData();
    formData.append("doc_id", docId);
    formData.append("new_username", newUsername);
    try {
        const response = await fetch(`${API}/documents/transfer`, { method: 'POST', headers: authHeaders(), body: formData });
        const result = await readApiResponse(response);
        alert(result.message);
        closeTransferModal();
        await loadDocs();
    } catch (error) {
        console.error("Transfer error:", error);
        alert("Transfer failed: " + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-check"></i><span>Transfer</span>';
    }
}

async function loadMap() {
    try {
        const r = await fetch(`${API}/knowledge-map/me`, { headers: authHeaders() });
        const data = await readApiResponse(r);
        const box = document.getElementById('view-map');
        box.innerHTML = "";
        if (data.map.length === 0) return box.innerHTML = '<div class="text-gray-500">Empty map.</div>';
        data.map.forEach(k => {
            let s = k.count > 3 ? "text-xl font-bold py-3 px-6 shadow-md" : (k.count > 1 ? "text-base font-semibold py-2 px-5" : "text-sm py-2 px-4");
            box.innerHTML += `<span class="${s} bg-white border border-blue-200 text-blue-700 rounded-full hover:scale-110 transition cursor-default shadow-sm m-1">${escapeHtml(k.keyword)} <span class="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full ml-1">${k.count}</span></span>`;
        });
    } catch (e) {
        console.error("Knowledge map failed", e);
    }
}

window.addEventListener('DOMContentLoaded', () => {
    prepareRegistrationValidation();
    restoreSession();
});
