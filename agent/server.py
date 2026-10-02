# -*- coding: utf-8 -*-
# server.py — LeebertyPharmacyAdministration 本地 Web 服务（http.server，纯标准库）
import os
import sys
import json
import argparse
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import load_kb, make_answer
from services import (detect_intent, pick_role, ROLE_NAME, ROLE_OPENING,
                      CHECKLISTS, checklist_start, checklist_step, checklist_report,
                      list_templates, match_checklist)
import llm as llm_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, 'web')

DISCLAIMER = '⚠️ 本助手为药事管理知识辅助工具，不构成医疗诊断或法律意见；用药请遵从医师处方与执业药师指导，合规问题以现行法规及属地监管部门为准。'

def build_reply(message, role, state, history, use_llm):
    q = (message or '').strip()
    ql = q.lower()
    resp = {'reply': '', 'role': role, 'state': state, 'sources': [],
            'llm': False, 'model': '', 'llm_error': ''}
    if not q:
        resp['reply'] = '请输入您的问题。'
        return resp
    # 记录用户消息到历史（命令类消息除外）
    is_command = ql in ('reset', 'help', 'exit', 'quit') or q in ('模板',) or '自查' in q or '清单' in q
    if state is None and not is_command and q not in ('个人', '机构', '公司', '换身份', '我是个人', '我是机构', '我是公司'):
        history.append({'role': 'user', 'content': q})
    if ql in ('exit', 'quit', 'reset', '重置'):
        resp['reply'] = '会话已重置（身份与历史已清空，配置保留）。'
        resp['state'] = None
        history.clear()
        return resp
    if ql in ('help', '帮助', '?', '？'):
        resp['reply'] = ('可用服务：\n1. 身份：我是个人 / 我是机构 / 我是公司\n'
            + '2. 自查：GSP自查 / 企业自查 / 机构自查 / 五专自查 / 不良反应自查（逐项答是/否）\n'
            + '3. 模板：输入“模板”查看制度/记录/培训模板\n'
            + '4. 知识问答：直接提问（已配置大模型时自动使用 AI 模式）\n'
            + '5. 设置：点击右上角 ⚙ 配置大模型 API')
        return resp
    if ql.startswith('role') or q in ('我是个人', '我是机构', '我是公司', '个人', '机构', '公司', '换身份'):
        if '个人' in q or ql.startswith('role personal'):
            role = 'personal'
        elif '机构' in q or '医院' in q or ql.startswith('role org'):
            role = 'org'
        elif '公司' in q or '企业' in q or ql.startswith('role company'):
            role = 'company'
        resp['reply'] = ROLE_OPENING.get(role, '')
        resp['role'] = role
        if role == 'company':
            resp['reply'] += '\n\n（AI 模式已启用时，可进一步咨询 GxP、QA/QC、临床试验 CRA/CRC、药物警戒体系等专题。）'
        return resp
    if '模板' in q or ql.startswith('template'):
        resp['reply'] = list_templates()
        return resp
    if '自查' in q or '清单' in q or 'checklist' in ql:
        kind = match_checklist(q)
        if kind is None:
            resp['reply'] = '请指定自查类型：GSP/企业自查、机构自查、五专自查、不良反应自查。'
            return resp
        state = checklist_start(kind)
        cl = CHECKLISTS[kind]
        resp['reply'] = '开始【%s】自查，共 %d 项，逐项回答 是/否：\n[1/%d] %s' % (cl['name'], len(cl['items']), len(cl['items']), cl['items'][0])
        resp['state'] = state
        return resp
    if state is not None:
        done, msg = checklist_step(state, q)
        if msg:
            resp['reply'] = msg
            resp['state'] = state
            return resp
        cl = CHECKLISTS[state['kind']]
        idx = state['index']
        if done:
            resp['reply'] = checklist_report(state)
            resp['state'] = None
        else:
            resp['reply'] = '[%d/%d] %s' % (idx + 1, len(cl['items']), cl['items'][idx])
            resp['state'] = state
        return resp
    intents = detect_intent(q)
    role = pick_role(intents, role)
    resp['role'] = role
    # 本地检索
    answer = make_answer(q, chunks, idf)
    for line in (answer or '').split('\n'):
        if line.startswith('来源：'):
            resp['sources'].append(line[3:].strip())
    # AI 模式：真实大模型基于知识库作答
    if use_llm and answer and llm_mod.is_configured():
        cfg = llm_mod.load_config()
        text, srcs, ok, err = llm_mod.answer_with_llm(q, chunks, idf, history, role)
        if ok and text:
            resp['reply'] = text
            resp['llm'] = True
            resp['model'] = cfg['model']
            if srcs:
                resp['sources'] = srcs
            history.append({'role': 'assistant', 'content': text})
        else:
            resp['llm_error'] = err or '未知错误'
            if answer:
                resp['reply'] = answer + '\n\n⚠️ AI 调用失败（%s），以上为本地知识库回答。' % (err or '')
            else:
                resp['reply'] = 'AI 调用失败（%s），且本地未检索到相关内容。' % (err or '')
            history.append({'role': 'assistant', 'content': resp['reply']})
    elif answer:
        resp['reply'] = answer
        history.append({'role': 'assistant', 'content': answer})
        if 'personal' in intents or role == 'personal':
            resp['reply'] += '\n\n⚠️ 用药安全提示：请遵医嘱用药；出现严重不良反应（呼吸急促、皮疹加重、意识障碍等）立即就医。'
    else:
        resp['reply'] = '未在知识库中找到相关内容。可尝试更具体的药名/法规名，或输入“help”查看服务，输入“模板”获取模板；已配置大模型时可获得 AI 扩展回答。'
    if len(history) > 24:
        del history[: len(history) - 24]
    return resp

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/health':
            self._send(200, json.dumps({'ok': True, 'chunks': len(chunks)}, ensure_ascii=False))
            return
        if parsed.path == '/api/llm/status':
            cfg = llm_mod.load_config()
            self._send(200, json.dumps({
                'configured': llm_mod.is_configured(cfg),
                'enabled': bool(cfg.get('enabled')),
                'api_base': cfg.get('api_base', ''),
                'model': cfg.get('model', ''),
                'key_set': bool(cfg.get('api_key')),
            }, ensure_ascii=False))
            return
        if parsed.path == '/':
            file_path = os.path.join(WEB_DIR, 'index.html')
        else:
            file_path = os.path.normpath(os.path.join(WEB_DIR, parsed.path.lstrip('/')))
        if not file_path.startswith(WEB_DIR) or not os.path.isfile(file_path):
            self._send(404, 'Not Found', 'text/plain; charset=utf-8')
            return
        ext = os.path.splitext(file_path)[1].lower()
        ctype = {
            '.html': 'text/html; charset=utf-8',
            '.js': 'text/javascript; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.png': 'image/png',
        }.get(ext, 'application/octet-stream')
        with open(file_path, 'rb') as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b'{}'
        try:
            payload = json.loads(raw.decode('utf-8'))
        except Exception:
            payload = {}
        if parsed.path == '/api/llm/config':
            cfg = llm_mod.load_config()
            for k in ('api_base', 'api_key', 'model', 'temperature', 'max_tokens', 'timeout', 'enabled'):
                if k in payload and payload[k] is not None:
                    cfg[k] = payload[k]
            llm_mod.save_config(cfg)
            self._send(200, json.dumps({
                'ok': True,
                'configured': llm_mod.is_configured(cfg),
                'model': cfg['model'],
                'api_base': cfg['api_base'],
            }, ensure_ascii=False))
            return
        if parsed.path == '/api/llm/test':
            cfg = llm_mod.load_config()
            for k in ('api_base', 'api_key', 'model', 'timeout'):
                if k in payload and payload[k] is not None:
                    cfg[k] = payload[k]
            ok, msg = llm_mod.test_connection(cfg)
            self._send(200, json.dumps({'ok': ok, 'message': msg}, ensure_ascii=False))
            return
        if parsed.path == '/api/ask':
            role = payload.get('role') or session_holder['role']
            state = payload.get('state') or session_holder['state']
            use_llm = payload.get('use_llm')
            if use_llm is None:
                use_llm = True
            try:
                resp = build_reply(payload.get('message', ''), role, state, session_holder['history'], bool(use_llm))
                session_holder['role'] = resp['role']
                session_holder['state'] = resp['state']
                resp['disclaimer'] = DISCLAIMER
                self._send(200, json.dumps(resp, ensure_ascii=False))
            except Exception as e:
                self._send(500, json.dumps({'error': str(e)}, ensure_ascii=False))
            return
        self._send(404, json.dumps({'error': 'not found'}, ensure_ascii=False))

def start(port=8901, open_browser=True):
    global chunks, idf, session_holder
    session_holder = {'role': None, 'state': None, 'history': []}
    chunks, idf = load_kb()
    if not chunks:
        print('错误：知识库加载失败，请检查 knowledge_base 目录。')
        sys.exit(1)
    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = 'http://127.0.0.1:%d' % port
    print('LeebertyPharmacyAdministration Web 服务已启动')
    print('知识库：%d 个知识块' % len(chunks))
    ai = '已配置（模型 %s）' % llm_mod.load_config().get('model') if llm_mod.is_configured() else '未配置（本地模式，可用 ⚙ 或 llm set 接入大模型）'
    print('大模型 API：%s' % ai)
    print('访问地址：%s' % url)
    print('按 Ctrl+C 停止服务')
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('服务已停止。')
    httpd.server_close()

chunks = []
idf = {}
session_holder = {'role': None, 'state': None, 'history': []}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LeebertyPharmacyAdministration Web 服务')
    parser.add_argument('--port', type=int, default=8901)
    parser.add_argument('--no-browser', action='store_true', help='不自动打开浏览器')
    args = parser.parse_args()
    start(args.port, not args.no_browser)