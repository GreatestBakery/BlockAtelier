import json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("ATELIER_DATA", ROOT / "data"))
VERSIONS = DATA / "versions"
WORKSPACE = Path(os.environ.get("ATELIER_WORKSPACE", ROOT / "workspace"))
CONFIG_FILE = WORKSPACE / "config.json"

# 主流大模型接入预设。除 anthropic 外都走 OpenAI 兼容的 /chat/completions 协议。
# model 一栏请填你账号里实际可用的模型名（各家更新很快，这里只给地址，不替你猜型号）。
PROVIDER_PRESETS = {
    "mock":       {"kind": "mock", "base_url": "", "note": "离线规则引擎，不联网，用于自检和演示"},
    "anthropic":  {"kind": "anthropic", "base_url": "https://api.anthropic.com", "note": "Claude (Messages API)"},
    "openai":     {"kind": "openai", "base_url": "https://api.openai.com/v1", "note": "OpenAI"},
    "gemini":     {"kind": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "note": "Google Gemini (OpenAI 兼容端点)"},
    "deepseek":   {"kind": "openai", "base_url": "https://api.deepseek.com", "note": "DeepSeek"},
    "qwen":       {"kind": "openai", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "note": "通义千问 (DashScope 兼容模式)"},
    "openrouter": {"kind": "openai", "base_url": "https://openrouter.ai/api/v1", "note": "OpenRouter (聚合多家)"},
    "ollama":     {"kind": "openai", "base_url": "http://localhost:11434/v1", "note": "本地 Ollama"},
    "custom":     {"kind": "openai", "base_url": "", "note": "任何 OpenAI 兼容服务 (LM Studio / vLLM / 中转)"},
}

DEFAULTS = {
    "provider": "mock", "model": "", "api_key": "", "base_url": "",
    "vision": True,            # 模型是否支持看图 (参考图 + 渲染自检)
    "max_tokens": 16000, "temperature": 0.6,
    "repair_rounds": 2,        # 结构校验不过时让模型修几轮
    "critique_rounds": 1,      # 渲染后让模型看图自评几轮 (0 关闭)
    "searxng_url": "",         # 可选: 自建 SearXNG 用于联网找参考
    "blender_path": "blender", # Blender 可执行文件
    "default_version": "",     # 空 = 本地最新的版本档案
    "author": "BlockAtelier",
}


def load_config():
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try: cfg.update(json.loads(CONFIG_FILE.read_text("utf-8")))
        except Exception: pass
    for k in ("provider", "model", "api_key", "base_url"):   # 环境变量优先，方便不把 key 落盘
        v = os.environ.get("ATELIER_" + k.upper())
        if v: cfg[k] = v
    return cfg


def save_config(patch):
    cfg = {}
    if CONFIG_FILE.exists():
        try: cfg = json.loads(CONFIG_FILE.read_text("utf-8"))
        except Exception: cfg = {}
    cfg.update({k: v for k, v in patch.items() if k in DEFAULTS})
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), "utf-8")
    return load_config()
