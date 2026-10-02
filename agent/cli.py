# -*- coding: utf-8 -*-
# cli.py — LeebertyPharmacyAdministration 命令行交互入口（纯标准库）
import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import load_kb, make_answer
from services import (detect_intent, pick_role, ROLE_NAME, ROLE_OPENING,
                      CHECKLISTS, checklist_start, checklist_step, checklist_report,
                      list_templates, match_checklist)
from agent_core import get_agent
import llm as llm_mod

BANNER = '''
┌──────────────────────────────────────────────────────────┐
│  LeebertyPharmacyAdministration — 药事管理智能 Agent      │
│  面向个人 / 集体 / 公司的药事管理科目服务                │
│  本地知识库 × 可选真实大模型（LLM）双模式                │
└──────────────────────────────────────────────────────────┘
'''

DISCLAIMER = '\n⚠️ 提示：本助手为药事管理知识辅助工具，不构成医疗诊断或法律意见；用药请遵从医师处方与执业药师指导，合规问题请以现行法规及属地监管部门为准。'

def show_topic_menu():
    print('\n请选择您的身份（决定服务侧重）：')
    print('  1. 个人（用药咨询 / 合理用药 / 家庭药箱）')
    print('  2. 集体（医疗机构 / 团体：药事管理建设、处方点评、五专自查）')
    print('  3. 公司（企业：GSP合规/GxP/QA·QC/CRA·CRC/药物警戒/药物经济学）')
    print('  0. 不指定身份，直接提问')

def ready_lines(role):
    lines = ['\n当前身份：%s' % ROLE_NAME.get(role, '未指定（可随时说“我是个人/机构/公司”）')]
    lines.append('LLM：' + llm_mod.status_text())
    lines.append('内置命令：help 帮助 | whoami 身份 | role 切换身份 | 模板 查看模板 | llm 大模型设置 | exit 退出')
    return '\n'.join(lines)

def llm_command(q, chunks, idf, history):
    """处理 llm 系列命令，返回 (答复文本, 是否应退出对话处理)"""
    qq = q.strip()
    if qq.lower() in ('llm', 'llm status', 'llm 状态', '大模型'):
        return llm_mod.status_text(), False
    if qq.lower() in ('llm on', 'llm 启用'):
        cfg = llm_mod.load_config()
        if not cfg.get('api_key'):
            return '尚未配置 API 密钥。请先执行：llm set', False
        cfg['enabled'] = True
        llm_mod.save_config(cfg)
        return '已启用 AI 模式（模型 %s）。' % cfg['model'], False
    if qq.lower() in ('llm off', 'llm 关闭'):
        cfg = llm_mod.load_config()
        cfg['enabled'] = False
        llm_mod.save_config(cfg)
        return '已切换为本地知识库模式。可用 llm on 重新启用。', False
    if qq.lower() in ('llm test', 'llm 测试', 'llm 连接测试'):
        ok, msg = llm_mod.test_connection()
        return ('✅ 连接成功：%s' % msg) if ok else ('❌ %s' % msg), False
    if qq.lower().startswith('llm set') or qq == 'llm 配置':
        cfg = llm_mod.load_config()
        try:
            base = input('API 地址（如 https://api.deepseek.com/v1，回车保持 [%s]）：' % cfg['api_base']).strip()
            key = input('API 密钥（sk-...，回车保持现有）：').strip()
            model = input('模型名（如 deepseek-chat，回车保持 [%s]）：' % cfg['model']).strip()
        except (EOFError, KeyboardInterrupt):
            return '已取消配置。', False
        if base:
            cfg['api_base'] = base
        if key:
            cfg['api_key'] = key
        if model:
            cfg['model'] = model
        cfg['enabled'] = True
        llm_mod.save_config(cfg)
        ok, msg = llm_mod.test_connection(cfg)
        if ok:
            return '✅ 配置已保存并通过连接测试（模型 %s）。已启用 AI 模式。' % cfg['model'], False
        return '配置已保存，但连接测试失败：%s（可稍后执行 llm test 重试）' % msg, False
    return None, False

