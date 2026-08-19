const API = "http://127.0.0.1:8000/api";
const AUTH_TOKEN_KEY = "infobank_access_token";
const AUTH_USER_KEY = "infobank_user_id";

let CURRENT_USER_ID = "";
let ACCESS_TOKEN = "";

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
        throw new Error(data.detail || data.message || `HTTP ${response.status}`);
    }
    return data;
}

function saveSession(userId, token) {
    CURRENT_USER_ID = userId;
    ACCESS_TOKEN = token;
    localStorage.setItem(AUTH_USER_KEY, userId);
    localStorage.setItem(AUTH_TOKEN_KEY, token);
}

function clearSession() {
    CURRENT_USER_ID = "";
    ACCESS_TOKEN = "";
    localStorage.removeItem(AUTH_USER_KEY);
    localStorage.removeItem(AUTH_TOKEN_KEY);
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

    const legacyLogoutBtn = document.querySelector('button[onclick="location.reload()"]');
    if (legacyLogoutBtn) legacyLogoutBtn.onclick = logout;

    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    const userId = localStorage.getItem(AUTH_USER_KEY);
    if (!token || !userId) {
        clearSession();
        showLoginScreen();
        return;
    }

    CURRENT_USER_ID = userId;
    ACCESS_TOKEN = token;
    const ok = await loadProfile();
    if (ok) showAppShell();
    else {
        clearSession();
        showLoginScreen();
    }
}

