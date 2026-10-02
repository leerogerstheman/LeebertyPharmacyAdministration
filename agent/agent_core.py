# -*- coding: utf-8 -*-
# agent_core.py — AI Native Agent 引擎（借鉴 hello-agents 方法论）
# 范式：ReAct（默认）/ Plan-and-Solve / Reflection；结构化工具循环 + 本地规则路由（无LLM也可用工具）
import re

from engine import load_kb
from services import detect_intent, pick_role
from tools import TOOL_PROTOCOL, parse_tool_calls, execute_tool, icer_calc, adr_quick, law_lookup, kb_search
import llm as llm_mod
import memory

MAX_ROUNDS = 4

ROLE_GUIDE = {
    'personal': '当前用户身份：个人。用药类回答末尾必须附安全提示：请遵医嘱用药，出现严重不良反应立即就医；不得推荐具体处方。',
    'org': '当前用户身份：集体/医疗机构。侧重药事管理与药物治疗学委员会、处方点评、麻精五专、抗菌药物、药房规范化等管理实务。',
    'company': '当前用户身份：公司/企业。侧重 GxP 合规、GSP/GMP、QA/QC、临床试验 CRA/CRC、药物警戒体系、药物经济学证据、许可申办。',
}

SYSTEM_BASE = ('你是“LeebertyPharmacyAdministration”药事管理智能 Agent，服务个人、医疗机构与企业。'
    + '回答要求：1) 优先基于工具结果与知识库，不编造法规条款与数据；2) 分条作答、简体中文；'
    + '3) 合规问题注明以现行有效法规与属地监管部门为准；4) 引用工具结果时标注【来源】。')

FEW_SHOT = ('调用示例：\n'
    + '用户：四查十对是什么？\n'
    + '助手：[TOOL_CALL:kb_search:四查十对]\n'
    + '[TOOL_RESULT:kb_search] 返回《06_处方与调剂管理》相关章节…\n'
    + '助手：四查十对包括查处方、查药品、查配伍禁忌、查用药合理性……（最终回答，不带工具标记）')

def _system_prompt(role):
    parts = [SYSTEM_BASE, ROLE_GUIDE.get(role, '')]
    prof = memory.recall_profile()
    if prof:
        parts.append(prof)
    parts.append(TOOL_PROTOCOL)
    parts.append(
        FEW_SHOT
    )
    return '\n'.join(x for x in parts if x)

