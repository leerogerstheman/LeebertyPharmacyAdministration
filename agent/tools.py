# -*- coding: utf-8 -*-
# tools.py — 药剂工具集（结构化 Tool 注册，供 Agent 循环调用）
# 协议：模型以 [TOOL_CALL:工具名:参数1|参数2] 调用，引擎注入 [TOOL_RESULT] 观察
import re

def kb_search(query, chunks, idf, top_k=3, doc_hint=None):
    """工具1：知识库检索。doc_hint 可限定主题文档（如个人场景优先 07），返回（结果文本, 来源列表）"""
    from engine import search
    if doc_hint:
        sub = [c for c in chunks if any(x in c.doc for x in doc_hint)]
        hits = search(query, sub, idf, top_k) if sub else []
    else:
        hits = search(query, chunks, idf, top_k)
    if not hits:
        return '未在知识库中找到相关内容。', []
    parts = []
    src = []
    for i, (score, c) in enumerate(hits, 1):
        src.append('knowledge_base/' + c.path)
        body = c.text[:500] + ('……' if len(c.text) > 500 else '')
        parts.append('[%d] 《%s》·%s（相关度%.2f）' % (i, c.doc, c.heading, score))
        parts.append(body)
    return '\n'.join(parts), src

def icer_calc(cost_a, effect_a, cost_b, effect_b, wtp=80000):
    """工具2：药物经济学 ICER 计算器（增量成本效果比，元/单位健康产出）"""
    try:
        ca = float(cost_a); ea = float(effect_a)
        cb = float(cost_b); eb = float(effect_b)
        w = float(wtp or 80000)
    except (TypeError, ValueError):
        return '参数无效：请提供 成本A、效果A、成本B、效果B（数字），如 icer_calc 10000|8|15000|9|80000'
    dcost = cb - ca
    deff = eb - ea
    if ea <= 0 or eb <= 0:
        return '健康效果必须大于0（可用 QALY 或自然单位）。'
    if deff <= 0:
        return '方案B效果未优于方案A（ΔE=%.2f≤0）：B 不具成本效果优势，不建议支付更高价。' % deff
    icer = dcost / deff
    lines = ['ICER 计算（ΔC/ΔE）：']
    lines.append('Δ成本 = %g - %g = %g 元' % (cb, ca, dcost))
    lines.append('Δ效果 = %g - %g = %g' % (eb, ea, deff))
    lines.append('ICER = %g / %g = %g 元/单位效果' % (dcost, deff, icer))
    if icer <= w:
        lines.append('结论：ICER(%g) ≤ 意愿支付阈值(%g)，方案B具有成本效果，建议纳入考虑。' % (icer, w))
    else:
        lines.append('结论：ICER(%g) > 意愿支付阈值(%g)，方案B需降价或谈判后才具经济性。' % (icer, w))
    lines.append('提示：正式决策建议补充敏感性分析与预算影响分析（BIA）。')
    return '\n'.join(lines)

def adr_quick(kind=''):
    """工具3：不良反应/不良事件报告时限速查"""
    lines = [
        '时限速查：',
        '- 死亡病例：获知后立即报告',
        '- 严重不良反应：获知后15日内',
        '- 其他（新药监测期内所有/其他药品新的和严重的）：30日内',
        '- 群体不良事件：立即报告并采取控制措施',
        '- 临床试验 SAE：研究者获知后按方案时限（一般24小时）内报告申办者；SUSAR 快速报告',
        '提示：具体要求以现行法规与方案为准。',
    ]
    return '\n'.join(lines)

def law_lookup(keyword, chunks, idf):
    """工具4：法规条款速查（聚焦法律法规文档）"""
    from engine import search
    q = (keyword or '') + ' 法规 规定'
    hits = search(q, chunks, idf, 2)
    if not hits:
        return '未找到相关法规条目。'
    parts = []
    for i, (score, c) in enumerate(hits, 1):
        parts.append('[%d] 《%s》·%s' % (i, c.doc, c.heading))
        parts.append(c.text[:400])
    return '\n'.join(parts)

def template_list():
    """工具5：模板导航"""
    from services import list_templates
    return list_templates()

def checklist_router(kind):
    """工具6：合规自查启动（返回清单名称与条目数）"""
    from services import CHECKLISTS, match_checklist
    k = match_checklist(kind)
    if not k or k not in CHECKLISTS:
        return '未知自查类型，可选：GSP自查、机构自查、五专自查、不良反应自查'
    cl = CHECKLISTS[k]
    first = cl['items'][0]
    return '已启动【%s】自查，共 %d 项。第一项：%s（逐项回答 是/否）' % (cl['name'], len(cl['items']), first)

TOOLS = {
    'kb_search': {'desc': '检索药事管理知识库获取权威内容', 'params': 'query（检索词）, top_k（可选，默认3）', 'fn': kb_search},
    'icer_calc': {'desc': '药物经济学 ICER 计算（增量成本效果比）', 'params': 'cost_a, effect_a, cost_b, effect_b, wtp(可选默认80000)', 'fn': icer_calc},
    'adr_quick': {'desc': '不良反应/SAE 报告时限速查', 'params': 'kind（可选）', 'fn': adr_quick},
    'law_lookup': {'desc': '法规条款速查', 'params': 'keyword', 'fn': law_lookup},
    'template_list': {'desc': '列出制度/记录/培训模板', 'params': '无', 'fn': template_list},
    'checklist_router': {'desc': '启动合规自查清单', 'params': 'kind（如 GSP自查/五专自查/机构自查/不良反应自查）', 'fn': checklist_router},
}

TOOL_PROTOCOL = ('可用工具：\n' + '\n'.join(
    '  - %s：%s（参数：%s）' % (n, t['desc'], t['params']) for n, t in TOOLS.items())
    + '\n调用格式：[TOOL_CALL:工具名:参数1|参数2|...]\n'
    + '收到 [TOOL_RESULT] 后结合结果继续推理，最终直接输出回答（不再包含工具调用标记）。')

CALL_RE = re.compile(r'\[TOOL_CALL:([A-Za-z_]+):([^\]]*)\]')

def parse_tool_calls(text):
    """解析 [TOOL_CALL:name:args] 协议，返回 [(name, args_str)]"""
    out = []
    for m in CALL_RE.finditer(text):
        out.append((m.group(1), m.group(2).strip()))
    return out

def execute_tool(name, args_str, ctx):
    """执行工具，ctx 提供 chunks/idf 等运行时环境。返回 (结果文本, 来源列表)"""
    chunks = ctx.get('chunks', [])
    idf = ctx.get('idf', {})
    args = [a.strip() for a in args_str.split('|')] if args_str else []
    try:
        if name == 'kb_search':
            q = args[0] if args else '药事管理'
            t = args[1] if len(args) > 1 and args[1].isdigit() else None
            text, src = kb_search(q, chunks, idf, int(t) if t else 3)
            return text, src
        if name == 'icer_calc':
            a = args + [''] * (5 - len(args))
            return icer_calc(a[0], a[1], a[2], a[3], a[4] or '80000'), []
        if name == 'adr_quick':
            return adr_quick(args[0] if args else ''), []
        if name == 'law_lookup':
            return law_lookup(args[0] if args else '', chunks, idf), []
        if name == 'template_list':
            return template_list(), []
        if name == 'checklist_router':
            return checklist_router(args[0] if args else ''), []
    except Exception as e:
        return '工具执行失败：%s' % e, []
    return '未知工具：%s' % name, []