# -*- coding: utf-8 -*-
# tools_mcp.py — 最小 MCP（Model Context Protocol）stdio 服务器（第10章）
# 协议层：JSON-RPC 2.0 over stdio，实现 initialize / tools/list / tools/call
# 用法：python agent/tools_mcp.py  （可被 Claude Desktop / Cursor / 自定义客户端以 stdio 方式挂载）
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import load_kb
from tools import TOOLS, execute_tool

chunks, idf = load_kb()
CTX = {'chunks': chunks, 'idf': idf}

def make_jsonrpc(id, result=None, error=None):
    msg = {'jsonrpc': '2.0', 'id': id}
    if error is not None:
        msg['error'] = error
    else:
        msg['result'] = result
    return msg

def handle(msg):
    mid = msg.get('id')
    method = msg.get('method', '')
    params = msg.get('params') or {}
    if method == 'initialize':
        return make_jsonrpc(mid, {
            'protocolVersion': '2024-11-05',
            'capabilities': {'tools': {}},
            'serverInfo': {'name': 'leeberty-pharma-agent', 'version': '3.0.0'},
        })
    if method == 'notifications/initialized':
        return None
    if method == 'tools/list':
        tools = [
            {
                'name': name,
                'description': t['desc'] + '。参数：' + t['params'],
                'inputSchema': {'type': 'object', 'properties': {'args': {'type': 'string', 'description': '以 | 分隔的参数'}}, 'required': ['args']},
            }
            for name, t in TOOLS.items()
        ]
        return make_jsonrpc(mid, {'tools': tools})
    if method == 'tools/call':
        name = params.get('name', '')
        args = params.get('arguments', {}).get('args', '')
        t0 = time.time()
        text, src = execute_tool(name, str(args), CTX)
        content = [{'type': 'text', 'text': text},
                   {'type': 'text', 'text': '来源：' + ('；'.join(src) if src else '无')}]
        return make_jsonrpc(mid, {'content': content, 'isError': False, 'meta': {'elapsed_ms': int((time.time() - t0) * 1000)}})
    return make_jsonrpc(mid, error={'code': -32601, 'message': 'method not found: ' + method})

def main():
    """stdio 循环：逐行读取 JSON-RPC 消息并响应"""
    print('[MCP] 药事管理工具服务器已就绪（6 个工具），等待客户端…', file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + '\n')
            sys.stdout.flush()

if __name__ == '__main__':
    main()