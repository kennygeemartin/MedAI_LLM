'use strict';
const $ = (selector) => document.querySelector(selector);
const state = {user: null, conversation: null, busy: false, registering: false, documents: [], library: [], adminTab: 'reports'};
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeURL = (value) => { try {const url = new URL(value); return url.protocol === 'https:' ? url.href : '#';} catch {return '#';} };
let toastTimer;
function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').hidden = true, 4500); }
async function api(path, options = {}) {
  const response = await fetch('/api' + path, {...options, headers: {'Content-Type': 'application/json', 'X-MedAI-Request': '1', ...options.headers}, credentials: 'same-origin'});
  let data; try {data = await response.json();} catch {throw new Error('The service is unavailable. Please try again.');}
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth')) {state.user = null; updateAccount(); openAuth();}
    throw new Error(Array.isArray(data.detail) ? data.detail.map(e => e.msg.replace('Value error, ', '')).join(' ') : data.detail || 'Something went wrong. Please try again.');
  }
  return data;
}
function updateAccount() {
  $('#account-label').textContent = state.user ? `${state.user.full_name} · Sign out` : 'Sign in or create account';
  $('#avatar').textContent = state.user ? state.user.full_name.charAt(0).toUpperCase() : 'U';
  $('#admin-nav').hidden = state.user?.role !== 'admin';
}
function openAuth() {if (!$('#auth-dialog').open) $('#auth-dialog').showModal();}
function setAuthMode() {
  $('#name-field').hidden = $('#consent-field').hidden = !state.registering;
  $('#full-name').required = $('#consent').required = state.registering;
  $('#auth-title').textContent = state.registering ? 'A healthier start.' : 'Welcome back.';
  $('#auth-subtitle').textContent = state.registering ? 'Create an account to save your conversations.' : 'Sign in to continue your health conversations.';
  $('#auth-submit').textContent = state.registering ? 'Create account' : 'Sign in';
  $('#auth-switch').textContent = state.registering ? 'Already have an account? Sign in' : 'New here? Create an account';
  $('#password').autocomplete = state.registering ? 'new-password' : 'current-password';
  $('#auth-error').textContent = '';
}
async function showView(view) {
  if (!['chat','library','about','admin'].includes(view)) view = 'chat';
  if (view === 'admin' && state.user?.role !== 'admin') return;
  document.querySelectorAll('.view').forEach(el => el.hidden = el.id !== 'view-' + view);
  document.querySelectorAll('[data-view]').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  $('#page-label').textContent = {chat:'Health assistant',library:'Health library',about:'About & privacy',admin:'Administration'}[view];
  history.replaceState(null, '', '#' + view);
  try {
    if (view === 'library') {$('#library').innerHTML = '<p class="quiet">Loading the library…</p>'; state.library = await api('/library'); renderLibrary();}
    if (view === 'admin') await loadAdmin(state.adminTab);
  } catch (error) {toast(error.message);}
}
async function refreshHistory() {
  if (!state.user) {$('#history').innerHTML = '<p class="quiet">Sign in to save your conversations.</p>';return;}
  const conversations = await api('/conversations');
  $('#history').innerHTML = conversations.length ? conversations.map(c => `<button data-conversation="${c.id}" class="${c.id === state.conversation ? 'selected' : ''}" title="${escapeHTML(c.title)}">${escapeHTML(c.title)}</button>`).join('') : '<p class="quiet">Your conversations will appear here.</p>';
}
function clearChat() {state.conversation = null; $('#messages').replaceChildren(); $('#welcome').hidden = false; $('#delete-chat').hidden = true;}
function renderMessage(message) {
  const element = document.createElement('article'); element.className = `message ${message.sender === 'user' ? 'user' : 'assistant'} ${message.mode === 'emergency' ? 'emergency' : ''}`;
  const mode = {evidence:'Library excerpts',medgemma:'AI-assisted explanation',general_ai:'AI · General education',ai_unavailable:'AI temporarily unavailable',emergency:'Seek urgent help',no_evidence:'More guidance needed',referral:'Professional advice needed'}[message.mode];
  element.innerHTML = `<div class="message-head">${message.sender === 'user' ? 'You' : '✚ MedAI'}${mode ? `<span class="mode-tag">${mode}</span>` : ''}</div><div class="message-content">${escapeHTML(message.content)}</div>`;
  if (message.sources?.length) element.insertAdjacentHTML('beforeend', `<div class="source-links">${message.sources.map((s,i) => `<a href="${escapeHTML(safeURL(s.url))}" target="_blank" rel="noopener noreferrer">[${i+1}] ${escapeHTML(s.title)} ↗</a>`).join('')}</div>`);
  if (message.sender === 'assistant' && message.id) element.insertAdjacentHTML('beforeend', `<div class="feedback"><span>Was this helpful?</span><button data-feedback="${message.id}" data-rating="5">Yes</button><button data-feedback="${message.id}" data-rating="1">Not quite</button></div>`);
  $('#messages').append(element);
  return element;
}
async function openConversation(id) {
  if (state.busy) return;
  try {const messages = await api(`/conversations/${id}/messages`); state.conversation = id; $('#welcome').hidden = true; $('#delete-chat').hidden = false; $('#messages').replaceChildren(); messages.forEach(renderMessage); await showView('chat'); await refreshHistory();} catch (error) {toast(error.message);}
}
function renderLibrary() {
  const query = $('#library-search').value.toLowerCase();
  const documents = state.library.filter(d => (d.title + ' ' + d.category + ' ' + d.content).toLowerCase().includes(query));
  $('#library').innerHTML = documents.length ? documents.map(d => `<article class="library-card"><span class="eyebrow">${escapeHTML(d.category)}</span><h2>${escapeHTML(d.title)}</h2><p>${escapeHTML(d.content.slice(0,160))}…</p><button data-article="${d.id}">Read article ↗</button></article>`).join('') : `<div class="empty">${query ? 'No articles match your search.' : 'The library is being prepared.<br>Reviewed health articles will appear here once an administrator publishes them.'}</div>`;
}
function showArticle(id) {
  const d = state.library.find(d => d.id === id); if (!d) return;
  $('#article-content').innerHTML = `<span class="eyebrow">${escapeHTML(d.category)}</span><h2>${escapeHTML(d.title)}</h2><p class="quiet">Reviewed ${d.reviewed_at ? new Date(d.reviewed_at).toLocaleDateString() : 'by an administrator'}</p><p class="article-body">${escapeHTML(d.content)}</p><a href="${escapeHTML(safeURL(d.source))}" target="_blank" rel="noopener noreferrer">Read the original source ↗</a>`;
  $('#article-dialog').showModal();
}
function documentEditor(id) {
  $('#document-form').reset(); $('#document-error').textContent = '';
  const d = state.documents.find(d => d.id === id);
  $('#document-id').value = d?.id || ''; $('#document-title').textContent = d ? 'Edit health information' : 'Add health information';
  for (const key of ['title','category','source','content']) $('#doc-' + key).value = d?.[key] || '';
  $('#doc-approved').checked = d?.approved || false; $('#document-dialog').showModal();
}
async function loadAdmin(tab) {
  state.adminTab = tab;
  document.querySelectorAll('[data-admin]').forEach(b => b.classList.toggle('selected', b.dataset.admin === tab));
  const container = $('#admin-content'); container.innerHTML = '<p class="quiet">Loading workspace…</p>';
  try {
    const data = await api('/admin/' + tab);
    if (state.adminTab !== tab) return;
    if (tab === 'reports') {
      const max = Math.max(1, ...data.daily.map(d => d.questions));
      container.innerHTML = `<div class="stats">${[['People',data.users],['Conversations',data.conversations],['Reviewed articles',data.approved_documents],['Average rating',data.average_rating ? data.average_rating.toFixed(1) + '/5' : '—']].map(([label,value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`).join('')}</div><div class="panel"><h2>Questions over time</h2>${data.daily.length ? data.daily.map(d => `<div class="chart-row"><span>${escapeHTML(d.date)}</span><meter min="0" max="${max}" value="${d.questions}" aria-label="Questions on ${escapeHTML(d.date)}">${d.questions}</meter><span>${d.questions}</span></div>`).join('') : '<p class="quiet">Activity will appear after the first conversation.</p>'}</div><div class="panel"><h2>Frequently asked questions</h2>${data.frequent_questions.length ? `<table><thead><tr><th>Question</th><th>Count</th></tr></thead><tbody>${data.frequent_questions.map(q => `<tr><td>${escapeHTML(q.question)}</td><td>${q.count}</td></tr>`).join('')}</tbody></table>` : '<p class="quiet">No questions yet.</p>'}</div><div class="toolbar"><p>${data.emergencies} emergency flags · ${data.feedback_count} feedback responses</p><button class="primary" id="export-report">Download report</button></div>`;
      $('#export-report').onclick = () => {const blob = new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url = URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='medai-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    } else if (tab === 'documents') {
      state.documents = data;
      container.innerHTML = `<div class="toolbar"><p>Only approved articles are used in answers.</p><button class="primary" id="add-document">＋ Add document</button></div><div class="panel">${data.length ? `<table><thead><tr><th>Title</th><th>Category</th><th>Status</th><th>Actions</th></tr></thead><tbody>${data.map(d => `<tr><td>${escapeHTML(d.title)}</td><td>${escapeHTML(d.category)}</td><td>${d.approved ? 'Published' : 'Draft'}</td><td><button data-edit-doc="${d.id}">Edit</button><button data-delete-doc="${d.id}">Delete</button></td></tr>`).join('')}</tbody></table>` : '<p class="quiet">Add a sourced article, review it, and publish it to start your knowledge base.</p>'}</div>`;
      $('#add-document').onclick = () => documentEditor(null);
    } else if (tab === 'users') {
      container.innerHTML = `<div class="panel"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Access</th></tr></thead><tbody>${data.map(u => `<tr><td>${escapeHTML(u.full_name)}</td><td>${escapeHTML(u.email)}</td><td>${escapeHTML(u.role)}</td><td>${u.role === 'admin' ? 'Administrator' : `<button data-user="${u.id}" data-active="${!u.active}">${u.active ? 'Disable' : 'Enable'}</button>`}</td></tr>`).join('')}</tbody></table></div>`;
    } else if (tab === 'interactions') {
      container.innerHTML = `<div class="panel"><h2>Recent interactions</h2><p class="quiet">Access is recorded in the audit log. Showing the latest 100 messages.</p>${data.length ? data.map(m => `<div class="interaction"><small>Conversation ${m.conversation_id} · ${escapeHTML(m.sender)} · ${escapeHTML(new Date(m.created_at).toLocaleString())}</small><p>${escapeHTML(m.content)}</p></div>`).join('') : '<p class="quiet">No interactions yet.</p>'}</div>`;
    } else {
      container.innerHTML = `<div class="panel"><h2>Recent audit events</h2><table><thead><tr><th>Administrator</th><th>Action</th><th>Time</th></tr></thead><tbody>${data.map(a => `<tr><td>${a.user_id}</td><td>${escapeHTML(a.action)}</td><td>${escapeHTML(new Date(a.created_at).toLocaleString())}</td></tr>`).join('')}</tbody></table></div>`;
    }
  } catch (error) {container.innerHTML = `<p class="error">${escapeHTML(error.message)}</p>`;}
}
document.addEventListener('click', async (event) => {
  const button = event.target.closest('button'); if (!button) return;
  const d = button.dataset;
  try {
    if (d.close) $('#' + d.close).close();
    if (d.view) await showView(d.view);
    if (d.question) {$('#question').value = d.question; $('#question').focus();}
    if (d.conversation) await openConversation(Number(d.conversation));
    if (d.article) showArticle(Number(d.article));
    if (d.admin) await loadAdmin(d.admin);
    if (d.editDoc) documentEditor(Number(d.editDoc));
    if (d.deleteDoc && confirm('Delete this article from the library and future answers?')) {await api('/admin/documents/' + d.deleteDoc,{method:'DELETE'});await loadAdmin('documents');toast('Document deleted.');}
    if (d.user) {await api('/admin/users/' + d.user,{method:'PATCH',body:JSON.stringify({active:d.active === 'true'})});await loadAdmin('users');}
    if (d.feedback) {await api('/feedback',{method:'POST',body:JSON.stringify({message_id:Number(d.feedback),rating:Number(d.rating)})});button.closest('.feedback').textContent = 'Thank you for your feedback.';}
  } catch (error) {toast(error.message);}
});
$('#auth-switch').onclick = () => {state.registering = !state.registering;setAuthMode();};
$('#account').onclick = async () => {
  if (state.busy) return;
  if (!state.user) return openAuth();
  try {await api('/auth/logout',{method:'POST'});state.user=null;clearChat();updateAccount();await refreshHistory();await showView('chat');toast('You have signed out.');}catch(error){toast(error.message);}
};
$('#auth-form').onsubmit = async event => {
  event.preventDefault(); $('#auth-submit').disabled = true; $('#auth-error').textContent = '';
  try {state.user=await api('/auth/' + (state.registering ? 'register' : 'login'),{method:'POST',body:JSON.stringify({email:$('#email').value,password:$('#password').value,...(state.registering ? {full_name:$('#full-name').value,consent:$('#consent').checked} : {})})});$('#auth-dialog').close();$('#password').value='';updateAccount();await refreshHistory();toast('You’re signed in.');}catch(error){$('#auth-error').textContent=error.message;}finally{$('#auth-submit').disabled=false;}
};
$('#new-chat').onclick = async () => {if(state.busy)return;clearChat();await showView('chat');try{await refreshHistory();}catch(error){toast(error.message);}$('#question').focus();};
$('#delete-chat').onclick = async () => {if(!state.conversation||state.busy||!confirm('Permanently delete this conversation and its feedback?'))return;try{await api(`/conversations/${state.conversation}`,{method:'DELETE'});clearChat();await refreshHistory();toast('Conversation deleted.');}catch(error){toast(error.message);}};
$('#chat-form').onsubmit = async event => {
  event.preventDefault();if(state.busy)return;if(!state.user)return openAuth();
  const question=$('#question').value.trim();if(!question)return;
  state.busy=true;$('#send').disabled=true;$('#send').textContent='…';
  $('#question').readOnly=true;
  const started=performance.now();
  $('#welcome').hidden=true;
  const pendingQuestion=renderMessage({sender:'user',content:question});
  const thinking=document.createElement('div');
  thinking.className='message thinking-status';
  thinking.setAttribute('role','status');
  thinking.setAttribute('aria-live','polite');
  thinking.textContent='MedAI · Thinking…';
  $('#messages').append(thinking);
  thinking.scrollIntoView({behavior:'smooth',block:'nearest'});
  let received=false;
  try {
    if(!state.conversation){const c=await api('/conversations',{method:'POST'});state.conversation=c.id;}
    const result=await api(`/conversations/${state.conversation}/messages`,{method:'POST',body:JSON.stringify({message:question})});
    // Pace normal replies in the browser without adding server execution time.
    // Urgent guidance and service failures should be displayed immediately.
    if(!['emergency','ai_unavailable'].includes(result.reply.mode)){
      const remaining=5000-(performance.now()-started);
      if(remaining>0)await new Promise(resolve=>setTimeout(resolve,remaining));
    }
    pendingQuestion.remove();thinking.remove();received=true;
    $('#welcome').hidden=true;$('#delete-chat').hidden=false;renderMessage(result.question);renderMessage(result.reply);$('#question').value='';await refreshHistory();$('#chat-form').scrollIntoView({behavior:'smooth',block:'end'});
  }catch(error){if(!received)pendingQuestion.remove();toast(error.message);}finally{thinking.remove();state.busy=false;$('#question').readOnly=false;$('#send').disabled=false;$('#send').textContent='↑';}
};
$('#question').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();$('#chat-form').requestSubmit();}});
$('#library-search').oninput=renderLibrary;
$('#doc-file').onchange=async()=>{const file=$('#doc-file').files[0];if(!file)return;if(file.size>120000){$('#document-error').textContent='Use a text file smaller than 120 KB.';return;}const content=await file.text();if(content.length>30000){$('#document-error').textContent='Use no more than 30,000 characters per document.';return;}$('#doc-content').value=content;$('#doc-approved').checked=false;};
$('#document-form').onsubmit=async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;try{const id=$('#document-id').value;await api('/admin/documents'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify({title:$('#doc-title').value,category:$('#doc-category').value,source:$('#doc-source').value,content:$('#doc-content').value,approved:$('#doc-approved').checked})});$('#document-dialog').close();await loadAdmin('documents');toast('Document saved.');}catch(error){$('#document-error').textContent=error.message;}finally{button.disabled=false;}};
(async()=>{try{state.user=await api('/auth/me');}catch{}updateAccount();try{await refreshHistory();}catch(error){toast(error.message);}await showView(location.hash.slice(1)||'chat');})();
