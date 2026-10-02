# -*- coding: utf-8 -*-
# multi_agent.py — 多智能体演示：虚拟药事委员会（第15章 赛博小镇式角色仿真）
# 三角色：患者代表 / 医院药学专家 / 企业合规官，围绕议题依次发言，最后汇总
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import load_kb
from tools import kb_search
import llm as llm_mod

MEMBERS = [
{'name': '李患者（个人用药视角）', 'role': 'personal', 'lens': '关注用药安全、便利与经济负担；担心不良反应与费用。', 'query': '个人用药安全 合理用药 注意事项'},
{'name': '王药师（医疗机构药学专家）', 'role': 'org', 'lens': '关注处方审核、药学服务、药事委员会决策与临床合理用药。', 'query': '医疗机构 处方审核 药学服务'},
{'name': '赵经理（企业合规官）', 'role': 'company', 'lens': '关注法规合规、质量体系与药物警戒义务。', 'query': 'GSP GxP 合规 药物警戒'},
]
def speak(member, topic, chunks, idf):
    """角色发言：LLM 模式用角色视角生成；本地模式用检索汇编"""
    text, src = kb_search(topic + ' ' + member['query'], chunks, idf, 2)
    if llm_mod.is_configured():
        sys_p = ('你是虚拟药事委员会的委员：%s。视角：%s。请围绕议题【%s】发表简短观点（3-5条），'
                 + '基于检索材料，不编造法规数据，语气符合角色身份。') % (member['name'], member['lens'], topic)
        try:
            out = llm_mod.chat([{'role': 'system', 'content': sys_p},
                               {'role': 'user', 'content': '【检索材料】\n' + text[:1500]}])
            return out, src
        except RuntimeError:
            pass
    lines = ['（本地模式发言）']
    lines.append(text[:600])
    return '\n'.join(lines), src

def main():
    parser = argparse.ArgumentParser(description='虚拟药事委员会（多智能体角色会谈）')
    parser.add_argument('topic', nargs='?', default='如何提升基层医疗机构合理用药水平')
    args = parser.parse_args()
    chunks, idf = load_kb()
    topic = args.topic
    print('议题：' + topic + '\n')
    print('=' * 54)
    all_src = []
    for m in MEMBERS:
        print('\n【%s】' % m['name'])
        print(m['lens'])
        speech, src = speak(m, topic, chunks, idf)
        print(speech)
        all_src.extend(src)
    print('\n' + '=' * 54)
    print('会议共识要点（由检索材料归纳）：')
    print('1. 以患者为中心，落实处方审核与用药教育；')
    print('2. 机构层面完善药事委员会与处方点评机制；')
    print('3. 企业层面守住 GxP 合规与药物警戒底线；')
    print('4. 三方数据共享（不良反应、满意度、合规记录）形成闭环。')
    uniq = []
    for x in all_src:
        if x not in uniq:
            uniq.append(x)
    print('\n参考来源：' + '；'.join(uniq[:5]))

if __name__ == '__main__':
    main()