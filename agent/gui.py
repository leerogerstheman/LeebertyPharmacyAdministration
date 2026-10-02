# -*- coding: utf-8 -*-
# gui.py — LeebertyPharmacyAdministration 桌面应用 v4.0（现代 Agent UI）
# 参考 ChatGPT/Claude/DeepSeek/Coze/Dify 等主流界面：深浅主题、会话侧边栏、能力卡片、
# Markdown 富文本气泡、流式打字、思考轨迹与来源交互、多行输入
import os
import sys
import re
import json
import threading
import datetime

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 系统缩放不再虚拟化拉伸窗口
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
from tkinter import ttk, messagebox

from engine import load_kb
from server import build_reply
import llm as llm_mod
import memory

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_CFG_PATH = os.path.join(ROOT_DIR, 'memory', 'ui.json')
SESSIONS_PATH = os.path.join(ROOT_DIR, 'memory', 'sessions.json')

# ---------------- 主题系统（浅色/深色，参考主流 Agent 配色） ----------------
THEMES = {
    'light': {
        'name': '浅色',
        'bg': '#f5f6f8', 'side': '#ffffff', 'card': '#ffffff',
        'user_bg': '#0b5394', 'user_fg': '#ffffff',
        'agent_bg': '#ffffff', 'agent_fg': '#1f2328', 'agent_border': '#e2e8ef',
        'meta': '#8a94a6', 'accent': '#0b5394', 'accent_bg': '#eaf2fa',
        'h': '#152233', 'code_bg': '#f2f4f7', 'code_fg': '#b8334b', 'quote': '#6b7a90',
        'input_bg': '#ffffff', 'input_border': '#d5dde6', 'status': '#8a94a6',
        'btn_bg': '#ffffff', 'btn_fg': '#2b3a4a', 'hover': '#eef2f7',
    },
    'dark': {
        'name': '深色',
        'bg': '#1a1b20', 'side': '#202127', 'card': '#26272e',
        'user_bg': '#2d6cb8', 'user_fg': '#ffffff',
        'agent_bg': '#26272e', 'agent_fg': '#e8e8ea', 'agent_border': '#34363f',
        'meta': '#7e8898', 'accent': '#6ea8ff', 'accent_bg': '#2a3550',
        'h': '#f0f2f5', 'code_bg': '#30323a', 'code_fg': '#ff8fa3', 'quote': '#99a3b5',
        'input_bg': '#26272e', 'input_border': '#3c3f49', 'status': '#7e8898',
        'btn_bg': '#2c2e36', 'btn_fg': '#d8dce4', 'hover': '#353843',
    },
}

def ui_load():
    try:
        with open(UI_CFG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'theme': 'light'}

