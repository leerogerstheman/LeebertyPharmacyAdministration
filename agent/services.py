# -*- coding: utf-8 -*-
# services.py — LeebertyPharmacyAdministration 服务模块（纯 Python 标准库）
# 功能：三类用户身份识别、用药咨询引导、交互式合规自查清单、模板导航
import os
import re

from paths import SERVICE_DIR
TEMPLATE_DIR = os.path.join(SERVICE_DIR, 'templates')

PATTERNS = {
    'personal': [
        r'用药|吃药|服法|用量|剂量|漏服|副作用|孕妇|哺乳|儿童|小孩|老人|老年人|储存|冷藏|过期|家庭药箱|说明书|相互作用|忌口|禁忌|阿司匹林|降压|降糖|抗生素|消炎药|退烧|感冒药',
    ],
    'org': [
        r'医院|医疗机构|药事(管理与药物)?治疗学委员会|处方点评|抗菌药物|药房|药剂科|临床药学|麻精|麻醉药品|精神药品|五专|印鉴卡|药事管理自评|门诊药房|病区药房|药学部门|审方',
    ],
    'company': [
        r'GSP|GMP|经营许可|许可证|批发|零售药店|连锁|持有人|MAH|药物警戒|追溯|网络销售|网上卖药|冷链|飞行检查|内审|首营|验收|养护|执业药师|报损|召回|质量负责人|票据|随货同行',
    ],
    'law': [
        r'药品管理法|疫苗管理法|条例|办法|法规|法律|规定|规章',
    ],
    'checklist': [
        r'自查|清单|核查|检查表|check',
    ],
    'template': [
        r'模板|制度文件|记录表|表单|表格|范本',
    ],
    'pharmaeco': [
        r'药物经济|医保目录|集采|集中采购|基本药物|DRG|价格',
    ],
}

ROLE_NAME = {'personal': '个人', 'org': '集体（医疗机构/团体）', 'company': '公司（企业）'}

ROLE_OPENING = {
    'personal': '您好！我是您的用药安全顾问。可咨询：药品用法用量、说明书解读、漏服处理、储存与有效期、孕哺/儿童/老人用药注意、不良反应识别、家庭药箱管理。',
    'org': '您好！我是贵机构的药事管理顾问。可协助：药事管理与药物治疗学委员会建设、处方点评、抗菌药物管理、麻精药品“五专”自查、药房规范化、药事管理自评。',
    'company': '您好！我是贵企业的合规顾问。可协助：GSP/GMP 合规自查、经营许可申办、药物警戒体系（持有人）、药品追溯、冷链管理、网络售药合规、培训计划。',
}

def detect_intent(text):
    hits = []
    for name, pats in PATTERNS.items():
        for p in pats:
            if re.search(p, text):
                hits.append(name)
                break
    return hits

def pick_role(intent_hits, declared=None):
    if declared and declared in ('personal', 'org', 'company'):
        return declared
    for name in ('personal', 'org', 'company'):
        if name in intent_hits:
            return name
    return 'unknown'

