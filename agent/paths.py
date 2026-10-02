# -*- coding: utf-8 -*-
# paths.py — 运行路径解析（源码 / PyInstaller exe 双模式）
import os
import sys

def _base():
    """内置只读资源根（知识库/服务/前端）"""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.isdir(os.path.join(exe_dir, 'knowledge_base')):
            return exe_dir, exe_dir   # exe 旁自带自定义资源
        return getattr(sys, '_MEIPASS', exe_dir), exe_dir
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return root, root

BASE, DATA_BASE = _base()
KB_DIR = os.path.join(BASE, 'knowledge_base')
SERVICE_DIR = os.path.join(BASE, 'services')
WEB_DIR = os.path.join(BASE, 'web')
MEMORY_DIR = os.path.join(DATA_BASE, 'memory')
CONFIG_PATH = os.path.join(DATA_BASE, 'config.json')

def ensure_dirs():
    try:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        return True
    except Exception:
        return False