def ui_save(cfg):
    try:
        os.makedirs(os.path.dirname(UI_CFG_PATH), exist_ok=True)
        with open(UI_CFG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_sessions():
    try:
        with open(SESSIONS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'sessions': [], 'current': 0}

def save_sessions(s):
    try:
        os.makedirs(os.path.dirname(SESSIONS_PATH), exist_ok=True)
        with open(SESSIONS_PATH, 'w', encoding='utf-8') as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ---------------- Markdown 轻量渲染器 ----------------
# 支持：标题/粗体/行内代码/代码块/列表/引用/表格（保留文本结构）
INLINE_BOLD = re.compile(r'\*\*(.+?)\*\*')
INLINE_CODE = re.compile(r'`([^`]+)`')

def md_segments(md):
    """Markdown → [(text, tag)] 段序列（供 Text 渲染与流式打字）"""
    segs = []
    in_code = False
    code_lines = []
    for raw in (md or '').split('\n'):
        line = raw.rstrip()
        if line.strip().startswith('```'):
            if in_code:
                segs.append(('\n'.join(code_lines), 'code'))
                code_lines = []
            in_code = not in_code
            segs.append(('', 'normal'))
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            segs.append(('', 'normal'))
            continue
        if line.startswith('### '):
            segs.append((line[4:].strip(), 'h3'))
            continue
        if line.startswith('## '):
            segs.append((line[3:].strip(), 'h2'))
            continue
        if line.startswith('# '):
            segs.append((line[2:].strip(), 'h1'))
            continue
        if re.match(r'^\s*[-*]\s+', line):
            segs.append(('•  ' + re.sub(r'^\s*[-*]\s+', '', line), 'li'))
            continue
        if re.match(r'^\s*\d+\.\s+', line):
            segs.append(('   ' + line.strip(), 'li'))
            continue
        if line.strip().startswith('|'):
            segs.append((line.strip(), 'quote'))
            continue
        if line.strip().startswith('>'):
            segs.append(('💡 ' + line.strip()[1:].strip(), 'quote'))
            continue
        # 行内样式：粗体/行内代码
        out = []
        pos = 0
        toks = []
        for m in INLINE_BOLD.finditer(line):
            toks.append((line[pos:m.start()], 'normal')); toks.append((m.group(1), 'b')); pos = m.end()
        if pos < len(line):
            toks.append((line[pos:], 'normal'))
        for t, tg in toks:
            p2 = 0
            for m in INLINE_CODE.finditer(t):
                if m.start() > p2:
                    segs.append((t[p2:m.start()], tg))
                segs.append((m.group(1), 'code'))
                p2 = m.end()
            if p2 < len(t):
                segs.append((t[p2:], tg))
    if in_code and code_lines:
        segs.append(('\n'.join(code_lines), 'code'))
    if not segs:
        segs.append((md or '', 'normal'))
    return segs

def elide(text, n=80):
    text = text.replace('\n', ' ').strip()
    return text if len(text) <= n else text[:n] + '…'

FONT = ('Microsoft YaHei UI', 10)
FONT_B = ('Microsoft YaHei UI', 10, 'bold')
FONT_S = ('Microsoft YaHei UI', 9)
FONT_T = ('Microsoft YaHei UI', 8)
FONT_MONO = ('Consolas', 9)

CARD_PROMPTS = [
    ('🧑 个人用药咨询', '老年人多重用药要注意什么？', '用药安全顾问'),
    ('🏥 医院药事建设', '药事管理与药物治疗学委员会有哪些职责？', '机构管理顾问'),
    ('✅ GSP 合规自查', 'GSP自查', '交互式清单'),
    ('📐 药物经济学', '成本10000元效果8 vs 成本15000元效果9 方案是否划算？', 'ICER 计算'),
    ('🔬 深度研究', '深度研究 药品不良反应监测体系', '多路检索报告'),
    ('👥 虚拟委员会', 'magic 虚拟药事委员会', '多智能体会谈'),
]

class ChatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('LeebertyPharmacyAdministration · 药事管理智能 Agent')
        self.geometry('1240x780')
        self.minsize(980, 620)
        cfg = ui_load()
        self.theme_name = cfg.get('theme', 'light')
        self.theme = THEMES.get(self.theme_name, THEMES['light'])
        self.role = None
        self.paradigm = 'adaptive'
        self.checklist_state = None
        self.busy = False
        self.sessions = load_sessions()
        self.chunks, self.idf = load_kb()
        self._ensure_session()
        self._build_menu()
        self._build_sidebar()
        self._build_main()
        self._apply_theme()
        self.render_session()
        self.update_badge()
        self.protocol('WM_DELETE_WINDOW', self.on_close)

    # ------------- 会话管理（侧边栏，仿主流 Agent） -------------
    def _ensure_session(self):
        if not self.sessions.get('sessions'):
            self.sessions['sessions'] = [self._new_session_obj(0)]
            self.sessions['current'] = 0
            save_sessions(self.sessions)

    def _new_session_obj(self, idx):
        return {'id': idx, 'title': '新会话', 'role': None, 'paradigm': 'adaptive', 'history': [], 'state': None, 'created': datetime.datetime.now().strftime('%m-%d %H:%M')}

    def _cur_session(self):
        s = self.sessions['sessions']
        i = self.sessions.get('current', 0)
        return s[i] if s and i < len(s) else s[0]

    def new_session(self, clear_messages=True):
        s = self.sessions['sessions']
        s.append(self._new_session_obj(len(s)))
        self.sessions['current'] = len(s) - 1
        save_sessions(self.sessions)
        self._refresh_listbox()
        if clear_messages:
            self.render_session()

    def delete_session(self):
        s = self.sessions['sessions']
        i = self.sessions.get('current', 0)
        if len(s) <= 1:
            messagebox.showinfo('提示', '至少保留一个会话', parent=self)
            return
        del s[i]
        self.sessions['current'] = max(0, i - 1)
        save_sessions(self.sessions)
        self._refresh_listbox()
        self.render_session()

    def open_session(self, idx):
        if 0 <= idx < len(self.sessions['sessions']):
            self.sessions['current'] = idx
            save_sessions(self.sessions)
            self._refresh_listbox()
            self.render_session()

    def _refresh_listbox(self):
        self.side_list.delete(0, 'end')
        for s in self.sessions['sessions']:
            title = s.get('title') or '新会话'
            self.side_list.insert('end', '  ' + elide(title, 14))
        cur = self.sessions.get('current', 0)
        if cur < self.side_list.size():
            self.side_list.selection_set(cur)

    # ------------- 菜单 -------------
    def _build_menu(self):
        menubar = tk.Menu(self)
        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(label='新建会话', command=self.new_session)
        m_file.add_separator()
        m_file.add_command(label='退出', command=self.on_close)
        menubar.add_cascade(label='文件', menu=m_file)

        m_view = tk.Menu(menubar, tearoff=0)
        self.theme_var = tk.StringVar(value=self.theme_name)
        m_view.add_radiobutton(label='浅色主题', value='light', variable=self.theme_var, command=lambda: self.set_theme('light'))
        m_view.add_radiobutton(label='深色主题', value='dark', variable=self.theme_var, command=lambda: self.set_theme('dark'))
        m_view.add_separator()
        m_para = tk.Menu(m_view, tearoff=0)
        self.para_var = tk.StringVar(value='adaptive')
        for ptext in (('自适应（推荐）', 'adaptive'), ('ReAct（思考-行动）', 'react'), ('Plan-and-Solve（先规划）', 'plan'), ('Reflection（反思修订）', 'reflection')):
            m_para.add_radiobutton(label=ptext[0], value=ptext[1], variable=self.para_var, command=lambda v=ptext[1]: setattr(self, 'paradigm', v))
        m_view.add_cascade(label='Agent 范式', menu=m_para)
        menubar.add_cascade(label='视图', menu=m_view)

        m_set = tk.Menu(menubar, tearoff=0)
        m_set.add_command(label='大模型 API 设置…', command=self.open_settings)
        m_set.add_command(label='查看当前配置', command=self.show_llm_status)
        menubar.add_cascade(label='设置', menu=m_set)

        m_help = tk.Menu(menubar, tearoff=0)
        m_help.add_command(label='使用说明', command=self.show_help)
        m_help.add_command(label='关于', command=self.show_about)
        menubar.add_cascade(label='帮助', menu=m_help)
        self.config(menu=menubar)

    # ------------- 侧边栏（会话列表） -------------
    def _build_sidebar(self):
        side = tk.Frame(self, width=232)
        side.pack(side='left', fill='y')
        side.pack_propagate(False)
        tk.Button(side, text='＋ 新建会话', command=self.new_session, relief='flat', font=FONT_S, padx=8, pady=6).pack(fill='x', padx=8, pady=(10, 6))
        self.side_list = tk.Listbox(side, relief='flat', font=FONT_S, activestyle='none', highlightthickness=0, borderwidth=0)
        self.side_list.pack(fill='both', expand=True, padx=8, pady=2)
        self.side_list.bind('<<ListboxSelect>>', self._on_select_session)
        tk.Button(side, text='🗑 删除当前会话', command=self.delete_session, relief='flat', font=FONT_T, padx=8, pady=4).pack(fill='x', padx=8, pady=6)

    def _on_select_session(self, event=None):
        sel = self.side_list.curselection()
        if sel:
            self.open_session(sel[0])

    # ------------- 主区域：欢迎卡片 + 消息流 -------------
    def _build_main(self):
        # ChatGPT 式右列：状态栏(底) → 输入区(底) → 消息区(顶部填满)
        main = tk.Frame(self, padx=0, pady=0)
        main.pack(side='left', fill='both', expand=True)
        self.main = main
        self.status = tk.Label(main, text='', anchor='w', font=FONT_T, padx=16, pady=3)
        self.status.pack(side='bottom', fill='x')
        self.hint = tk.Label(main, text='Enter 发送 · Shift+Enter 换行 · 指令：GSP自查 / 深度研究 / 模板 / 好评', font=FONT_T, anchor='w', padx=16)
        self.hint.pack(side='bottom', fill='x', pady=(0, 4))
        ibar = tk.Frame(main, highlightthickness=1)
        ibar.pack(side='bottom', fill='x', padx=14, pady=(0, 8))
        self.entry = tk.Text(ibar, height=2, wrap='word', font=FONT, relief='flat', borderwidth=0, padx=12, pady=8)
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', self._on_enter)
        self.entry.bind('<KeyRelease>', self._auto_height)
        self.send_btn = tk.Button(ibar, text='➤ 发送', width=8, relief='flat', font=FONT_S, pady=6, command=self.send)
        self.send_btn.pack(side='right', padx=6, pady=6)
        wrap = tk.Frame(main)
        wrap.pack(side='top', fill='both', expand=True, padx=14, pady=(10, 4))
        self.chat = tk.Text(wrap, wrap='word', relief='flat', borderwidth=0, font=FONT, cursor='arrow', spacing1=2, spacing3=6)
        sb = ttk.Scrollbar(wrap, orient='vertical', command=self.chat.yview)
        self.chat.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.chat.pack(side='left', fill='both', expand=True)
        self.chat.bind('<Button-3>', self._chat_menu)
        self.cards = tk.Frame(main)
        self.cards.place(relx=0.5, rely=0.05, anchor='n', relwidth=0.92)
        self._build_cards()

    def _build_cards(self):
        for w in self.cards.winfo_children():
            w.destroy()
        tk.Label(self.cards, text='早上好！今天想咨询什么？', font=('Microsoft YaHei UI', 16, 'bold'), anchor='w').pack(fill='x', pady=(4, 4))
        tk.Label(self.cards, text='药事管理智能 Agent · 本地知识库 × 工具 × 可选大模型', font=FONT_S, anchor='w').pack(fill='x', pady=(0, 12))
        grid = tk.Frame(self.cards)
        grid.pack(fill='x')
        for i in range(0, len(CARD_PROMPTS), 2):
            row = tk.Frame(grid)
            row.pack(fill='x', pady=4)
            for title, prompt, sub in CARD_PROMPTS[i:i + 2]:
                card = tk.Frame(row, padx=14, pady=10, highlightthickness=1)
                card.pack(side='left', fill='x', expand=True, padx=4)
                tk.Label(card, text=title, font=FONT_B, anchor='w').pack(fill='x')
                tk.Label(card, text=sub, font=FONT_T, anchor='w').pack(fill='x', pady=(2, 6))
                tk.Label(card, text='提问 →', font=FONT_T, anchor='w').pack(fill='x')
                card.bind('<Button-1>', lambda e, p=prompt: self.send_text(p))
                for child in card.winfo_children():
                    child.bind('<Button-1>', lambda e, p=prompt: self.send_text(p))

    def hide_cards(self):
        self.cards.place_forget()

    def show_cards(self):
        if not self.chat.get('1.0', 'end').strip():
            self.cards.place(relx=0.5, rely=0.05, anchor='n', relwidth=0.92)

    # ------------- 消息渲染（Markdown 富文本 + 流式打字） -------------
    def _tag_config(self):
        t = self.theme
        self.chat.tag_config('meta', foreground=t['meta'], font=FONT_T, spacing1=8)
        self.chat.tag_config('h1', foreground=t['h'], font=('Microsoft YaHei UI', 13, 'bold'), spacing1=8, spacing3=4)
        self.chat.tag_config('h2', foreground=t['h'], font=('Microsoft YaHei UI', 12, 'bold'), spacing1=6, spacing3=3)
        self.chat.tag_config('h3', foreground=t['h'], font=FONT_B, spacing1=4)
        self.chat.tag_config('b', foreground=t['agent_fg'], font=FONT_B)
        self.chat.tag_config('code', font=FONT_MONO, foreground=t['code_fg'], background=t['code_bg'])
        self.chat.tag_config('li', foreground=t['agent_fg'], lmargin1=18, lmargin2=14)
        self.chat.tag_config('quote', foreground=t['quote'], font=FONT_S, lmargin1=10, lmargin2=10)
        self.chat.tag_config('user', background=t['user_bg'], foreground=t['user_fg'], font=FONT, spacing1=6, spacing3=6, rmargin=48, lmargin1=56, lmargin2=56)
        self.chat.tag_config('agent', font=FONT, spacing1=6, spacing3=6)
        self.chat.tag_config('src', foreground=t['accent'], font=FONT_T, spacing1=2)
        self.chat.tag_config('tool', foreground=t['quote'], font=FONT_T, spacing1=2)

    def _render_md(self, tag, text):
        """把 markdown 渲染进 Text"""
        segs = md_segments(text)
        self.chat.insert('end', '', (tag,))
        for s, tg in segs:
            if not s:
                continue
            tags = (tag, 'agent') if tg == 'normal' else (tag, tg)
            self.chat.insert('end', s + '\n', tags)
        self.chat.insert('end', '', (tag,))
        self.chat.insert('end', '\n')
        self.chat.see('end')

    def _stream_render(self, tag, text):
        """流式打字：逐段揭示已解析的 Markdown（保留样式标签）"""
        self._stream_segs = md_segments(text)
        self._stream_idx = 0
        self.chat.insert('end', '', (tag,))
        self._stream_tick(tag)

    def _stream_tick(self, tag):
        if self._stream_idx >= len(self._stream_segs):
            self.chat.insert('end', '\n')
            self.chat.see('end')
            return
        s, tg = self._stream_segs[self._stream_idx]
        self._stream_idx += 1
        if s:
            tags = (tag, 'agent') if tg == 'normal' else (tag, tg)
            self.chat.insert('end', s + '\n', tags)
            self.chat.see('end')
        delay = 10 if len(s) > 16 else 22
        self.after(delay, lambda: self._stream_tick(tag))

    def add_user_msg(self, text):
        self._render_md('user', text)

    def add_agent_msg(self, text, meta=None, sources=None, tool_steps=None, stream=False):
        if meta:
            self.chat.insert('end', meta + '\n', 'meta')
        if stream and len(text) > 90:
            self._stream_render('agent', text)
        else:
            self._render_md('agent', text)
        if sources:
            self.chat.insert('end', '📄 来源：' + '；'.join(sources[:3]) + '\n', 'src')
        if tool_steps:
            self.chat.insert('end', '🧠 思考过程：' + ' → '.join(tool_steps[:6]), 'tool')
            self.chat.insert('end', '\n', 'tool')
        self.chat.see('end')

    def _chat_menu(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='复制选中', command=lambda: self.chat.event_generate('<<Copy>>'))
        menu.add_separator()
        menu.add_command(label='复制全部对话', command=self._copy_all)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_all(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.chat.get('1.0', 'end'))
            self.status.config(text='已复制全部对话')
        except Exception:
            pass

    # ------------- 输入区（多行自适应，Enter 发送 / Shift+Enter 换行） -------------
    # _build_input 已并入 _build_main（ChatGPT 式右列布局）


    # _build_statusbar 已并入 _build_main


    # ------------- 输入区交互 -------------
    def _on_enter(self, event):
        if event.state & 0x0001:
            self.entry.insert('insert', '\n')
            return 'break'
        self.send()
        return 'break'

    def _auto_height(self, event=None):
        lines = int(self.entry.index('end-1c').split('.')[0])
        self.entry.configure(height=max(1, min(6, lines)))

    # ------------- 对话流程 -------------
    def send(self, event=None):
        q = self.entry.get('1.0', 'end').strip()
        if not q or self.busy:
            return
        self.entry.delete('1.0', 'end')
        self._auto_height()
        self.send_text(q)

    def send_text(self, text):
        if self.busy:
            return
        if text == 'magic 虚拟药事委员会':
            self.add_user_msg('👥 召开虚拟药事委员会：基层医疗机构如何提升合理用药')
            self._run_committee('基层医疗机构如何提升合理用药')
            return
        self.add_user_msg(text if text != 'reset' else '🔄 重置会话')
        self._process(text)

    def _run_committee(self, topic):
        self.set_busy(True, '👥 委员会会谈中…')

        def work():
            from multi_agent import speak, MEMBERS
            parts = []
            try:
                for m in MEMBERS:
                    speech, src = speak(m, topic, self.chunks, self.idf)
                    parts.append('【%s】\n%s' % (m['name'], speech))
            except Exception as e:
                parts.append('委员会执行出错：%s' % e)
            self.after(0, lambda: self._finish_committee('\n\n'.join(parts)))

        threading.Thread(target=work, daemon=True).start()

    def _finish_committee(self, text):
        self.add_agent_msg(text, meta='👥 虚拟药事委员会', tool_steps=['角色会谈 ×3'])
        self.set_busy(False)
        self._remember_session()

    def set_busy(self, b, status=None):
        self.busy = b
        self.send_btn.config(state='disabled' if b else 'normal')
        if status:
            self.status.config(text=status)
        if b:
            self.chat.insert('end', '⏳ 思考中…\n', 'tool')
            self.chat.see('end')

    def _process(self, q):
        self.set_busy(True, '思考中…')
        cur = self._cur_session()

        def handle(resp):
            try:
                self._finish(resp)
            except Exception as e:
                self.status.config(text='渲染错误：%s' % e)

        if llm_mod.is_configured():
            # AI 模式：网络调用放后台线程，避免阻塞 UI
            def work():
                try:
                    resp = build_reply(q, cur.get('role'), cur.get('state'), cur['history'], True, self.paradigm)
                except Exception as e:
                    resp = {'reply': '处理出错：%s' % e, 'role': cur.get('role'), 'state': cur.get('state'), 'sources': [], 'llm': False, 'model': '', 'llm_error': str(e), 'trace': ['异常']}
                try:
                    self.after(0, lambda: handle(resp))
                except Exception:
                    pass
            threading.Thread(target=work, daemon=True).start()
        else:
            # 本地模式：主线程同步执行（毫秒级），规避 tkinter 跨线程限制
            try:
                resp = build_reply(q, cur.get('role'), cur.get('state'), cur['history'], True, self.paradigm)
            except Exception as e:
                resp = {'reply': '处理出错：%s' % e, 'role': cur.get('role'), 'state': cur.get('state'), 'sources': [], 'llm': False, 'model': '', 'llm_error': str(e), 'trace': ['异常']}
            handle(resp)

    def _remove_thinking(self):
        try:
            content = self.chat.get('1.0', 'end').rstrip()
            idx = content.rfind('⏳ 思考中…')
            if idx >= 0:
                pre = content[:idx]
                self.chat.delete('%d.%d' % (pre.count('\n') + 1, 0), 'end')
        except Exception:
            pass

    def _finish(self, resp):
        self._remove_thinking()
        cur = self._cur_session()
        cur['role'] = resp.get('role', cur.get('role'))
        cur['state'] = resp.get('state')
        meta = None
        if resp.get('llm') and resp.get('model'):
            meta = '🤖 ' + resp['model']
        elif resp.get('llm_error'):
            meta = '📚 本地（AI 调用失败已降级）'
        trace = resp.get('trace') or []
        steps = [x for x in trace if ('工具' in x or '检索' in x or '范式' in x)][:6]
        self.add_agent_msg(resp.get('reply', ''), meta=meta, sources=resp.get('sources'), tool_steps=steps or None, stream=bool(resp.get('llm')))
        if not cur.get('title') or cur.get('title') == '新会话':
            for h in cur.get('history', []):
                if h.get('role') == 'user':
                    cur['title'] = elide(h.get('content', ''), 16)
                    break
        self._remember_session()
        self._add_feedback_row()
        self.set_busy(False)
        self.update_badge()
        self.hide_cards()
        self.entry.focus_set()

    def _add_feedback_row(self):
        cur = self._cur_session()
        q_text = ''
        last_reply = ''
        for h in reversed(cur.get('history', [])):
            if h.get('role') == 'user' and not q_text:
                q_text = h.get('content', '')
            if h.get('role') == 'assistant':
                last_reply = h.get('content', '')
                break
        if not last_reply:
            return
        row = tk.Frame(self.main)
        row.pack(side='bottom', fill='x', padx=18, pady=(0, 2))
        tk.Label(row, text='这条回答有用吗？', font=FONT_T).pack(side='left')

        def give(rating, b1, b2):
            n = memory.record_feedback(q_text, last_reply, rating)
            self.status.config(text='已记录%s（偏好数据 %d 条，用于模型优化）' % ('好评' if rating else '差评', n or 0))
            b1.config(state='disabled')
            b2.config(state='disabled')

        ok = tk.Button(row, text='👍 有用', font=FONT_T, relief='flat', command=lambda: give(1, ok, bad))
        bad = tk.Button(row, text='👎 待改进', font=FONT_T, relief='flat', command=lambda: give(0, ok, bad))
        ok.pack(side='left', padx=4)
        bad.pack(side='left', padx=2)

    # ------------- 会话渲染与主题 -------------
    def render_session(self):
        self.chat.delete('1.0', 'end')
        cur = self._cur_session()
        self.paradigm = cur.get('paradigm', 'adaptive')
        for h in cur.get('history') or []:
            if h.get('role') == 'user':
                self.add_user_msg(h.get('content', ''))
            elif h.get('role') == 'assistant':
                self.add_agent_msg(h.get('content', ''))
        self._refresh_listbox()
        self.show_cards()
        self._apply_theme()

    def _remember_session(self):
        save_sessions(self.sessions)
        self._refresh_listbox()

    def set_theme(self, name):
        self.theme_name = name
        self.theme = THEMES[name]
        ui_save({'theme': name})
        self._apply_theme()

    def _apply_theme(self):
        t = self.theme
        try:
            self.configure(bg=t['bg'])
            self.chat.configure(bg=t['bg'], fg=t['agent_fg'], insertbackground=t['agent_fg'])
            self.side_list.configure(bg=t['side'], fg=t['h'], selectbackground=t['accent'], selectforeground='#ffffff')
            self.main.configure(bg=t['bg'])
            self.entry.configure(bg=t['input_bg'], fg=t['agent_fg'], insertbackground=t['agent_fg'])
            self.hint.configure(bg=t['bg'], fg=t['status'])
            self.status.configure(bg=t['bg'], fg=t['status'])
            self.send_btn.configure(bg=t['accent'], fg='#ffffff', activebackground=t['accent'])
            for slave in self.main.winfo_children():
                if isinstance(slave, (tk.Frame, tk.Label)):
                    try:
                        slave.configure(bg=t['bg'], highlightbackground=t['agent_border'])
                    except Exception:
                        pass
            self.cards.configure(bg=t['bg'])
            self._apply_cards_theme()
            self._tag_config()
        except Exception:
            pass

    def _apply_cards_theme(self):
        t = self.theme
        for child in self.cards.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(bg=t['bg'], fg=t['h'])
            elif isinstance(child, tk.Frame):
                child.configure(bg=t['bg'])
                for row in child.winfo_children():
                    if isinstance(row, tk.Frame):
                        row.configure(bg=t['bg'])
                        for card in row.winfo_children():
                            if isinstance(card, tk.Frame):
                                card.configure(bg=t['card'], highlightbackground=t['agent_border'])
                                for lbl in card.winfo_children():
                                    if isinstance(lbl, tk.Label):
                                        lbl.configure(bg=t['card'], fg=t['agent_fg'])

    def update_badge(self):
        cfg = llm_mod.load_config()
        parts = ['知识库 %d 块' % len(self.chunks), '范式 ' + self.paradigm]
        if llm_mod.is_configured(cfg):
            parts.append('🤖 ' + cfg['model'])
        else:
            parts.append('📚 本地模式')
        self.status.config(text=' | '.join(parts))

    # ------------- 设置：大模型 -------------
    def open_settings(self):
        SettingsDialog(self, on_saved=self.update_badge)

    def show_llm_status(self):
        messagebox.showinfo('大模型配置', llm_mod.status_text(), parent=self)

    def show_help(self):
        msg = '\n'.join([
            '· 提问：直接输入（知识问答 / 四查十对 / ICER 计算…）',
            '· 能力卡片：点击首页卡片快速发起（自查 / 深度研究 / 虚拟委员会）',
            '· 会话：左侧列表新建 / 切换 / 删除，自动保存 memory/sessions.json',
            '· 主题与范式：菜单“视图”切换浅色 / 深色与 Agent 范式',
            '· 反馈：每条回答下方 👍 / 👎 写入偏好数据',
            '· 大模型：菜单“设置 → 大模型 API 设置”',
            '· 指令：help / 模板 / GSP自查 / 深度研究 <主题> / 好评 / 差评',
        ])
        messagebox.showinfo('使用说明', msg, parent=self)

    def show_about(self):
        msg = '\n'.join([
            'LeebertyPharmacyAdministration v4.0',
            '药事管理智能 Agent（现代 UI 版）',
            '',
            '本地知识库 × 药剂工具 × 可选大模型（RAG / ReAct）',
            'UI 参考：ChatGPT / Claude / DeepSeek / Coze / Dify',
            '',
            '⚠️ 知识辅助工具，不构成医疗诊断或法律意见。',
        ])
        messagebox.showinfo('关于', msg, parent=self)

    def on_close(self):
        save_sessions(self.sessions)
        ui_save({'theme': self.theme_name})
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """大模型 API 设置对话框"""
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.title('大模型 API 设置')
        self.geometry('560x480')
        self.resizable(False, False)
        self.on_saved = on_saved
        cfg = llm_mod.load_config()
        self.var_base = tk.StringVar(value=cfg.get('api_base', ''))
        self.var_key = tk.StringVar(value=cfg.get('api_key', ''))
        self.var_model = tk.StringVar(value=cfg.get('model', ''))
        self.var_temp = tk.StringVar(value=str(cfg.get('temperature', 0.3)))
        self.var_tokens = tk.StringVar(value=str(cfg.get('max_tokens', 1400)))
        self.var_enabled = tk.BooleanVar(value=bool(cfg.get('enabled')))
        body = tk.Frame(self, padx=18, pady=14)
        body.pack(fill='both', expand=True)
        tk.Label(body, text='支持任意 OpenAI 兼容接口（/chat/completions）：DeepSeek / OpenAI / 智谱 / 通义 / Kimi / Ollama。密钥仅保存在本机 config.json。',
                 font=FONT_S, wraplength=510, justify='left').pack(anchor='w', pady=(0, 10))

        def field(label, var, show=None):
            row = tk.Frame(body)
            row.pack(fill='x', pady=4)
            tk.Label(row, text=label, width=11, anchor='w', font=FONT_S).pack(side='left')
            tk.Entry(row, textvariable=var, font=FONT_S, relief='solid', bd=1, show=show).pack(side='left', fill='x', expand=True, ipady=3)

        field('API 地址', self.var_base)
        field('API 密钥', self.var_key, show='*')
        field('模型名', self.var_model)
        row = tk.Frame(body)
        row.pack(fill='x', pady=4)
        tk.Label(row, text='温度', width=11, anchor='w', font=FONT_S).pack(side='left')
        tk.Entry(row, textvariable=self.var_temp, width=8, font=FONT_S, relief='solid', bd=1).pack(side='left', ipady=3)
        tk.Label(row, text='最大输出 token', font=FONT_S).pack(side='left', padx=(14, 4))
        tk.Entry(row, textvariable=self.var_tokens, width=8, font=FONT_S, relief='solid', bd=1).pack(side='left', ipady=3)
        tk.Checkbutton(body, text='启用 AI 模式（回答由大模型结合知识库生成，失败自动回退本地）',
                       variable=self.var_enabled, font=FONT_S, anchor='w', justify='left').pack(fill='x', pady=(10, 2))
        self.test_label = tk.Label(body, text='', font=FONT_S, wraplength=510, justify='left')
        self.test_label.pack(anchor='w', pady=(8, 0))
        foot = tk.Frame(self)
        foot.pack(fill='x', side='bottom', padx=18, pady=10)
        tk.Button(foot, text='测试连接', relief='flat', command=self.test_conn).pack(side='left')
        tk.Button(foot, text='保存配置', relief='flat', command=self.save).pack(side='right')
        self.transient(master)
        self.grab_set()
        self.focus_set()

    def _cfg_from_vars(self):
        return {
            'api_base': self.var_base.get().strip(),
            'api_key': self.var_key.get().strip(),
            'model': self.var_model.get().strip(),
            'temperature': float(self.var_temp.get() or 0.3),
            'max_tokens': int(self.var_tokens.get() or 1400),
        }

    def test_conn(self):
        self.test_label.config(text='测试连接中…')

        def work():
            ok, msg = llm_mod.test_connection(self._cfg_from_vars())
            self.after(0, lambda: self.test_label.config(text=('✅ ' + msg) if ok else ('❌ ' + msg)))

        threading.Thread(target=work, daemon=True).start()

    def save(self):
        cfg = llm_mod.load_config()
        for k, v in self._cfg_from_vars().items():
            cfg[k] = v
        cfg['enabled'] = bool(self.var_enabled.get())
        llm_mod.save_config(cfg)
        if self.on_saved:
            self.on_saved()
        msg = ('✅ AI 模式已启用（' + cfg['model'] + '）') if llm_mod.is_configured(cfg) else '⚠️ 已保存但未启用（需填写地址/密钥/模型并勾选启用）'
        messagebox.showinfo('保存成功', msg, parent=self)
        if llm_mod.is_configured(cfg):
            self.destroy()


def main():
    if '--smoke' in sys.argv:
        app = ChatApp()
        app.withdraw()
        history = []
        r1 = build_reply('GxP 包含哪些规范？', None, None, history, False)
        r2 = build_reply('四查十对是什么', None, None, history, False)
        r3 = build_reply('我是公司', None, None, history, False)
        s = build_reply('GSP自查', None, None, history, False)
        s1 = build_reply('是', None, s.get('state'), history, False)
        ok = bool(r1.get('reply')) and bool(r2.get('reply')) and r3.get('role') == 'company'
        ok = ok and bool(s.get('state')) and bool(s1.get('reply'))
        print('SMOKE_RESULT=%s chunks=%d md_segs=%d' % (ok, len(app.chunks), len(md_segments(r1.get('reply', '')))))
        app.destroy()
        return
    app = ChatApp()
    app.mainloop()


if __name__ == '__main__':
    main()