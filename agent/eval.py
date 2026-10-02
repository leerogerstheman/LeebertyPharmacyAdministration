# -*- coding: utf-8 -*-
# eval.py — Agent 性能评估系统（借鉴 hello-agents 第十二章）
# 运行：python agent/eval.py [--mode local] → 输出 examples/eval_report.md
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import load_kb
from agent_core import get_agent

QA_SET = [
    # ===== 个人（用药咨询）=====
    {'q': '阿司匹林漏服了怎么办？', 'role': 'personal', 'expect': ['07_药学服务与合理用药']},
    {'q': '孕妇感冒能吃哪些药？要注意什么？', 'role': 'personal', 'expect': ['07_药学服务与合理用药']},
    {'q': '药品说明书里的禁忌是什么意思？', 'role': 'personal', 'expect': ['07_药学服务与合理用药']},
    {'q': '为什么吃头孢期间不能喝酒？', 'role': 'personal', 'expect': ['07_药学服务与合理用药']},
    {'q': '家里过期药品应该怎么处理？', 'role': 'personal', 'expect': ['07_药学服务与合理用药']},
    {'q': '老年人多重用药要注意什么？', 'role': 'personal', 'expect': ['07_药学服务与合理用药']},
    {'q': '降压药漏服一次要紧吗？', 'role': 'personal', 'expect': ['07_药学服务与合理用药']},
    {'q': '儿童用退烧药的剂量怎么把握？', 'role': 'personal', 'expect': ['07_药学服务与合理用药']},
    {'q': '抗生素为什么要按疗程吃完不能随便停药？', 'role': 'personal', 'expect': ['07_药学服务与合理用药', '01_法律法规体系']},
    {'q': '家庭药箱应该怎么管理和储存药品？', 'role': 'personal', 'expect': ['07_药学服务与合理用药']},
    # ===== 集体（医疗机构）=====
    {'q': '药事管理与药物治疗学委员会有哪些职责？', 'role': 'org', 'expect': ['05_医疗机构药事管理']},
    {'q': '处方点评制度怎么开展？抽样数量有什么要求？', 'role': 'org', 'expect': ['06_处方与调剂管理']},
    {'q': '麻精药品五专管理具体指什么？', 'role': 'org', 'expect': ['09_特殊药品管理']},
    {'q': '抗菌药物分级管理怎么实施？', 'role': 'org', 'expect': ['05_医疗机构药事管理', '01_法律法规体系']},
    {'q': '各类处方保存期限分别是多少？', 'role': 'org', 'expect': ['06_处方与调剂管理']},
    {'q': '处方调剂的四查十对是什么？', 'role': 'org', 'expect': ['06_处方与调剂管理']},
    {'q': '药品不良反应报告时限是什么？', 'role': 'org', 'special': 'adr'},
    {'q': '医疗机构药品采购渠道有哪些要求？', 'role': 'org', 'expect': ['05_医疗机构药事管理']},
    {'q': '药房冷链药品管理要点？', 'role': 'org', 'expect': ['05_医疗机构药事管理']},
    {'q': '处方有效期和处方用量的一般规定？', 'role': 'org', 'expect': ['06_处方与调剂管理']},
    # ===== 公司（企业）=====
    {'q': 'GSP 质量管理部门有哪些职责？', 'role': 'company', 'expect': ['04_药品经营与GSP']},
    {'q': '药品经营许可证怎么办？需要什么条件？', 'role': 'company', 'expect': ['04_药品经营与GSP']},
    {'q': 'GxP 都包括哪些规范？', 'role': 'company', 'expect': ['11_GxP质量管理体系']},
    {'q': 'CRA 临床研究监查员的核心职责？', 'role': 'company', 'expect': ['12_临床试验与CRA_CRC']},
    {'q': 'QA 和 QC 有什么区别？', 'role': 'company', 'expect': ['13_QA与QC质量管理']},
    {'q': '数据完整性 ALCOA 原则是什么？', 'role': 'company', 'expect': ['11_GxP质量管理体系', '13_QA与QC质量管理']},
    {'q': '药品上市许可持有人有什么药物警戒义务？', 'role': 'company', 'expect': ['08_药物警戒与不良反应监测']},
    {'q': 'ICER 计算：方案A成本10000元效果8，方案B成本15000元效果9，阈值80000', 'role': 'company', 'special': 'icer'},
    {'q': '严重不良反应上报时限是几天？', 'role': 'company', 'special': 'adr'},
    {'q': '药品生命周期各阶段对应哪些 GxP？', 'role': 'company', 'expect': ['11_GxP质量管理体系']},
]

