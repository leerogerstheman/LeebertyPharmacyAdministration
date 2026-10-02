# -*- coding: utf-8 -*-
# memory.py — 长期记忆系统（用户画像，跨会话持久化）
# 借鉴 hello-agents 第八章：短期工作记忆(对话窗口) + 长期记忆(画像文件)
import os
import json
import datetime

from paths import MEMORY_DIR
PROFILE_PATH = os.path.join(MEMORY_DIR, 'profile.json')
MAX_TOPICS = 12

DEFAULT_PROFILE = {
    'role': None,
    'interests': [],
    'recent_questions': [],
    'last_active': '',
    'notes': {},
}

def load_profile():
    p = dict(DEFAULT_PROFILE)
    try:
        with open(PROFILE_PATH, 'r', encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict):
            for k in DEFAULT_PROFILE:
                if k in d:
                    p[k] = d[k]
    except Exception:
        pass
    return p

def save_profile(p):
    try:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        with open(PROFILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def remember(role=None, question=None):
    """会话中调用：更新用户画像（身份、兴趣话题）"""
    p = load_profile()
    changed = False
    if role and role in ('personal', 'org', 'company') and p.get('role') != role:
        p['role'] = role
        changed = True
    if question:
        q = question.strip()
        if q and (not p['recent_questions'] or p['recent_questions'][-1] != q):
            p['recent_questions'].append(q)
            p['recent_questions'] = p['recent_questions'][-8:]
            changed = True
    if changed:
        p['last_active'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        save_profile(p)
    return p

def recall_profile():
    """生成画像摘要文本，注入 system prompt"""
    p = load_profile()
    if not p.get('role') and not p.get('recent_questions'):
        return ''
    parts = ['【用户画像（长期记忆）】']
    role_map = {'personal': '个人', 'org': '集体/医疗机构', 'company': '公司/企业'}
    if p.get('role'):
        parts.append('身份：' + role_map.get(p['role'], p['role']))
    if p.get('recent_questions'):
        parts.append('近期关注：' + '、'.join(p['recent_questions'][-4:]))
    if p.get('last_active'):
        parts.append('最近活跃：' + p['last_active'])
    return '\n'.join(parts)

def reset_profile():
    save_profile(dict(DEFAULT_PROFILE))
PREFS_PATH = os.path.join(MEMORY_DIR, 'preferences.json')

def record_feedback(question, reply, rating):
    """第11章：记录用户反馈（偏好数据，为 Agentic-RL 微调备料）"""
    try:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        prefs = []
        if os.path.exists(PREFS_PATH):
            try:
                with open(PREFS_PATH, 'r', encoding='utf-8') as f:
                    prefs = json.load(f)
            except Exception:
                prefs = []
            if not isinstance(prefs, list):
                prefs = []
        prefs.append({
            'question': (question or '')[:300],
            'reply': (reply or '')[:500],
            'rating': int(rating),
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        })
        prefs = prefs[-2000:]
        with open(PREFS_PATH, 'w', encoding='utf-8') as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
        return len(prefs)
    except Exception:
        return None

def session_summary(history, max_len=10):
    """第8章：会话摘要——历史超过阈值时返回摘要提示（LLM 模式可用）"""
    if not history or len(history) <= max_len:
        return None
    # 保留最近的 max_len 条，更早的合并为一段
    recent = history[-max_len:]
    old = history[:-max_len]
    lines = []
    for h in old:
        who = '用户' if h.get('role') == 'user' else '助手'
        content = (h.get('content') or '')[:120]
        lines.append(who + '：' + content)
    return '（以下为较早对话压缩摘要）\n' + '\n'.join(lines[-6:])