function logout() {
    clearSession();
    showLoginScreen();
    const chat = document.getElementById('view-chat');
    if (chat) {
        chat.innerHTML = `
            <div class="flex justify-start w-full">
                <div class="bg-gray-100 border border-gray-200 p-4 rounded-2xl rounded-tl-none max-w-[80%] md:max-w-2xl text-gray-700 shadow-sm text-sm">
                    Hello! I am your InfoBank Assistant. I only answer based on your uploaded documents. How can I help?
                </div>
            </div>`;
    }
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

function renderGovernanceTrace(res) {
    const profile = res.query_profile || {};
    const gov = res.governance || {};
    const roleSummary = renderRoleSummary(res.source_role_summary);
    const lexicalTerms = (profile.lexical_terms || []).join(', ') || 'N/A';
    const semanticTags = (profile.semantic_tags || []).join(', ') || 'N/A';
    const expectedGenres = (profile.expected_genres || []).join(', ') || 'N/A';
    const taskIntent = profile.task_intent || 'general_document_question';
    const retrievalStrategy = profile.retrieval_strategy || 'N/A';
    const deniedCount = (gov.denied_doc_ids || []).length;
    const metadataCount = (gov.metadata_only_doc_ids || []).length;
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
                <div><b>Lexical signals:</b> ${escapeHtml(lexicalTerms)}</div>
                <div><b>Semantic tags:</b> ${escapeHtml(semanticTags)}</div>
                <div><b>Expected genres:</b> ${escapeHtml(expectedGenres)}</div>
                <div><b>Source roles:</b> ${roleSummary || '<span class="text-gray-400">N/A</span>'}</div>
                <div><b>Metadata-only sources:</b> ${metadataCount}</div>
                <div><b>Denied by governance:</b> ${deniedCount}</div>
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

async function doRegister() {
    const d = {
        username: document.getElementById('reg-name').value,
        email: document.getElementById('reg-email').value,
        password: document.getElementById('reg-pass').value
    };
    try {
        const r = await fetch(`${API}/register`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(d) });
        await readApiResponse(r);
        alert("Registration successful! You can now log in.");
        toggleAuth();
    } catch (e) {
        alert(e.message || "Registration failed.");
    }
}

async function doLogin() {
    const d = { email: document.getElementById('log-email').value, password: document.getElementById('log-pass').value };
    try {
        const r = await fetch(`${API}/login`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(d) });
        const res = await readApiResponse(r);
        saveSession(res.user_id, res.access_token);
        showAppShell();
        await loadProfile();
    } catch (e) {
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

function isActionListQuestion(q) {
    const text = q.toLowerCase();
    return (text.includes('current action list') || text.includes('action list') || text.includes('open task') || text.includes('todo'))
        && !text.includes('browser history alone');
}

function evidenceRoleSummary(units) {
    const out = {};
    units.forEach(unit => {
        const role = unit.role || 'contextual';
        out[role] = (out[role] || 0) + 1;
    });
    return out;
}

function evidenceLevelSummary(units) {
    const base = {
        lexical: 0, semantic: 0, ontological: 0, pragmatic: 0, genre: 0,
        perlocutionary: 0, temporal_status: 0, governance: 0, evidential: 0,
    };
    if (!units.length) return base;
    units.forEach(unit => {
        const primary = unit.role === 'primary';
        const contrastive = unit.role === 'contrastive';
        base.lexical += primary ? 0.8 : 0.3;
        base.semantic += primary || contrastive ? 1 : 0.5;
        base.ontological += 1;
        base.pragmatic += 1;
        base.genre += 1;
        base.perlocutionary += primary ? 1 : 0.5;
        base.temporal_status += (unit.classifier?.temporal_status || []).includes('unspecified') ? 0.2 : 1;
        base.governance += unit.policy?.use_decision === 'deny' ? 0 : 1;
        base.evidential += primary ? 1 : (contrastive ? 0.85 : 0.45);
    });
    Object.keys(base).forEach(k => base[k] = Number((base[k] / units.length).toFixed(3)));
    return base;
}

function evidenceSources(units) {
    return units.map(unit => ({
        document_id: unit.id,
        file_name: `${unit.source_type || 'Evidence'} · ${unit.title || 'Untitled'}`,
        role: unit.role || 'contextual',
        use_decision: unit.policy?.use_decision || 'full',
        text: unit.content_summary || '[evidence content unavailable]',
        usable_relevance: {
            levels: evidenceLevelSummary([unit]),
            role: unit.role || 'contextual',
            base_role: unit.citds_source_role || unit.role || 'contextual',
            use_decision: unit.policy?.use_decision || 'full',
            genre: unit.classifier?.genre || unit.signals?.genre || ['evidence_unit'],
            speech_acts: unit.classifier?.speech_acts || unit.signals?.primary || ['informative'],
            temporal_status: unit.classifier?.temporal_status || unit.signals?.temporal_status || ['unspecified'],
            evidence_warnings: unit.classifier?.warnings || [],
        },
    }));
}

function formatActionListFromEvidence(data) {
    const open = data.open_items || [];
    if (!open.length) {
        let suffix = '';
        if ((data.contextual_only || []).length) suffix += ' Contextual/browser-history evidence exists, but it cannot create an action item by itself.';
        if ((data.closed_items || []).length) suffix += ' Some candidate items are already closed or cancelled.';
        return 'I found no open action items supported by primary evidence.' + suffix;
    }
    const items = open.map((item, idx) => {
        let text = `(${idx + 1}) ${item.action || 'Unspecified action'}`;
        if (item.object && !text.includes(item.object)) text += ` (${item.object})`;
        if (item.due) text += ` by ${item.due}`;
        return text;
    });
    return `Your current action list contains ${open.length} open item(s): ${items.join('; ')}.`;
}

async function actionListChatResponse(q) {
    const r = await fetch(`${API}/evidence/action-list`, { headers: authHeaders() });
    const data = await readApiResponse(r);
    const units = data.classified_units || [];
    return {
        status: 'success',
        answer: formatActionListFromEvidence(data),
        extracted_keywords: ['action', 'email', 'calendar'],
        query_profile: {
            lexical_terms: q.toLowerCase().split(/\W+/).filter(Boolean).slice(0, 12),
            semantic_tags: ['action', 'email', 'calendar'],
            task_intent: 'current_action_list',
            retrieval_strategy: 'evidence_reconstruction',
            expected_genres: ['email_or_message', 'calendar_or_schedule', 'activity_trace'],
        },
        governance: {
            source_type: 'evidence_units',
            usable_doc_ids: [],
            denied_doc_ids: [],
            metadata_only_doc_ids: [],
        },
        source_role_summary: evidenceRoleSummary(units),
        relevance_level_summary: evidenceLevelSummary(units),
        evidence_check: {
            decision: (data.open_items || []).length ? 'answer_allowed' : 'controlled_failure_or_no_open_items',
            counts: data.counts || {},
        },
        sources: evidenceSources(units),
    };
}

async function askQuestion() {
    const input = document.getElementById('chat-input');
    const box = document.getElementById('view-chat');
    const btn = document.getElementById('btn-send-chat');
    const q = input.value.trim();
    if(!q) return;

    box.innerHTML += `<div class="flex justify-end w-full mb-2"><div class="bg-blue-600 text-white p-3 px-5 rounded-2xl rounded-tr-none max-w-[80%] md:max-w-2xl shadow-sm text-sm">${escapeHtml(q)}</div></div>`;
    input.value = "";
    input.disabled = true;
    btn.disabled = true;
    box.scrollTop = box.scrollHeight;
    showTyping();

    const fd = new FormData();
    fd.append("question", q);
    try {
        let res;
        if (isActionListQuestion(q)) {
            res = await actionListChatResponse(q);
        } else {
            const r = await fetch(`${API}/ask`, { method: 'POST', headers: authHeaders(), body: fd });
            res = await readApiResponse(r);
        }
        removeTyping();
        if (res.status === "success") {
            const formattedText = escapeHtml(res.answer).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            const governanceTraceHTML = renderGovernanceTrace(res);
            const reviewerHeader = renderAnswerReviewHeader(res);
            let sourcesHTML = "";
            if (res.sources && res.sources.length > 0) {
                const srcBlocks = res.sources.map(src => `
                    <div class="bg-gray-50 p-3 rounded-lg text-xs text-gray-600 border border-gray-200 shadow-sm">
                        <div class="font-bold text-gray-700 mb-1 flex items-center gap-2 flex-wrap">
                            <i class="far fa-file-pdf text-red-500"></i> ${escapeHtml(src.file_name)}
                            ${roleBadge(src.role)}
                            <span class="px-2 py-0.5 rounded-full bg-white border text-[10px] text-gray-500 uppercase" data-reviewer-field="permission-badge">${escapeHtml(src.use_decision || 'unknown')}</span>
                        </div>
                        <div class="text-[10px] text-slate-500 mb-1" data-reviewer-field="page-message-citation">Document ${escapeHtml(src.citation?.document_id || src.document_id || 'N/A')} · page/message ${escapeHtml(src.citation?.page_number || 'N/A')} · chunk ${escapeHtml(src.citation?.chunk_id || 'N/A')}</div>
                        ${src.citation?.source_view_url ? `<button onclick="openAuthorizedSource('${escapeHtml(src.citation.source_view_url)}')" class="mb-2 text-blue-600 font-bold">Open cited source page</button>` : ''}
                        <div class="italic leading-relaxed max-h-24 overflow-y-auto pr-1 text-[11px] whitespace-pre-wrap">${escapeHtml(src.text)}</div>
                        ${renderSourceProfile(src.usable_relevance)}
                    </div>`).join('');
                sourcesHTML = `<div class="mt-4 pt-3 border-t border-gray-100"><details class="group"><summary class="text-xs text-blue-500 font-bold cursor-pointer list-none flex items-center gap-1 hover:text-blue-700 transition"><i class="fas fa-chevron-down transition-transform duration-300 group-open:rotate-180"></i>View Retrieved Sources & Roles</summary><div class="mt-3 space-y-2">${srcBlocks}</div></details></div>`;
            }
            box.innerHTML += `<div class="flex justify-start w-full mb-2"><div class="bg-white border border-gray-200 p-5 rounded-2xl rounded-tl-none max-w-[80%] md:max-w-2xl text-gray-800 shadow-sm text-sm leading-relaxed">${reviewerHeader}<div class="flex items-center space-x-2 mb-3 pb-3 border-b border-gray-100 text-[10px] text-gray-500 uppercase tracking-widest font-bold"><i class="fas fa-filter text-blue-500"></i><span>Semantic Routing: ${escapeHtml(res.extracted_keywords?.join(', ') || 'N/A')}</span></div><p style="white-space: pre-wrap;">${formattedText}</p>${governanceTraceHTML}${sourcesHTML}</div></div>`;
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
        const tbody = document.getElementById('docs-tbody');
        tbody.innerHTML = "";
        data.documents.forEach(doc => {
            const isOwner = doc.is_owner === true;
            const iconClass = isOwner ? 'fa-trash-alt' : 'fa-unlink';
            const iconTitle = isOwner ? 'Permanent Delete' : 'Unsubscribe';
            const transferBtn = isOwner ? `<button onclick="openTransferModal('${doc.document_id}')" class="text-blue-500 hover:text-blue-700 transition ml-2" title="Transfer Ownership"><i class="fas fa-exchange-alt"></i></button>` : '';
            const lifecycleButtons = isOwner ? `<button onclick="reindexDoc('${doc.document_id}')" class="text-indigo-500 ml-2" title="Re-index"><i class="fas fa-sync"></i></button><button onclick="archiveDoc('${doc.document_id}')" class="text-amber-600 ml-2" title="Archive"><i class="fas fa-archive"></i></button><button onclick="restoreDoc('${doc.document_id}')" class="text-green-600 ml-2" title="Restore"><i class="fas fa-trash-restore"></i></button>` : '';
            const selectId = `perm-${doc.document_id}`;
            const provenance = (doc.provenance || []).map(item => `${item.field}:${item.type}`).slice(0, 4).join(' · ');
            tbody.innerHTML += `
                <tr class="hover:bg-gray-50 transition">
                    <td class="px-6 py-4 text-gray-800"><div class="font-medium"><i class="far fa-file-pdf text-red-500 mr-2"></i>${escapeHtml(doc.file_name)}</div><div class="mt-1 text-[10px] font-mono text-gray-500" data-reviewer-field="document-uuid-hash">UUID ${escapeHtml(doc.document_id)}<br>SHA ${escapeHtml(doc.source_sha256 || 'N/A')}</div><div class="mt-1 text-[10px]">${escapeHtml(doc.processing_status)} · ${escapeHtml(doc.source_status)} · ${escapeHtml(doc.page_count ?? 0)} page · ${escapeHtml(doc.chunk_count ?? 0)} chunk</div></td>
                    <td class="px-6 py-4"><div class="flex items-center space-x-2"><input type="text" id="kw-${doc.document_id}" value="${escapeHtml(doc.keywords.join(', '))}" class="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-xs outline-none focus:ring-2 focus:ring-blue-400"><button onclick="saveKW('${doc.document_id}')" class="text-white bg-blue-500 hover:bg-blue-600 rounded-md p-1.5 transition"><i class="fas fa-save"></i></button></div><div class="text-[10px] text-gray-400 mt-1" data-reviewer-field="provenance">${escapeHtml(provenance || 'No provenance')}</div></td>
                    <td class="px-6 py-4"><select id="${selectId}" data-current="${escapeHtml(doc.permission)}" onchange="savePerm('${doc.document_id}', this.value, this)" ${!isOwner?'disabled':''} class="text-xs border border-gray-300 rounded-md p-2 outline-none ${!isOwner?'opacity-50 cursor-not-allowed bg-gray-100':'bg-white focus:ring-2 focus:ring-blue-400'}">${rightsOptions(doc.permission, isOwner)}</select></td>
                    <td class="px-6 py-4 text-center whitespace-nowrap"><button onclick="openAuthorizedSource('/api/documents/${doc.document_id}/source?page=1')" class="text-blue-600" title="Open page 1"><i class="fas fa-external-link-alt"></i></button><button onclick="selectPolicyDocument('${doc.document_id}')" class="text-purple-600 ml-2" title="Permission link"><i class="fas fa-user-shield"></i></button>${lifecycleButtons}<button onclick="deleteDoc('${doc.document_id}', '${isOwner}')" class="text-gray-400 hover:text-red-600 transition ml-2" title="${iconTitle}"><i class="fas ${iconClass}"></i></button>${transferBtn}</td>
                </tr>`;
        });
    } catch (e) {
        alert("Document list failed: " + e.message);
    }
}

async function saveKW(id) {
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

async function openAuthorizedSource(path) {
    try {
        const url = path.startsWith('/api/') ? `${API.replace('/api', '')}${path}` : `${API}${path}`;
        const r = await fetch(url, {headers: authHeaders()});
        if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
        const type = r.headers.get('content-type') || '';
        if (type.includes('application/json')) {
            const data = await r.json();
            const win = window.open('', '_blank');
            win.document.write(`<pre style="white-space:pre-wrap;font-family:system-ui;padding:2rem">${escapeHtml(data.text || JSON.stringify(data, null, 2))}</pre>`);
        } else {
            window.open(URL.createObjectURL(await r.blob()), '_blank');
        }
    } catch (e) { alert(`Source open failed: ${e.message}`); }
}

let lastPolicyTargetUserId = null;

function selectPolicyDocument(id) {
    document.getElementById('policy-doc-id').value = id;
    switchView('policy');
}

function policyOutput(data) {
    document.getElementById('policy-review-output').textContent = JSON.stringify(data, null, 2);
}

async function grantReviewerPermission() {
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
        output.textContent = JSON.stringify({
            closure_states: ['OPEN','CLOSED_COMPLETED','CLOSED_CANCELLED','SUPERSEDED'],
            browser_only_rule: 'contextual evidence cannot create an action by itself',
            counts: data.counts,
            open_items: data.open_items,
            closed_items: data.closed_items,
            contextual_only: data.contextual_only,
            evidence_roles: ['primary','contextual','contrastive'],
            audit_and_correction: 'Evidence-unit IDs and controlled-failure feedback preserve reviewer traceability.'
        }, null, 2);
    } catch(e) { output.textContent = JSON.stringify({error:e.message}, null, 2); }
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

window.addEventListener('DOMContentLoaded', restoreSession);