def judge(item, reply, sources):
    """评分：工具题检查输出特征；知识题检查来源命中"""
    special = item.get('special')
    if special == 'icer':
        return ('ICER' in reply and '元/单位效果' in reply), '工具输出包含 ICER 计算过程'
    if special == 'adr':
        return ('15' in reply or '15日' in reply), '工具输出包含 15 日时限'
    for exp in item.get('expect', []):
        for s in sources:
            if exp in s:
                return True, '命中来源 ' + s
    return False, '未命中期望来源：' + '、'.join(item.get('expect', [])) + ('；实际：' + '、'.join(sources[:3]) if sources else '（无来源）')

def run_eval(mode='local', qa_set=None, tag=''):
    chunks, idf = load_kb()
    ag = get_agent()
    qa_set = qa_set or QA_SET
    rows = []
    passed = 0
    groups = {}
    for i, item in enumerate(qa_set, 1):
        res = ag.run(item['q'], item.get('role'), [], use_llm=(mode == 'llm'), paradigm=item.get('paradigm', 'adaptive'))
        ok, why = judge(item, res.get('reply', ''), res.get('sources', []))
        if ok:
            passed += 1
        g = item.get('group', '综合')
        groups.setdefault(g, [0, 0])
        groups[g][1] += 1
        if ok:
            groups[g][0] += 1
        rows.append({'no': i, 'ok': ok, 'q': item['q'], 'why': why, 'model': res.get('model', ''), 'steps': len(res.get('trace', []))})
        print('[%s] Q%d %s' % ('✓' if ok else '✗', i, item['q'][:40]))
    total = len(qa_set)
    rate = passed * 100.0 / total
    group_summary = {k: '%d/%d' % (v[0], v[1]) for k, v in groups.items()}
    report = {
        'mode': mode,
        'tag': tag,
        'total': total,
        'passed': passed,
        'rate': round(rate, 1),
        'groups': group_summary,
        'rows': rows,
    }
    return report

def write_report(report):
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'examples')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'eval_report.md')
    lines = ['# Agent 评估报告']
    lines.append('')
    lines.append('- 模式：%s（local=本地知识库工具路由 / llm=大模型 ReAct 循环）' % report['mode'])
    lines.append('- 评估集：%d 条（个人10 / 集体10 / 企业10）' % report['total'])
    lines.append('- 通过：%d / %d（%.1f%%）' % (report['passed'], report['total'], report['rate']))
    gs = report.get('groups')
    if gs:
        lines.append('- 分组：' + '；'.join('%s %s' % (k, v) for k, v in gs.items()))
    if report.get('tag'):
        lines.append('- 标记：' + report['tag'])
    lines.append('')
    lines.append('| # | 结果 | 问题 | 说明 |')
    lines.append('|---|---|---|---|')
    for r in report['rows']:
        lines.append('| %d | %s | %s | %s |' % (r['no'], '✅' if r['ok'] else '❌', r['q'].replace('|', '｜')[:36], r['why']))
    lines.append('')
    lines.append('> 说明：知识题按“回答来源是否命中期望专题”评分；工具题（ICER/ADR时限）按输出特征评分。')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('\n评估报告已写入：%s' % path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='local', choices=['local', 'llm'])
    parser.add_argument('--custom', default='', help='自定义评估集 JSON 文件（列表，字段 q/role/expect/special/group）')
    parser.add_argument('--tag', default='', help='报告标记（如版本号）')
    args = parser.parse_args()
    qa_set = None
    if args.custom:
        with open(args.custom, 'r', encoding='utf-8') as f:
            qa_set = json.load(f)
        print('使用自定义评估集：%d 条' % len(qa_set))
    report = run_eval(args.mode, qa_set=qa_set, tag=args.tag)
    write_report(report)