def main():
    print(BANNER)
    print('正在加载药事管理知识库…')
    chunks, idf = load_kb()
    if not chunks:
        print('错误：未找到知识库（knowledge_base 目录）。请确保在项目根目录运行。')
        return
    docs = set()
    for c in chunks:
        docs.add(c.doc)
    print('知识库加载完成：%d 个知识块，%d 篇文档。\n' % (len(chunks), len(docs)))
    role = None
    history = []
    checklist_state = None
    show_topic_menu()
    try:
        choice = input('请输入编号 (1/2/3/0，直接回车=0)：').strip()
    except EOFError:
        choice = '0'
    if choice == '1':
        role = 'personal'
    elif choice == '2':
        role = 'org'
    elif choice == '3':
        role = 'company'
    if role:
        print('\n' + ROLE_OPENING[role])
    print(ready_lines(role))
    print(DISCLAIMER)
    while True:
        try:
            q = input('\n你> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n再见！')
            break
        if not q:
            continue
        ql = q.lower()
        if ql in ('exit', 'quit', '退出', '再见'):
            print('再见！愿您安全用药、合规经营。')
            break
        if ql in ('help', '帮助', '?', '？'):
            print(ready_lines(role))
            print('\n自查命令示例：\n  - “GSP自查”、“企业自查” → 经营合规清单\n  - “五专自查”、“麻精自查” → 麻精药品专项\n  - “不良反应自查”、“ADR自查” → 不良反应制度\n  - “机构自查”、“医院自查” → 医疗机构药事管理\n回答“是/否”逐项完成，最终给出通过率报告。')
            continue
        if ql in ('whoami', '身份'):
            print('当前身份：%s' % ROLE_NAME.get(role, '未指定'))
            continue
        if ql.startswith('llm') or q in ('大模型',):
            out, _ = llm_command(q, chunks, idf, history)
            if out:
                print(out)
            continue
        if ql.startswith('role') or q in ('我是个人', '我是机构', '我是公司', '个人', '机构', '公司', '换身份'):
            if '个人' in q or ql.startswith('role personal'):
                role = 'personal'
            elif '机构' in q or '医院' in q or ql.startswith('role org'):
                role = 'org'
            elif '公司' in q or '企业' in q or ql.startswith('role company'):
                role = 'company'
            print('\n' + ROLE_OPENING[role])
            continue
        if '模板' in q or ql.startswith('template'):
            print(list_templates())
            continue
        if '自查' in q or '清单' in q or 'checklist' in ql:
            kind = match_checklist(q)
            if kind is None:
                print('请指定自查类型：GSP/企业自查、机构自查、五专自查、不良反应自查。')
                continue
            checklist_state = checklist_start(kind)
            cl = CHECKLISTS[kind]
            print('开始【%s】自查，共 %d 项。逐项回答 是/否：' % (cl['name'], len(cl['items'])))
            print('[1/%d] %s' % (len(cl['items']), cl['items'][0]))
            continue
        if checklist_state is not None:
            done, msg = checklist_step(checklist_state, q)
            if msg:
                print(msg)
                continue
            cl = CHECKLISTS[checklist_state['kind']]
            idx = checklist_state['index']
            if done:
                print(checklist_report(checklist_state))
                checklist_state = None
            else:
                print('[%d/%d] %s' % (idx + 1, len(cl['items']), cl['items'][idx]))
            continue
        intents = detect_intent(q)
        role = pick_role(intents, role)
        history.append({'role': 'user', 'content': q})
        result = get_agent().run(q, role, history, llm_mod.is_configured())
        for step in result.get('trace', []):
            print('  · ' + step)
        print('\n' + result.get('reply', ''))
        if result.get('sources'):
            print('参考来源：' + '；'.join(result['sources']))
        history.append({'role': 'assistant', 'content': result.get('reply', '')})
        if len(history) > 24:
            del history[: len(history) - 24]

if __name__ == '__main__':
    main()