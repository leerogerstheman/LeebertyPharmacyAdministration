# -*- coding: utf-8 -*-
# engine.py — LeebertyPharmacyAdministration 知识检索引擎（纯 Python 标准库）
# 功能：加载 knowledge_base/*.md，按 "##" 标题切块，字符 n-gram + TF-IDF 余弦检索
import os
import re
import math
from collections import Counter

from paths import KB_DIR
CHUNK_MIN_LEN = 40
TOP_K_DEFAULT = 3

class Chunk:
    __slots__ = ('doc', 'heading', 'text', 'path', 'n_grams', 'tf', 'norm')

    def __init__(self, doc, heading, text, path):
        self.doc = doc
        self.heading = heading
        self.text = text
        self.path = path
        grams = ngrams(text)
        self.n_grams = grams
        self.tf = Counter(grams)
        self.norm = math.sqrt(sum(v * v for v in self.tf.values())) or 1.0

def ngrams(text, ns=(2, 3)):
    s = re.sub('[\\s\\u3000\\n\\r\\t]+', '', text)
    grams = []
    for n in ns:
        if len(s) >= n:
            grams.extend(s[i:i + n] for i in range(len(s) - n + 1))
    return grams

def load_kb(kb_dir=None):
    kb_dir = kb_dir or KB_DIR
    chunks = []
    if not os.path.isdir(kb_dir):
        return chunks, {}
    for fname in sorted(os.listdir(kb_dir)):
        if not fname.endswith('.md'):
            continue
        path = os.path.join(kb_dir, fname)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        doc_title = fname.replace('.md', '')
        first_m = re.match(r'^#\s+(.+?)\s*$', content)
        if first_m:
            doc_title = first_m.group(1).strip()
        parts = re.split(r'(?m)^##\s+(.+?)\s*$', content)
        heads = parts[1::2]
        bodies = parts[2::2]
        if not heads:
            t = parts[0].strip()
            if len(t) >= CHUNK_MIN_LEN:
                chunks.append(Chunk(doc_title, doc_title, t, fname))
            continue
        for h, b in zip(heads, bodies):
            text = h + '。\n' + b.strip()
            if len(text) >= CHUNK_MIN_LEN:
                chunks.append(Chunk(doc_title, h.strip(), text, fname))
    N = float(len(chunks))
    df = {}
    for c in chunks:
        for g in set(c.n_grams):
            df[g] = df.get(g, 0) + 1
    idf = {g: math.log(1.0 + N / (1.0 + f)) for g, f in df.items()}
    return chunks, idf

def search(query, chunks, idf, top_k=TOP_K_DEFAULT):
    if not chunks:
        return []
    q_grams = ngrams(query)
    if not q_grams:
        return []
    q_tf = Counter(q_grams)
    q_norm = math.sqrt(sum(v * v for v in q_tf.values())) or 1.0
    scored = []
    for c in chunks:
        dot = 0.0
        for g, f in q_tf.items():
            w = idf.get(g, 0.0) * f
            if w and g in c.tf:
                dot += w * c.tf[g] * idf.get(g, 0.0)
        if dot > 0:
            scored.append((dot / (q_norm * c.norm), c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]

def make_answer(query, chunks, idf, top_k=TOP_K_DEFAULT, max_len=1000):
    hits = search(query, chunks, idf, top_k)
    if not hits:
        return None
    lines = []
    for i, (score, c) in enumerate(hits, 1):
        lines.append('【%d】《%s》·%s（相关度 %.2f）' % (i, c.doc, c.heading, score))
        body = c.text
        snippet = body
        for key in query:
            if len(key) >= 2 and key in body:
                idx = body.find(key)
                start = max(0, idx - 60)
                snippet = body[start:start + max_len]
                break
        tail = '……' if len(body) > len(snippet.strip()) else ''
        lines.append(snippet.strip() + tail)
        lines.append('来源：knowledge_base/' + c.path)
        lines.append('')
    return '\n'.join(lines).rstrip()

def stats(chunks):
    docs = set()
    for c in chunks:
        docs.add(c.doc)
    return {'chunks': len(chunks), 'docs': len(docs)}