CHECKLISTS = {
    'company': {
        'name': '药品经营（GSP）合规自查',
        'items': [
            '许可证在有效期内，经营范围与实际经营一致',
            '质量负责人由高层担任并具有裁决权，质量管理部门独立设置',
            '质量管理体系文件现行有效并受控管理',
            '年度内审已开展并有整改闭环记录',
            '首营企业/首营品种资质审核档案齐全',
            '采购记录、发票、随货同行单“票账货”一致',
            '验收按批号抽样并记录完整',
            '库房温湿度监测正常，超标及时处置并记录',
            '冷藏药品验证报告齐全，运输有温度记录',
            '计算机系统权限管理规范，追溯数据完整',
            '执业药师在岗，处方药审核记录齐全',
            '近效期预警与不合格品处理记录完整',
        ],
    },
    'org': {
        'name': '医疗机构药事管理合规自查',
        'items': [
            '药事管理与药物治疗学委员会按规运行（会议、议题、记录）',
            '用药目录年度评审并动态调整',
            '新药引进经评审程序',
            '药品采购渠道合法，供应商资质档案齐全',
            '处方审核全覆盖，点评按月开展（门急诊≥100张/月）',
            '麻精药品“五专”落实、账物相符',
            '抗菌药物分级管理与处方权限落实',
            '药品不良反应上报及时、数量质量达标',
            '效期药品、报损与召回管理规范',
            '药学人员配比与培训记录完整',
        ],
    },
    'five_special': {
        'name': '麻醉药品与第一类精神药品“五专”自查',
        'items': [
            '专人负责：明确专人保管、双人双锁',
            '专柜加锁：专柜（库）加锁且钥匙密码分开',
            '专用账册：逐笔登记、账物相符',
            '专用处方：红色处方、处方权人备案',
            '专册登记：使用消耗专册完整（含空安瓿回收）',
            '过期/损毁药品按规定申请监督销毁',
            '处方保存3年（麻一精）落实',
        ],
    },
    'adr': {
        'name': '药品不良反应报告制度自查',
        'items': [
            '制定不良反应监测报告制度并有专人负责',
            '医务人员知晓报告范围（新药监测期内所有、其他新的和严重的）',
            '死亡病例立即报告、严重15日内、其他30日内',
            '群体不良事件立即上报并采取控制措施',
            '近一年有培训与考核记录',
            '报告质量（因果关系评价、随访）符合要求',
        ],
    },
}

CHECKLIST_ALIAS = {
    'company': ['gsp', '经营', '企业', '零售', '批发'],
    'org': ['机构', '医疗', '医院', '药事管理', '药房'],
    'five_special': ['五专', '麻精', '麻醉', '精神药品'],
    'adr': ['不良反应', 'adr', '监测'],
}

def checklist_start(kind):
    if kind not in CHECKLISTS:
        return None
    return {'kind': kind, 'answers': [], 'index': 0}

def checklist_step(state, answer):
    key = answer.strip().lower()
    if key in ('是', 'y', 'yes', '√', '对', '符合', 'ok', '1'):
        val = True
    elif key in ('否', 'n', 'no', 'x', '×', '不对', '不符合', '0'):
        val = False
    else:
        return False, '请回答：是 / 否（不确定请答“否”并备注）。'
    state['answers'].append(val)
    state['index'] += 1
    cl = CHECKLISTS[state['kind']]
    if state['index'] >= len(cl['items']):
        return True, None
    return False, None

def checklist_report(state):
    cl = CHECKLISTS[state['kind']]
    total = len(cl['items'])
    yes = sum(1 for a in state['answers'] if a)
    rate = int(yes * 100 / total) if total else 100
    lines = ['【%s 自查结果】通过 %d/%d（%d%%）' % (cl['name'], yes, total, rate)]
    no_pos = []
    for i, a in enumerate(state['answers']):
        if not a:
            no_pos.append(cl['items'][i])
    if no_pos:
        lines.append('以下项目未通过/待整改：')
        for i, it in enumerate(no_pos, 1):
            lines.append('%d. %s' % (i, it))
        lines.append('提示：可对照 knowledge_base 对应专题完善制度与记录；重大合规风险建议咨询执业药师及属地监管部门。')
    else:
        lines.append('全部通过！请保存记录并纳入质量管理体系文件。')
    return '\n'.join(lines)

TEMPLATE_INDEX = [
    ('制度汇编', 'services/templates/制度模板_药事管理制度汇编.md', '20项制度目录+单份制度示例'),
    ('处方审核记录', 'services/templates/记录模板_处方审核调剂与四查十对.md', '四查十对核对单+适宜性审核要点+干预记录'),
    ('不良反应报告表', 'services/templates/记录模板_药品不良反应报告表.md', '报告表结构+关联性评价+时限提醒'),
    ('年度培训计划', 'services/templates/培训模板_药事管理年度培训计划.md', '四季培训主题+记录要素'),
]

def list_templates():
    lines = ['可用模板（项目 services 目录）：']
    for name, path, desc in TEMPLATE_INDEX:
        lines.append('- %s：%s（%s）' % (name, path, desc))
    return '\n'.join(lines)

def match_checklist(text):
    t = text.lower()
    for kind, aliases in CHECKLIST_ALIAS.items():
        for a in aliases:
            if a.lower() in t:
                return kind
    return None