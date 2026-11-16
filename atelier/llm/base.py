"""大模型适配层。上层只调用 client.chat(system, messages, task=...) -> str。

messages: [{"role": "user"|"assistant", "text": str, "images": [png/jpeg bytes, ...]}]
两种线协议覆盖了几乎所有主流模型:
  - anthropic : Claude 的 Messages API
  - openai    : /chat/completions (OpenAI、Gemini 兼容端点、DeepSeek、通义、OpenRouter、Ollama、LM Studio、各种中转)
只用标准库 urllib，不绑任何厂商 SDK，换模型只改配置。
"""
import base64, json, re, urllib.request, urllib.error


class LLMError(Exception):
    pass


def _mime(b):
    return "image/png" if b[:4] == b"\x89PNG" else ("image/webp" if b[8:12] == b"WEBP" else "image/jpeg")


def _post(url, headers, body, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise LLMError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:600]}")
    except Exception as e:
        raise LLMError(f"请求失败: {e}")


class AnthropicClient:
    def __init__(self, cfg):
        self.cfg = cfg
        self.base = (cfg.get("base_url") or "https://api.anthropic.com").rstrip("/")

    def chat(self, system, messages, task=None):
        msgs = []
        for m in messages:
            content = [{"type": "image", "source": {"type": "base64", "media_type": _mime(b), "data": base64.b64encode(b).decode()}}
                       for b in m.get("images", []) if self.cfg.get("vision", True)]
            content.append({"type": "text", "text": m["text"]})
            msgs.append({"role": m["role"], "content": content})
        body = {"model": self.cfg["model"], "max_tokens": int(self.cfg.get("max_tokens", 16000)), "system": system, "messages": msgs}
        if self.cfg.get("temperature") is not None and self.cfg.get("send_temperature", False):
            body["temperature"] = self.cfg["temperature"]
        r = _post(self.base + "/v1/messages", {"x-api-key": self.cfg.get("api_key", ""), "anthropic-version": "2023-06-01"}, body)
        text = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        if not text: raise LLMError(f"模型没有返回文本: {str(r)[:300]}")
        if r.get("stop_reason") == "max_tokens": text += "\n/*TRUNCATED*/"
        return text


class OpenAICompatClient:
    def __init__(self, cfg):
        self.cfg = cfg
        if not cfg.get("base_url"): raise LLMError("缺少 base_url")
        self.base = cfg["base_url"].rstrip("/")

    def chat(self, system, messages, task=None):
        msgs = [{"role": "system", "content": system}]
        for m in messages:
            imgs = m.get("images", []) if self.cfg.get("vision", True) else []
            if imgs:
                content = [{"type": "text", "text": m["text"]}] + [
                    {"type": "image_url", "image_url": {"url": f"data:{_mime(b)};base64,{base64.b64encode(b).decode()}"}} for b in imgs]
            else:
                content = m["text"]
            msgs.append({"role": m["role"], "content": content})
        body = {"model": self.cfg["model"], "messages": msgs}
        # 各家对 max_tokens / max_completion_tokens / temperature 的支持不一致，默认都不发，需要时在配置里打开
        if self.cfg.get("send_max_tokens", False): body["max_tokens"] = int(self.cfg.get("max_tokens", 16000))
        if self.cfg.get("send_temperature", False): body["temperature"] = self.cfg.get("temperature", 0.6)
        headers = {"authorization": "Bearer " + self.cfg["api_key"]} if self.cfg.get("api_key") else {}
        r = _post(self.base + "/chat/completions", headers, body)
        try:
            ch = r["choices"][0]; text = ch["message"]["content"]
            if isinstance(text, list): text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
        except Exception:
            raise LLMError(f"无法解析返回: {str(r)[:300]}")
        if not text: raise LLMError("模型返回为空")
        if ch.get("finish_reason") == "length": text += "\n/*TRUNCATED*/"
        return text


def make_client(cfg):
    from ..config import PROVIDER_PRESETS
    preset = PROVIDER_PRESETS.get(cfg.get("provider", "mock"), PROVIDER_PRESETS["custom"])
    cfg = dict(cfg); cfg["base_url"] = cfg.get("base_url") or preset["base_url"]
    kind = preset["kind"]
    if kind == "mock":
        from .mock import MockClient
        return MockClient(cfg)
    if not cfg.get("model"): raise LLMError("请在设置里填写模型名 (model)")
    return AnthropicClient(cfg) if kind == "anthropic" else OpenAICompatClient(cfg)


def extract_json(text):
    """从模型输出里抠出 JSON 对象: 容忍 ```json 围栏、前后废话、// 注释、尾逗号。"""
    if "/*TRUNCATED*/" in text:
        raise LLMError("模型输出被长度上限截断 (可调大 max_tokens，或减小建筑规模/分组件生成)")
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    cand = m.group(1) if m else None
    if cand is None:
        i = text.find("{")
        if i < 0: raise LLMError("模型输出里没有 JSON 对象")
        depth = 0; in_s = False; esc = False; end = -1
        for j in range(i, len(text)):
            c = text[j]
            if in_s:
                if esc: esc = False
                elif c == "\\": esc = True
                elif c == '"': in_s = False
            elif c == '"': in_s = True
            elif c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0: end = j; break
        if end < 0: raise LLMError("JSON 不完整 (括号未闭合)")
        cand = text[i:end + 1]
    for attempt in (cand, re.sub(r",\s*([}\]])", r"\1", re.sub(r"(?m)^\s*//.*$|(?<=[,\[{\s])//[^\n\"]*$", "", cand))):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError as e:
            err = e
    raise LLMError(f"JSON 解析失败: {err}")
