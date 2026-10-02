# -*- coding: utf-8 -*-
# gui.py — LeebertyPharmacyAdministration 桌面应用（tkinter 原生窗口，纯标准库，无需浏览器）
# 启动：python agent/gui.py   或双击 start_app.bat（pythonw 无控制台）
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
from tkinter import ttk, messagebox

from engine import load_kb
from server import build_reply
import llm as llm_mod

BG = '#eef4fa'
USER_BG = '#0b5394'
USER_FG = '#ffffff'
AGENT_BG = '#ffffff'
AGENT_FG = '#24384d'
AGENT_BORDER = '#dbe7f2'
META_FG = '#7d94a8'
SRC_FG = '#4a86b8'
FONT = ('Microsoft YaHei UI', 10)
FONT_SMALL = ('Microsoft YaHei UI', 9)
FONT_META = ('Microsoft YaHei UI', 8)

CHECKLIST_CHOICES = ['GSP自查（药品经营）', '机构自查（医疗机构）', '五专自查（麻精药品）', '不良反应自查']

class ChatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('LeebertyPharmacyAdministration · 药事管理智能 Agent')
        self.geometry('1000x720')
        self.minsize(860, 560)
        self.configure(bg=BG)
        self.role = None
        self.history = []
        self.checklist_state = None
        self.busy = False
        self.chunks, self.idf = load_kb()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._build_input()
        self._build_chat()
        self._welcome()
        self.update_badge()
        self.protocol('WM_DELETE_WINDOW', self.on_close)

    # ---------- 菜单 ----------
    def _build_menu(self):
        menubar = tk.Menu(self)
        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(label='退出', command=self.on_close)
        menubar.add_cascade(label='文件', menu=m_file)
        m_set = tk.Menu(menubar, tearoff=0)
        m_set.add_command(label='大模型 API 设置…', command=self.open_settings)
        m_set.add_command(label='查看当前配置', command=self.show_llm_status)
        menubar.add_cascade(label='设置', menu=m_set)
        m_help = tk.Menu(menubar, tearoff=0)
        m_help.add_command(label='使用说明', command=self.show_help)
        m_help.add_command(label='关于', command=self.show_about)
        menubar.add_cascade(label='帮助', menu=m_help)
        self.config(menu=menubar)

    # ---------- 顶部工具条 ----------
    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BG, padx=10, pady=6)
        bar.pack(side='top', fill='x')
        role_map = {'personal': '个人', 'org': '机构', 'company': '公司'}
        for text, role in (('🧑 个人', 'personal'), ('🏥 集体', 'org'), ('🏢 公司', 'company')):
            b = tk.Button(bar, text=text, width=8, bg='#ffffff', fg='#0b5394',
                          activebackground='#eaf4fc', relief='flat',
                          command=lambda r=role: self.send_text('我是' + role_map[r]))
            b.pack(side='left', padx=3, pady=2)
        tip = tk.Label(bar, text='自查：', bg=BG, fg='#3d5a72', font=FONT_SMALL)
        tip.pack(side='left', padx=(12, 2))
        self.cl_combo = ttk.Combobox(bar, values=CHECKLIST_CHOICES, width=16, state='readonly')
        self.cl_combo.current(0)
        self.cl_combo.pack(side='left')
        tk.Button(bar, text='开始自查', width=8, bg='#ffffff', fg='#0b5394',
                  activebackground='#eaf4fc', relief='flat', command=self.start_checklist).pack(side='left', padx=3, pady=2)
        tk.Button(bar, text='📄 模板', bg='#ffffff', fg='#0b5394', activebackground='#eaf4fc',
                  relief='flat', command=lambda: self.send_text('模板')).pack(side='left', padx=3, pady=2)
        tk.Button(bar, text='🔄 重置', bg='#ffffff', fg='#0b5394', activebackground='#eaf4fc',
                  relief='flat', command=lambda: self.send_text('reset')).pack(side='left', padx=3, pady=2)
        self.badge = tk.Label(bar, text='', bg=BG, fg='#3e7c4f', font=FONT_SMALL)
        self.badge.pack(side='right')

    # ---------- 底部输入区与状态栏 ----------
    def _build_statusbar(self):
        self.status = tk.Label(self, text='', anchor='w', bg='#ffffff', fg='#8aa2b8',
                               font=FONT_SMALL, padx=12, pady=3)
        self.status.pack(side='bottom', fill='x')

    def _build_input(self):
        bar = tk.Frame(self, bg='#ffffff', padx=10, pady=8)
        bar.pack(side='bottom', fill='x')
        self.entry = tk.Entry(bar, font=FONT, relief='solid', bd=1)
        self.entry.pack(side='left', fill='x', expand=True, ipady=5)
        self.entry.bind('<Return>', self.send)
        self.send_btn = tk.Button(bar, text='发送', width=8, bg='#0b5394', fg='#ffffff',
                                 activebackground='#0a4480', relief='flat', command=self.send)
        self.send_btn.pack(side='left', padx=(8, 0))

    # ---------- 聊天区（Canvas 滚动消息流） ----------
    def _build_chat(self):
        wrap = tk.Frame(self, bg=BG, padx=10, pady=4)
        wrap.pack(side='top', fill='both', expand=True)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(wrap, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.body = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor='nw')
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', self._canvas_resize)
        self.canvas.bind_all('<MouseWheel>', self._on_wheel)

    def _canvas_resize(self, e):
        self.canvas.itemconfig(self._win, width=max(300, e.width - 20))

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), 'units')

    # ---------- 消息渲染 ----------
    def add_msg(self, who, text, meta=None, sources=None):
        f = tk.Frame(self.body, bg=BG)
        f.pack(fill='x', pady=3)
        meta_text = '你' if who == 'user' else (meta or '📚 本地知识库')
        tk.Label(f, text=meta_text, bg=BG, fg=META_FG, font=FONT_META).pack(anchor='e' if who == 'user' else 'w')
        kw = dict(bg=USER_BG if who == 'user' else AGENT_BG,
                  fg=USER_FG if who == 'user' else AGENT_FG,
                  font=FONT, justify='left', wraplength=600, padx=12, pady=9)
        if who == 'agent':
            kw['highlightthickness'] = 1
            kw['highlightbackground'] = AGENT_BORDER
        tk.Label(f, text=text, **kw).pack(anchor='e' if who == 'user' else 'w', pady=(0, 4))
        for s in (sources or [])[:3]:
            tk.Label(f, text='📄 ' + s, bg=BG, fg=SRC_FG, font=FONT_META).pack(anchor='w')
        self.after(10, lambda: self.canvas.yview_moveto(1.0))

    def _welcome(self):
        n = len(self.chunks)
        welcome = ('您好！我是药事管理智能助手（本地知识库 %d 个知识块）。\n\n'
            + '· 🧑 个人：用药咨询、说明书解读、特殊人群用药、家庭药箱\n'
            + '· 🏥 集体：药事委员会建设、处方点评、麻精五专自查、抗菌药物管理\n'
            + '· 🏢 公司：GxP 体系、GSP/GMP、QA/QC、临床试验 CRA/CRC、药物警戒、药物经济学\n\n'
            + '直接输入问题即可（如：四查十对是什么、GSP自查）。'
            + '点击上方“开始自查”可进行合规自查；菜单“设置→大模型 API 设置”可接入真实大模型。') % n
        self.add_msg('agent', welcome, meta='💊 LeebertyPharmacyAdministration')

    # ---------- 交互 ----------
    def send(self, event=None):
        q = self.entry.get().strip()
        if not q or self.busy:
            return
        self.entry.delete(0, 'end')
        self.add_msg('user', q)
        self._process(q)

    def send_text(self, text):
        if self.busy:
            return
        self.add_msg('user', text if text != 'reset' else '🔄 重置会话')
        self._process(text)

    def start_checklist(self):
        self.send_text(self.cl_combo.get())

    def _process(self, q):
        self.busy = True
        self.send_btn.config(state='disabled')
        self.status.config(text='思考中…')

        def work():
            try:
                resp = build_reply(q, self.role, self.checklist_state, self.history, True)
            except Exception as e:
                resp = {'reply': '处理出错：%s' % e, 'role': self.role, 'state': self.checklist_state,
                        'sources': [], 'llm': False, 'model': '', 'llm_error': str(e)}
            try:
                self.after(0, lambda: self._finish(resp))
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _finish(self, resp):
        self.role = resp.get('role', self.role)
        if 'state' in resp:
            self.checklist_state = resp['state']
        meta = None
        if resp.get('llm') and resp.get('model'):
            meta = '🤖 ' + resp['model']
        self.add_msg('agent', resp.get('reply', ''), meta=meta, sources=resp.get('sources'))
        self.busy = False
        self.send_btn.config(state='normal')
        self.update_badge()
        self.entry.focus_set()

    # ---------- 状态与配置 ----------
    def update_badge(self):
        cfg = llm_mod.load_config()
        if llm_mod.is_configured(cfg):
            self.badge.config(text='🤖 AI 模式 · ' + cfg['model'], fg='#0b5394')
            self.status.config(text='知识库 %d 块 · AI 模式（%s）· 回答由大模型结合知识库生成' % (len(self.chunks), cfg['model']))
        else:
            self.badge.config(text='📚 本地知识库模式', fg='#3e7c4f')
            self.status.config(text='知识库 %d 块 · 未配置大模型（菜单：设置 → 大模型 API 设置）' % len(self.chunks))

    def open_settings(self):
        SettingsDialog(self, on_saved=self.update_badge)

    def show_llm_status(self):
        messagebox.showinfo('大模型配置', llm_mod.status_text(), parent=self)

    def show_help(self):
        messagebox.showinfo('使用说明',
            '· 直接输入问题：知识问答（如：四查十对是什么、GxP 有哪些规范）\n'
            + '· 身份按钮：切换个人/集体/公司服务侧重\n'
            + '· 自查：选择类型后点“开始自查”，逐项输入 是/否，最后给出通过率报告\n'
            + '· 模板：点击“📄 模板”查看制度/记录/培训模板清单\n'
            + '· 大模型：菜单“设置 → 大模型 API 设置”，填入密钥并测试连接\n'
            + '· 重置：清空对话历史与自查状态', parent=self)

    def show_about(self):
        messagebox.showinfo('关于',
            'LeebertyPharmacyAdministration\n药事管理智能 Agent（桌面版）\n\n'
            + '面向个人/集体/公司的药事管理科目服务：\n本地知识库 × 可选真实大模型（RAG 增强）。\n\n'
            + '⚠️ 知识辅助工具，不构成医疗诊断或法律意见；\n用药请遵从医师处方与执业药师指导。', parent=self)

    def on_close(self):
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """大模型 API 设置对话框（OpenAI 兼容，配置保存到 config.json）"""
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.title('大模型 API 设置')
        self.geometry('540x460')
        self.resizable(False, False)
        self.configure(bg='#ffffff')
        self.on_saved = on_saved
        cfg = llm_mod.load_config()
        self.var_base = tk.StringVar(value=cfg.get('api_base', ''))
        self.var_key = tk.StringVar(value=cfg.get('api_key', ''))
        self.var_model = tk.StringVar(value=cfg.get('model', ''))
        self.var_temp = tk.StringVar(value=str(cfg.get('temperature', 0.3)))
        self.var_tokens = tk.StringVar(value=str(cfg.get('max_tokens', 1400)))
        self.var_enabled = tk.BooleanVar(value=bool(cfg.get('enabled')))
        body = tk.Frame(self, bg='#ffffff', padx=18, pady=14)
        body.pack(fill='both', expand=True)
        tk.Label(body, text='支持任意 OpenAI 兼容接口（/chat/completions），如 DeepSeek、OpenAI、智谱、通义、Kimi、Ollama。密钥仅保存在本机 config.json。',
                 bg='#ffffff', fg='#8aa2b8', font=FONT_META, wraplength=490, justify='left').pack(anchor='w', pady=(0, 10))
        def field(label, var, show=None):
            row = tk.Frame(body, bg='#ffffff')
            row.pack(fill='x', pady=4)
            tk.Label(row, text=label, width=11, anchor='w', bg='#ffffff', fg='#3d5a72', font=FONT_SMALL).pack(side='left')
            e = tk.Entry(row, textvariable=var, font=FONT_SMALL, relief='solid', bd=1, show=show)
            e.pack(side='left', fill='x', expand=True, ipady=3)
            return e
        field('API 地址', self.var_base)
        field('API 密钥', self.var_key, show='*')
        field('模型名', self.var_model)
        row = tk.Frame(body, bg='#ffffff')
        row.pack(fill='x', pady=4)
        tk.Label(row, text='温度', width=11, anchor='w', bg='#ffffff', fg='#3d5a72', font=FONT_SMALL).pack(side='left')
        tk.Entry(row, textvariable=self.var_temp, width=8, font=FONT_SMALL, relief='solid', bd=1).pack(side='left', ipady=3)
        tk.Label(row, text='最大输出 token', bg='#ffffff', fg='#3d5a72', font=FONT_SMALL).pack(side='left', padx=(14, 4))
        tk.Entry(row, textvariable=self.var_tokens, width=8, font=FONT_SMALL, relief='solid', bd=1).pack(side='left', ipady=3)
        tk.Checkbutton(body, text='启用 AI 模式（回答由大模型结合本地知识库生成，失败自动回退本地）',
                       variable=self.var_enabled, bg='#ffffff', fg='#3d5a72', font=FONT_SMALL, anchor='w', justify='left').pack(fill='x', pady=(10, 2))
        self.test_label = tk.Label(body, text='', bg='#ffffff', fg='#3e7c4f', font=FONT_SMALL, wraplength=490, justify='left')
        self.test_label.pack(anchor='w', pady=(8, 0))
        foot = tk.Frame(self, bg='#f5f9fc', padx=18, pady=10)
        foot.pack(fill='x', side='bottom')
        tk.Button(foot, text='测试连接', bg='#ffffff', fg='#0b5394', relief='flat',
                  command=self.test_conn).pack(side='left')
        tk.Button(foot, text='保存配置', bg='#0b5394', fg='#ffffff', relief='flat',
                  command=self.save).pack(side='right')
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
        self.test_label.config(text='测试连接中…', fg='#8aa2b8')

        def work():
            ok, msg = llm_mod.test_connection(self._cfg_from_vars())
            self.after(0, lambda: self._on_test(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _on_test(self, ok, msg):
        self.test_label.config(text=('✅ ' + msg) if ok else ('❌ ' + msg),
                               fg='#3e7c4f' if ok else '#c0392b')

    def save(self):
        cfg = llm_mod.load_config()
        for k, v in self._cfg_from_vars().items():
            cfg[k] = v
        cfg['enabled'] = bool(self.var_enabled.get())
        llm_mod.save_config(cfg)
        if self.on_saved:
            self.on_saved()
        if llm_mod.is_configured(cfg):
            msg = '✅ AI 模式已启用（' + cfg['model'] + '）'
        else:
            msg = '⚠️ 已保存但未启用（需填写地址/密钥/模型并勾选启用）'
        messagebox.showinfo('保存成功', msg, parent=self)
        if llm_mod.is_configured(cfg):
            self.destroy()


def main():
    if '--smoke' in sys.argv:
        # 自检模式：验证核心链路后自动退出（无窗口交互，需用 python 运行以输出结果）
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
        print('SMOKE_RESULT=%s chunks=%d role=%s checklist_step=%s'
              % (ok, len(app.chunks), r3.get('role'), bool(s1.get('reply'))))
        app.destroy()
        return
    app = ChatApp()
    app.mainloop()


if __name__ == '__main__':
    main()