def _clean_reply(text):
    """移除回复中残留的协议标记"""
    text = re.sub(r'\[TOOL_CALL:[^\]]*\]', '', text)
    text = re.sub(r'\[TOOL_RESULT:[^\]]*\]', '', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()

def _extract_icer_args(q):
    """从提问中启发式提取 ICER 参数：成本A/效果A/成本B/效果B/阈值"""
    if not re.search(r'ICER|成本效果|增量成本|经济性|性价比', q, re.I):
        return None
    nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', q)]
    if len(nums) >= 4:
        return nums[:5]  # 最多取5个：成本A,效果A,成本B,效果B,阈值
    return None

class PharmaAgent:
    def __init__(self, chunks=None, idf=None):
        self.chunks = chunks
        self.idf = idf
        if not self.chunks:
            self.chunks, self.idf = load_kb()
        self.ctx = {'chunks': self.chunks, 'idf': self.idf}

    def run(self, query, role=None, history=None, use_llm=True, paradigm='adaptive'):
        """统一入口：返回 dict（reply/sources/llm/model/trace/llm_error）
        paradigm: adaptive（自动）/ react / plan / reflection"""
        trace = []
        intents = detect_intent(query)
        role = pick_role(intents, role)
        trace.append('身份：' + role + ('（意图：' + '、'.join(intents) + '）' if intents else ''))
        # 第14章：深度研究模式
        if re.search(r'深度研究|研究报告|research', query, re.I):
            return self.research(query, role, history, trace)
        if paradigm == 'adaptive':
            paradigm = self._pick_paradigm(query)
            trace.append('范式选择：' + paradigm)
        if use_llm and llm_mod.is_configured():
            if paradigm == 'plan':
                return self._run_plan(query, role, history, trace)
            if paradigm == 'reflection':
                return self._run_reflection(query, role, history, trace)
            return self._run_react(query, role, history, trace)
        return self._run_local(query, role, trace)

    def _pick_paradigm(self, q):
        """adaptive 策略：规划类问题→plan；审查类问题→reflection；其余→react"""
        if re.search(r'规划|体系|方案|建设|路线|计划|实施', q):
            return 'plan'
        if re.search(r'审查|核对|复核|检查一遍|评估我的|自检', q):
            return 'reflection'
        return 'react'

    def research(self, topic, role, history, trace):
        """第14章：深度研究模式——多关键词检索 + 结构化报告（本地也可用）"""
        from tools import kb_search
        report_topic = re.sub(r'深度研究|研究报告|research[:：\s]*', '', topic, flags=re.I).strip() or topic
        # 关键词扩展：取主题词 + 常用法规视角
        keywords = []
        for k in report_topic.replace('，', ' ').replace('、', ' ').replace('？', ' ').split():
            if len(k) >= 2:
                keywords.append(k)
        keywords = keywords[:3]
        if report_topic not in keywords:
            keywords.insert(0, report_topic)
        keywords += ['合规 要求']
        sources = []
        findings = []
        trace.append('深度研究主题：' + report_topic)
        for kw in keywords[:4]:
            trace.append('检索：' + kw)
            text, src = kb_search(kw, self.chunks, self.idf, 2)
            sources.extend(src)
            findings.append('### 检索词：' + kw)
            findings.append(text)
            findings.append('')
        report = []
        report.append('## 深度研究报告：' + report_topic)
        report.append('')
        if llm_mod.is_configured():
            try:
                msgs = [
                    {'role': 'system', 'content': '你是药事管理研究分析师。请基于【检索材料】撰写结构化深度研究报告（背景/核心要点/风险提示/行动建议），分条清晰，注明以现行法规为准，不得编造。'},
                    {'role': 'user', 'content': '研究主题：' + report_topic + '\n\n【检索材料】\n' + '\n'.join(findings)[:6000]},
                ]
                summary = llm_mod.chat(msgs)
                trace.append('LLM 综合生成研究报告')
                if role == 'personal' and '⚠️' not in summary:
                    summary += '\n\n⚠️ 用药安全提示：请遵医嘱用药；出现严重不良反应立即就医。'
                return {'reply': summary, 'sources': list(dict.fromkeys(sources)), 'llm': True, 'model': llm_mod.load_config().get('model', ''), 'trace': trace, 'llm_error': None}
            except RuntimeError as e:
                trace.append('LLM 汇总失败，输出本地检索汇编（%s）' % (e,))
        report.append('\n'.join(findings))
        report.append('## 研究小结')
        report.append('以上为本主题在知识库中的检索汇编（' + str(len(sources)) + ' 个来源）。如需进一步细化，请指定子主题（如"GSP 数据完整性要求"）。')
        return {'reply': '\n'.join(report), 'sources': list(dict.fromkeys(sources)), 'llm': False, 'model': '', 'trace': trace, 'llm_error': None}

    # ---------- 本地模式：规则路由（工具同样可用） ----------
    def _run_local(self, query, role, trace):
        q = query.strip()
        # 工具路由 1：ICER 计算
        icer_args = _extract_icer_args(q)
        if icer_args:
            trace.append('工具调用：icer_calc %s' % (icer_args,))
            reply = icer_calc(*icer_args)
            return {'reply': reply, 'sources': [], 'llm': False, 'model': '', 'trace': trace, 'llm_error': None}
        # 工具路由 2：不良反应时限速查
        if '不良反应' in q and re.search(r'时限|上报|报告', q):
            trace.append('工具调用：adr_quick')
            return {'reply': adr_quick(), 'sources': [], 'llm': False, 'model': '', 'trace': trace, 'llm_error': None}
        # 工具路由 3：法规速查
        # 通用：知识库检索（个人场景主题加权 → 07 药学服务）
        hint = ['07'] if role == 'personal' else None
        trace.append('工具调用：kb_search' + ('（个人主题加权）' if hint else ''))
        text, src = kb_search(q, self.chunks, self.idf, 3, doc_hint=hint)
        reply = text
        if role == 'personal':
            reply += '\n\n⚠️ 用药安全提示：请遵医嘱用药；出现严重不良反应（呼吸急促、皮疹加重、意识障碍等）立即就医。'
        return {'reply': reply, 'sources': src, 'llm': False, 'model': '', 'trace': trace, 'llm_error': None}

    # ---------- ReAct 范式（思考→行动→观察，循环调用工具） ----------
    def _run_react(self, query, role, history, trace):
        messages = [{'role': 'system', 'content': _system_prompt(role)}]
        for h in (history or [])[-6:]:
            if h.get('role') in ('user', 'assistant') and h.get('content'):
                messages.append({'role': h['role'], 'content': h['content'][:1500]})
        messages.append({'role': 'user', 'content': query})
        sources = []
        last_out = ''
        for rnd in range(1, MAX_ROUNDS + 1):
            try:
                last_out = llm_mod.chat(messages)
            except RuntimeError as e:
                trace.append('AI 调用失败：%s（降级本地模式）' % (e,))
                return self._fallback_local(query, role, trace, str(e))
            calls = parse_tool_calls(last_out)
            if not calls:
                trace.append('第%d轮：模型给出最终回答' % rnd)
                reply = _clean_reply(last_out)
                if role == 'personal' and '⚠️' not in reply:
                    reply += '\n\n⚠️ 用药安全提示：请遵医嘱用药；出现严重不良反应立即就医。'
                return {'reply': reply, 'sources': sources, 'llm': True, 'model': llm_mod.load_config().get('model', ''), 'trace': trace, 'llm_error': None}
            for name, args in calls:
                text, src = execute_tool(name, args, self.ctx)
                sources.extend(src)
                trace.append('第%d轮 调用工具：%s(%s)' % (rnd, name, args[:40]))
                messages.append({'role': 'user', 'content': '[TOOL_RESULT:%s]\n%s' % (name, text[:1500])})
        trace.append('达到最大工具轮数，使用最后输出')
        reply = _clean_reply(last_out) or '已完成多步推理，请补充说明具体问题。'
        return {'reply': reply, 'sources': sources, 'llm': True, 'model': llm_mod.load_config().get('model', ''), 'trace': trace, 'llm_error': None}

    # ---------- Plan-and-Solve 范式（先计划后执行） ----------
    def _run_plan(self, query, role, history, trace):
        messages = [{'role': 'system', 'content': _system_prompt(role) + '\n请先输出简短执行计划（编号1-3步），再按计划调用工具，最后总结回答。'}]
        for h in (history or [])[-6:]:
            if h.get('role') in ('user', 'assistant') and h.get('content'):
                messages.append({'role': h['role'], 'content': h['content'][:1500]})
        messages.append({'role': 'user', 'content': query})
        sources = []
        last_out = ''
        for rnd in range(1, MAX_ROUNDS + 1):
            try:
                last_out = llm_mod.chat(messages)
            except RuntimeError as e:
                trace.append('AI 调用失败：%s（降级本地模式）' % (e,))
                return self._fallback_local(query, role, trace, str(e))
            calls = parse_tool_calls(last_out)
            if not calls:
                trace.append('第%d轮：计划执行完成，输出总结' % rnd)
                return {'reply': _clean_reply(last_out), 'sources': sources, 'llm': True, 'model': llm_mod.load_config().get('model', ''), 'trace': trace, 'llm_error': None}
            for name, args in calls:
                text, src = execute_tool(name, args, self.ctx)
                sources.extend(src)
                trace.append('第%d轮 执行：%s(%s)' % (rnd, name, args[:40]))
                messages.append({'role': 'user', 'content': '[TOOL_RESULT:%s]\n%s' % (name, text[:1500])})
        return {'reply': _clean_reply(last_out), 'sources': sources, 'llm': True, 'model': llm_mod.load_config().get('model', ''), 'trace': trace, 'llm_error': None}

    # ---------- Reflection 范式（自我检查修订） ----------
    def _run_reflection(self, query, role, history, trace):
        res = self._run_react(query, role, history, trace)
        if not res.get('llm'):
            return res
        try:
            messages = [{'role': 'system', 'content': _system_prompt(role)}]
            for h in (history or [])[-4:]:
                if h.get('role') in ('user', 'assistant') and h.get('content'):
                    messages.append({'role': h['role'], 'content': h['content'][:1200]})
            messages.append({'role': 'user', 'content': query})
            messages.append({'role': 'assistant', 'content': res['reply']})
            messages.append({'role': 'user', 'content': '请自我检查以上回答：1)是否引用知识库/工具结果；2)是否存在不确定或推测性表述；3)用药类回答是否含安全提示。如需修订请输出修订版完整回答。'});
            revised = llm_mod.chat(messages)
            trace.append('反思修订完成')
            res['reply'] = _clean_reply(revised)
        except RuntimeError:
            trace.append('反思轮失败，保留原回答')
        return res

    def _fallback_local(self, query, role, trace, err):
        text, src = kb_search(query, self.chunks, self.idf, 3)
        reply = text + '\n\n⚠️ AI 调用失败（%s），以上为本地知识库回答。' % err
        return {'reply': reply, 'sources': src, 'llm': False, 'model': '', 'trace': trace, 'llm_error': err}

def get_agent():
    """全局单例（懒加载）"""
    global _AGENT
    if _AGENT is None:
        _AGENT = PharmaAgent()
    return _AGENT

_AGENT = None