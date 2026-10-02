# -*- coding: utf-8 -*-
# llm.py — 真实大模型 API 接入（OpenAI 兼容协议 /chat/completions，纯标准库 urllib）
# 支持 DeepSeek、OpenAI、智谱 GLM、通义千问、Kimi、Ollama 等任何 OpenAI 兼容服务
import os
import json
import urllib.request
import urllib.error

from paths import CONFIG_PATH

DEFAULTS = {
    'api_base': 'https://api.deepseek.com/v1',
    'api_key': '',
    'model': 'deepseek-chat',
    'enabled': False,
    'temperature': 0.3,
    'max_tokens': 1400,
    'timeout': 90,
}

HISTORY_MAX = 6

def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in DEFAULTS:
                if k in data:
                    cfg[k] = data[k]
    except Exception:
        pass
    return cfg

def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def is_configured(cfg=None):
    cfg = cfg or load_config()
    return bool(cfg.get('enabled') and cfg.get('api_key') and cfg.get('api_base') and cfg.get('model'))

def status_text(cfg=None):
    cfg = cfg or load_config()
    if is_configured(cfg):
        return 'AI 模式已启用：模型 %s，服务 %s' % (cfg['model'], cfg['api_base'])
    return '当前为本地知识库模式（未配置/未启用大模型 API）。输入 llm set 开始配置，或 llm on 启用。'

def chat(messages, cfg=None):
    cfg = cfg or load_config()
    url = cfg['api_base'].rstrip('/') + '/chat/completions'
    payload = {
        'model': cfg['model'],
        'messages': messages,
        'temperature': float(cfg.get('temperature', 0.3)),
        'max_tokens': int(cfg.get('max_tokens', 1400)),
        'stream': False,
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'Bearer ' + cfg['api_key'].strip())
    timeout = int(cfg.get('timeout', 90))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8')[:300]
        except Exception:
            pass
        if e.code == 401:
            raise RuntimeError('API 密钥无效（401），请检查 api_key')
        if e.code == 404:
            raise RuntimeError('接口地址不存在（404），请检查 api_base 是否包含 /v1')
        if e.code == 429:
            raise RuntimeError('请求过于频繁或额度不足（429）')
        raise RuntimeError('API 错误 %s：%s' % (e.code, body))
    except urllib.error.URLError as e:
        raise RuntimeError('无法连接 API（%s），请检查网络与 api_base' % (e.reason,))
    except Exception as e:
        raise RuntimeError('请求异常：%s' % (e,))
    try:
        data = json.loads(raw)
        return data['choices'][0]['message']['content']
    except Exception:
        raise RuntimeError('API 返回格式异常（缺少 choices[0].message.content）')

def _build_system_prompt(role):
    role_line = ''
    if role == 'personal':
        role_line = '当前用户身份：个人（关注用药咨询、说明书解读、特殊人群用药、家庭药箱）。'
    elif role == 'org':
        role_line = '当前用户身份：集体/医疗机构（关注药事管理与药物治疗学委员会、处方点评、麻精药品五专、抗菌药物管理、药房规范化）。'
    elif role == 'company':
        role_line = '当前用户身份：公司/企业（关注 GxP 合规、GSP/GMP、QA/QC、临床试验 CRA/CRC、药物警戒、药物经济学证据、许可申办）。'
    return ('你是一名专业的药事管理（Pharmacy Administration）专家助手，为个人、医疗机构与企业提供知识服务。'
            '请优先依据下方【参考资料】中的知识库内容回答，并遵循：\n'
            '1. 参考资料不足以回答时，明确说明并给出一般性指引，不得编造法规条款、数据或案例；\n'
            '2. 结构清晰、分条作答，使用简体中文；\n'
            '3. 涉及用药的内容，末尾附安全提示：请遵医嘱用药，出现严重不良反应立即就医；\n'
            '4. 涉及合规/监管的内容，注明以现行有效法规与属地药品监督管理部门为准；\n'
            '5. 引用参考资料时，在相应位置标注【来源1】【来源2】。\n' + role_line)

def trim_history(history):
    if not history:
        return []
    return history[-HISTORY_MAX:]

def answer_with_llm(query, chunks, idf, history=None, role=None, top_k=3, max_ctx_chars=800):
    """RAG 增强问答：检索知识库 → 组装提示词 → 调用真实大模型。
    成功返回 (text, sources, True)；失败返回 (None, [], False, errmsg)。"""
    from engine import search
    hits = search(query, chunks, idf, top_k)
    sources = []
    ctx_lines = ['你正在使用“LeebertyPharmacyAdministration”药事管理知识库。']
    for i, (score, c) in enumerate(hits, 1):
        sources.append('knowledge_base/' + c.path)
        body = c.text
        if len(body) > max_ctx_chars:
            body = body[:max_ctx_chars] + '……'
        ctx_lines.append('[来源%d] 《%s》·%s：%s' % (i, c.doc, c.heading, body))
    ctx = '\n'.join(ctx_lines)
    messages = [{'role': 'system', 'content': _build_system_prompt(role)}]
    for h in trim_history(history or []):
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': h['content'][:2000]})
    user_msg = '【参考资料】\n' + ctx + '\n\n【用户问题】\n' + query
    messages.append({'role': 'user', 'content': user_msg})
    try:
        text = chat(messages)
        return text, sources, True, None
    except RuntimeError as e:
        return None, [], False, str(e)

def test_connection(cfg=None):
    cfg = cfg or load_config()
    try:
        text = chat([{'role': 'user', 'content': '你好，请回复：连接成功'}], cfg)
        return True, text[:120]
    except RuntimeError as e:
        return False, str(e)