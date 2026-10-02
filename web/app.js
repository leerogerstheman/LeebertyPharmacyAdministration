// LeebertyPharmacyAdministration 前端（本地知识库 × 真实大模型）
(function () {
  const chat = document.getElementById('chat');
  const input = document.getElementById('input');
  const sendBtn = document.getElementById('send');
  const disclaimer = document.getElementById('disclaimer');
  const badge = document.getElementById('modelBadge');
  const modal = document.getElementById('llmModal');
  const gearBtn = document.getElementById('gearBtn');
  let role = null;
  let llmConfigured = false;

  async function refreshStatus() {
    try {
      const j = await (await fetch('/api/llm/status')).json();
      llmConfigured = !!j.configured;
      if (j.configured) {
        badge.textContent = '🤖 AI 模式 · ' + j.model;
        badge.classList.add('ai');
        disclaimer.textContent = '知识库已加载 · AI 模式（' + j.model + '）· ⚠️ 不构成医疗诊断或法律意见，用药请遵医嘱。';
      } else {
        badge.textContent = '📚 本地知识库模式';
        badge.classList.remove('ai');
        disclaimer.textContent = '知识库已加载 · 本地模式 · ⚠️ 不构成医疗诊断或法律意见；点击 ⚙ 模型 可接入真实大模型。';
      }
    } catch (e) {
      disclaimer.textContent = '服务连接失败，请确认后台服务已启动（python agent/server.py）';
    }
  }

  function fillSettings() {
    fetch('/api/llm/status').then(r => r.json()).then(j => {
      document.getElementById('cfgBase').value = j.api_base || '';
      document.getElementById('cfgModel').value = j.model || '';
      document.getElementById('cfgEnabled').checked = !!j.enabled;
    });
  }

  function addMsg(text, who, sources, isAI, modelName) {
    const div = document.createElement('div');
    div.className = 'msg ' + who;
    const tag = document.createElement('span');
    tag.className = 'tag';
    if (who === 'agent') {
      tag.innerHTML = isAI ? '<span class="ai-tag">🤖 ' + (modelName || 'AI') + '</span>' : '📚 本地知识库';
    } else {
      tag.textContent = '你';
    }
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    div.appendChild(tag);
    div.appendChild(bubble);
    if (sources && sources.length) {
      sources.slice(0, 3).forEach(s => {
        const src = document.createElement('span');
        src.className = 'src';
        src.textContent = '📄 ' + s;
        bubble.appendChild(src);
      });
    }
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  function ask(message, extra) {
    sendBtn.disabled = true;
    const body = Object.assign({ message: message, role: role }, extra || {});
    fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(r => r.json())
      .then(j => {
        addMsg(j.reply || '(无回复)', 'agent', j.sources, !!j.llm, j.model);
        if (j.llm_error) console.warn('LLM error:', j.llm_error);
        if (j.role && j.role !== role) {
          role = j.role;
          document.querySelectorAll('.role-btn[data-role]').forEach(b => {
            b.classList.toggle('active', b.dataset.role === role);
          });
        }
        refreshStatus();
      })
      .catch(e => addMsg('请求失败：' + e.message, 'agent'))
      .finally(() => { sendBtn.disabled = false; input.focus(); });
  }

  sendBtn.addEventListener('click', () => {
    const v = input.value.trim();
    if (!v) return;
    addMsg(v, 'user');
    input.value = '';
    ask(v);
  });

  input.addEventListener('keydown', e => { if (e.key === 'Enter') sendBtn.click(); });

  document.querySelectorAll('.role-btn[data-role]').forEach(btn => {
    btn.addEventListener('click', () => {
      const r = btn.dataset.role;
      if (r === 'clear') { ask('reset'); return; }
      role = r;
      document.querySelectorAll('.role-btn[data-role]').forEach(b => b.classList.toggle('active', b.dataset.role === r));
      ask('我是' + ({ personal: '个人', org: '机构', company: '公司' })[r]);
    });
  });

  // 设置弹窗
  gearBtn.addEventListener('click', () => { fillSettings(); modal.classList.add('show'); });
  document.getElementById('modalClose').addEventListener('click', () => modal.classList.remove('show'));
  modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('show'); });

  document.getElementById('testBtn').addEventListener('click', () => {
    const res = document.getElementById('testResult');
    res.textContent = '测试连接中…';
    res.classList.remove('err');
    fetch('/api/llm/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_base: document.getElementById('cfgBase').value.trim(),
        api_key: document.getElementById('cfgKey').value.trim() || undefined,
        model: document.getElementById('cfgModel').value.trim() || undefined
      })
    }).then(r => r.json()).then(j => {
      if (j.ok) { res.textContent = '✅ ' + j.message; }
      else { res.classList.add('err'); res.textContent = '❌ ' + j.message; }
    }).catch(e => { res.classList.add('err'); res.textContent = '❌ 请求失败：' + e.message; });
  });

  document.getElementById('saveBtn').addEventListener('click', () => {
    const res = document.getElementById('testResult');
    fetch('/api/llm/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_base: document.getElementById('cfgBase').value.trim(),
        api_key: document.getElementById('cfgKey').value.trim(),
        model: document.getElementById('cfgModel').value.trim(),
        temperature: parseFloat(document.getElementById('cfgTemp').value) || 0.3,
        max_tokens: parseInt(document.getElementById('cfgTokens').value) || 1400,
        enabled: document.getElementById('cfgEnabled').checked
      })
    }).then(r => r.json()).then(j => {
      if (j.configured) {
        res.textContent = '✅ 已保存并启用 AI 模式（' + j.model + '）。';
        res.classList.remove('err');
      } else {
        res.textContent = '已保存，但尚未满足启用条件（需要 api_base、api_key、model 且勾选启用）。';
        res.classList.remove('err');
      }
      refreshStatus();
      setTimeout(() => modal.classList.remove('show'), 1200);
    }).catch(e => { res.classList.add('err'); res.textContent = '❌ 保存失败：' + e.message; });
  });

  refreshStatus();
  input.focus();
})();
