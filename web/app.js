// LeebertyPharmacyAdministration 前端 v4（现代 Agent UI）
(function () {
  const chat = document.getElementById('chat');
  const input = document.getElementById('input');
  const sendBtn = document.getElementById('send');
  const disclaimer = document.getElementById('disclaimer');
  const badge = document.getElementById('modelBadge');
  const sideList = document.getElementById('sideList');
  const sideCount = document.getElementById('sideCount');
  let role = null, paradigm = 'adaptive', llmConfigured = false;
  let sessions = [{ title: '新会话', msgs: [] }], cur = 0;

  // ---------- Markdown 轻渲染（转义后结构化，无 XSS） ----------
  function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function inline(t){
    t = esc(t);
    t = t.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    return t;
  }
  function md2html(md){
    const lines = (md||'').split('\n');
    let html = '', inCode = false, codeBuf = [];
    for (let raw of lines){
      const line = raw.trimEnd();
      if (line.trim().startsWith('```')){
        if (inCode){ html += '<pre><code>' + esc(codeBuf.join('\n')) + '</code></pre>'; codeBuf = []; }
        inCode = !inCode; continue;
      }
      if (inCode){ codeBuf.push(line); continue; }
      if (!line.trim()){ html += '<br>'; continue; }
      if (/^### /.test(line)){ html += '<h3>' + inline(line.slice(4)) + '</h3>'; continue; }
      if (/^## /.test(line)){ html += '<h2>' + inline(line.slice(3)) + '</h2>'; continue; }
      if (/^# /.test(line)){ html += '<h1>' + inline(line.slice(2)) + '</h1>'; continue; }
      if (/^\s*[-*]\s+/.test(line)){ html += '<div>• ' + inline(line.replace(/^\s*[-*]\s+/,'')) + '</div>'; continue; }
      if (/^\s*\d+\.\s+/.test(line)){ html += '<div>' + inline(line.trim()) + '</div>'; continue; }
      if (line.trim().startsWith('|')){ html += '<div class="tbl">' + esc(line.trim()) + '</div>'; continue; }
      if (line.trim().startsWith('>')){ html += '<blockquote>' + inline(line.trim().slice(1).trim()) + '</blockquote>'; continue; }
      html += '<div>' + inline(line) + '</div>';
    }
    if (inCode && codeBuf.length) html += '<pre><code>' + esc(codeBuf.join('\n')) + '</code></pre>';
    return html;
  }

  // ---------- 渲染消息 ----------
  function addMsg(who, text, opt){
    opt = opt || {};
    const curS = sessions[cur];
    curS.msgs.push({ who, text, meta: opt.meta || null, tool: opt.tool || null, src: opt.src || [] });
    renderMsg(curS.msgs[curS.msgs.length-1], true);
    saveSessions();
  }
  function renderMsg(m, scroll){
    const div = document.createElement('div');
    div.className = 'msg ' + m.who;
    if (m.meta) { const meta = document.createElement('div'); meta.className='meta'; meta.textContent = m.meta; div.appendChild(meta); }
    const b = document.createElement('div'); b.className='bubble';
    b.innerHTML = (m.who === 'user') ? esc(m.text).replace(/\n/g,'<br>') : md2html(m.text);
    div.appendChild(b);
    if (m.src && m.src.length){ const s = document.createElement('span'); s.className='src'; s.textContent='📄 ' + m.src.slice(0,3).join('；'); div.appendChild(s); }
    if (m.tool){ const t = document.createElement('span'); t.className='tool'; t.textContent='🧠 ' + m.tool; div.appendChild(t); }
    if (m.who === 'agent' && m.text){
      const acts = document.createElement('div'); acts.className='msg-actions';
      const cpy = document.createElement('button'); cpy.className='mini-btn'; cpy.textContent='📋 复制';
      cpy.onclick = () => navigator.clipboard.writeText(m.text);
      const ok = document.createElement('button'); ok.className='mini-btn'; ok.textContent='👍';
      const bad = document.createElement('button'); bad.className='mini-btn'; bad.textContent='👎';
      const fb = (r) => fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:lastUser(),reply:m.text,rating:r})}).then(r=>r.json()).then(j=>{disclaimer.textContent='已记录'+(r?'好评':'差评')+'（共 '+j.total+' 条偏好数据）'; ok.disabled=bad.disabled=true;});
      ok.onclick = () => fb(1); bad.onclick = () => fb(0);
      acts.append(cpy, ok, bad); div.appendChild(acts);
    }
    chat.appendChild(div);
    if (scroll) chat.scrollTop = chat.scrollHeight;
  }
  function lastUser(){ const msgs = sessions[cur].msgs; for (let i=msgs.length-1;i>=0;i--) if (msgs[i].who==='user') return msgs[i].text; return ''; }

  // ---------- 会话 ----------
  function saveSessions(){ try { localStorage.setItem('lp_sessions', JSON.stringify(sessions)); } catch(e){} }
  function loadSessions(){ try { const d = localStorage.getItem('lp_sessions'); if (d){ sessions = JSON.parse(d); if (!sessions.length) sessions=[{title:'新会话',msgs:[]}]; } } catch(e){} renderSide(); if (!chat.children.length) renderAll(); }
  function renderSide(){
    sideList.innerHTML = '';
    sideCount.textContent = sessions.length;
    sessions.forEach((s,i)=>{
      const it = document.createElement('div'); it.className='side-item' + (i===cur?' active':'');
      it.textContent = s.title || '新会话'; it.onclick = () => openSession(i);
      sideList.appendChild(it);
    });
  }
  function openSession(i){ if (i<0||i>=sessions.length) return; cur=i; chat.innerHTML=''; sessions[i].msgs.forEach(m=>renderMsg(m,false)); renderSide(); chat.scrollTop = chat.scrollHeight; }
  function newSession(){ sessions.push({title:'新会话',msgs:[]}); cur=sessions.length-1; chat.innerHTML=''; renderWelcome(); renderSide(); saveSessions(); }

  // ---------- 欢迎引导卡片 ----------
  const CHIPS = [
    ['🧑 个人用药咨询', '老年人多重用药要注意什么？'],
    ['🏥 医院药事建设', '药事管理与药物治疗学委员会有哪些职责？'],
    ['✅ GSP 合规自查', 'GSP自查'],
    ['📐 药物经济学', '成本10000元效果8 vs 成本15000元效果9 方案是否划算？'],
    ['🔬 深度研究', '深度研究 药品不良反应监测体系'],
    ['📜 模板服务', '模板'],
  ];
  function renderWelcome(){
    if (sessions[cur].msgs.length) return;
    const w = document.createElement('div'); w.className='cards';
    w.innerHTML = '<h2>您好，有什么可以帮您？</h2><p>药事管理智能 Agent · 本地知识库 × 药剂工具 × 可选大模型</p>';
    const grid = document.createElement('div'); grid.className='chip-grid';
    CHIPS.forEach(([t,p])=>{
      const c = document.createElement('div'); c.className='chip';
      c.innerHTML = '<b>'+t+'</b><span>点击提问 →</span>';
      c.onclick = () => { chat.innerHTML=''; send(p); };
      grid.appendChild(c);
    });
    w.appendChild(grid); chat.appendChild(w);
  }

  // ---------- 对话 ----------
  function showThinking(){
    const d = document.createElement('div'); d.className='msg agent';
    d.id = 'thinking';
    d.innerHTML = '<div class="meta">🤖 思考中</div><div class="bubble thinking"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
    chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
  }
  function ask(message){
    sendBtn.disabled = true; showThinking();
    fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,role,paradigm})})
      .then(r=>r.json())
      .then(j=>{
        const th = document.getElementById('thinking'); if (th) th.remove();
        addMsg('agent', j.reply || '(无回复)', {
          meta: j.llm ? ('🤖 ' + (j.model||'AI') + (paradigm!=='adaptive' ? ' · ' + paradigm : '')) : null,
          src: j.sources, tool: (j.trace||[]).filter(s=>/工具|检索|范式/.test(s)).slice(0,6).join(' → ')
        });
        if (j.role) role = j.role;
        if (j.llm_error) disclaimer.textContent = '⚠️ AI 调用失败已降级：' + j.llm_error;
        refreshStatus();
      })
      .catch(e=>{ const th=document.getElementById('thinking'); if(th) th.remove(); addMsg('agent','请求失败：'+e.message); })
      .finally(()=>{ sendBtn.disabled=false; input.focus(); });
  }
  function send(text){
    const v = (text || input.value).trim();
    if (!v || sendBtn.disabled) return;
    if (!text) input.value = '';
    if (v === 'reset') { sessions[cur].msgs=[]; chat.innerHTML=''; renderWelcome(); saveSessions(); return; }
    const w = document.querySelector('.cards'); if (w) w.remove();
    addMsg('user', v);
    const t = v.replace(/^我是/,'');
    if (['个人','机构','公司'].includes(t)) role = ({个人:'personal',机构:'org',公司:'company'})[t];
    sessions[cur].title = v.slice(0,16); renderSide();
    ask(v);
  }

  // ---------- 主题 ----------
  function initTheme(){ try { const t = localStorage.getItem('lp_theme'); if (t) document.body.classList.toggle('dark', t==='dark'); } catch(e){} }
  function toggleTheme(){ document.body.classList.toggle('dark'); try { localStorage.setItem('lp_theme', document.body.classList.contains('dark')?'dark':'light'); } catch(e){} }

  // ---------- LLM 状态 ----------
  async function refreshStatus(){
    try {
      const j = await (await fetch('/api/llm/status')).json();
      llmConfigured = !!j.configured;
      badge.textContent = j.configured ? ('🤖 ' + j.model) : '📚 本地模式';
    } catch(e){ badge.textContent = '服务未连接'; }
  }

  // ---------- 事件绑定 ----------
  sendBtn.onclick = () => send();
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); send(); }
  });
  input.addEventListener('input', () => { input.style.height='auto'; input.style.height=Math.min(150, input.scrollHeight)+'px'; });
  document.getElementById('themeBtn').onclick = toggleTheme;
  document.getElementById('newBtn').onclick = newSession;

  // 设置弹窗
  const modal = document.getElementById('llmModal');
  document.getElementById('cfgBtn').onclick = () => { fillSettings(); modal.classList.add('show'); };
  document.getElementById('modalClose').onclick = () => modal.classList.remove('show');
  modal.onclick = e => { if (e.target === modal) modal.classList.remove('show'); };
  function fillSettings(){ fetch('/api/llm/status').then(r=>r.json()).then(j=>{ document.getElementById('cfgBase').value=j.api_base||''; document.getElementById('cfgModel').value=j.model||''; document.getElementById('cfgEnabled').checked=!!j.enabled; }); }
  document.getElementById('testBtn').onclick = () => {
    const res = document.getElementById('testResult'); res.textContent='测试连接中…'; res.classList.remove('err');
    fetch('/api/llm/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_base:val('cfgBase'),api_key:val('cfgKey')||undefined,model:val('cfgModel')||undefined})})
      .then(r=>r.json()).then(j=>{ if(j.ok){res.textContent='✅ '+j.message;} else {res.classList.add('err');res.textContent='❌ '+j.message;} })
      .catch(e=>{res.classList.add('err');res.textContent='❌ '+e.message;});
  };
  function val(id){ return document.getElementById(id).value.trim(); }
  document.getElementById('saveBtn').onclick = () => {
    const res = document.getElementById('testResult');
    fetch('/api/llm/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_base:val('cfgBase'),api_key:val('cfgKey'),model:val('cfgModel'),temperature:parseFloat(val('cfgTemp'))||0.3,max_tokens:parseInt(val('cfgTokens'))||1400,enabled:document.getElementById('cfgEnabled').checked})})
      .then(r=>r.json()).then(j=>{ res.textContent = j.configured ? '✅ 已启用 AI 模式（'+j.model+'）' : '已保存（尚未启用）'; res.classList.remove('err'); refreshStatus(); setTimeout(()=>modal.classList.remove('show'),1200); })
      .catch(e=>{res.classList.add('err');res.textContent='❌ 保存失败：'+e.message;});
  };

  initTheme(); loadSessions(); refreshStatus(); input.focus();
})();