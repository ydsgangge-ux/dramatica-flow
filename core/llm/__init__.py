"""
LLM 抽象层
DeepSeek 走 OpenAI 兼容接口，支持多 Provider 路由
"""
from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class LLMMessage:
    role: str   # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 0  # 0 = 不限制，让模型自行决定


# ── 异常 ──────────────────────────────────────────────────────────────────────

class LLMError(Exception):
    pass


class LLMParseError(LLMError):
    """LLM 输出无法解析为目标 schema"""
    def __init__(self, message: str, raw_output: str):
        super().__init__(message)
        self.raw_output = raw_output


# ── Provider 抽象接口 ─────────────────────────────────────────────────────────

class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        ...

    @abstractmethod
    def stream(
        self,
        messages: list[LLMMessage],
        on_chunk: Callable[[str], None],
    ) -> LLMResponse:
        ...


# ── DeepSeek Provider（OpenAI SDK 兼容） ──────────────────────────────────────

class DeepSeekProvider(LLMProvider):
    """
    DeepSeek 通过 OpenAI 兼容接口接入。
    同样适用于其他 OpenAI 兼容接口（中转站、本地 Ollama 等）。
    """

    def __init__(self, config: LLMConfig):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError:
            raise LLMError("请先安装 openai: pip install openai")

        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=(30, 600),
        )

    def _build_kwargs(self, stream: bool = False) -> dict:
        kwargs = dict(model=self.config.model, temperature=self.config.temperature, stream=stream)
        if self.config.max_tokens > 0:
            kwargs["max_tokens"] = self.config.max_tokens
        return kwargs

    def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        response = self.client.chat.completions.create(
            messages=[m.to_dict() for m in messages], **self._build_kwargs(stream=False))
        content = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResponse(
            content=content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def stream(self, messages: list[LLMMessage], on_chunk: Callable[[str], None]) -> LLMResponse:
        full_content = ""
        stream = self.client.chat.completions.create(
            messages=[m.to_dict() for m in messages], **self._build_kwargs(stream=True))
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_content += delta
                on_chunk(delta)
        return LLMResponse(content=full_content)


# ── Ollama Provider ─────────────────────────────────────────────────────────────

class OllamaProvider(LLMProvider):
    """
    Ollama 本地模型通过 OpenAI 兼容接口接入。
    默认连接 http://localhost:11434/v1
    """

    def __init__(self, config: LLMConfig | None = None):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError:
            raise LLMError("请先安装 openai: pip install openai")

        if config is None:
            config = LLMConfig(
                api_key="ollama",
                base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                model=os.environ.get("OLLAMA_MODEL", "llama3.1"),
                temperature=float(os.environ.get("DEFAULT_TEMPERATURE", "0.7")),
            )
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=(30, 600),
        )

    def _build_kwargs(self, stream: bool = False) -> dict:
        kwargs = dict(model=self.config.model, temperature=self.config.temperature, stream=stream)
        if self.config.max_tokens > 0:
            kwargs["max_tokens"] = self.config.max_tokens
        return kwargs

    def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        response = self.client.chat.completions.create(
            messages=[m.to_dict() for m in messages], **self._build_kwargs(stream=False))
        content = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResponse(
            content=content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def stream(self, messages: list[LLMMessage], on_chunk: Callable[[str], None]) -> LLMResponse:
        full_content = ""
        stream = self.client.chat.completions.create(
            messages=[m.to_dict() for m in messages], **self._build_kwargs(stream=True))
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_content += delta
                on_chunk(delta)
        return LLMResponse(content=full_content)


# ── Pydantic Schema 安全解析 ──────────────────────────────────────────────────

def parse_llm_json(
    raw: str,
    schema: type[T],
    context: str = "",
    patch_fn: Callable[[dict], dict] | None = None,
) -> T:
    """
    从 LLM 输出中安全解析 JSON。
    支持 ```json ... ``` 包裹，解析失败时抛出带上下文的错误。
    patch_fn: 可选回调，在 Pydantic 验证前对 dict 做修正（补缺字段等）。
    """
    # 剥离 ```json ... ``` 或 ``` ... ```
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    stripped = re.sub(r"\s*```\s*$", "", stripped, flags=re.MULTILINE).strip()

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as e:
        # 尝试修复截断的 JSON
        repaired = _repair_truncated_json(stripped)
        try:
            data = json.loads(repaired)
        except json.JSONDecodeError:
            ctx = f" ({context})" if context else ""
            raise LLMParseError(
                f"JSON 解析失败{ctx}: {e}",
                raw_output=raw,
            )

    if patch_fn and isinstance(data, dict):
        data = patch_fn(data)

    try:
        return schema.model_validate(data)
    except ValidationError as e:
        # fallback: 通用修复 sequences 中的 dramatic_function 和缺失字段
        if isinstance(data, dict) and "sequences" in data:
            data_copy = dict(data)
            fixed_seqs = []
            for si, seq in enumerate(data_copy["sequences"]):
                if not isinstance(seq, dict):
                    fixed_seqs.append(seq)
                    continue
                seq = dict(seq)
                # 补 narrative_goal
                if not seq.get("narrative_goal"):
                    seq["narrative_goal"] = seq.get("summary", "推进剧情")
                # 修正 dramatic_function
                if seq.get("dramatic_function"):
                    seq["dramatic_function"] = _fix_df(seq["dramatic_function"])
                fixed_seqs.append(seq)
            data_copy["sequences"] = fixed_seqs
            try:
                return schema.model_validate(data_copy)
            except ValidationError:
                pass
        ctx = f" ({context})" if context else ""
        raise LLMParseError(
            f"Schema 校验失败{ctx}: {e}",
            raw_output=raw,
        )


def _quote_bare_keys(text: str) -> str:
    """
    给裸露的属性名补上双引号：{name: "x", age: 1} -> {"name": "x", "age": 1}
    只匹配紧跟在 { 或 , 之后的「标识符 + 冒号」，尽量不误伤字符串内容。
    """
    return re.sub(
        r'([{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*:)',
        lambda m: f'{m.group(1)}"{m.group(2)}"{m.group(3)}',
        text,
    )


def _fix_unescaped_inner_quotes(text: str) -> str:
    """
    修复字符串值内部未转义的引号，例如：
      "dramatic_question": "以"守"证道的心剑，能否胜过以"夺"证道？"
    模型常把中文引号写成 ASCII 双引号，导致 JSON 断在字符串中间。
    逐行处理：只有当「key: "value"」整行单独解析失败时才转义内部引号。
    """
    line_re = re.compile(r'^(\s*"[^"]+"\s*:\s*")(.*)("\s*,?\s*)$')
    out = []
    for line in text.split("\n"):
        m = line_re.match(line)
        if not m:
            out.append(line)
            continue
        # 能独立解析成 {key: value} 说明这一行本身没问题，不动
        try:
            json.loads("{" + line.strip().rstrip(",") + "}")
            out.append(line)
            continue
        except Exception:
            pass
        inner = m.group(2)
        # 先把已转义的引号保护起来，避免二次转义
        inner = inner.replace('\\"', "\x00")
        inner = inner.replace('"', '\\"').replace("\x00", '\\"')
        out.append(m.group(1) + inner + m.group(3))
    return "\n".join(out)


def _repair_truncated_json(text: str) -> str:
    """尝试修复被 max_tokens 截断的 JSON（补全未闭合的括号/大括号）"""
    # 先补属性名的双引号（模型常输出 {name: "x"} 这类非法 JSON）
    text = _quote_bare_keys(text)
    # 再修复字符串值内部未转义的引号（中文引号被写成 ASCII 双引号）
    text = _fix_unescaped_inner_quotes(text)
    # 去掉末尾可能残留的不完整内容：截断到最后一个完整对象（} 或 ]）
    # 先尝试直接补全
    depth = 0
    in_str = False
    escape = False
    last_valid = -1
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_str:
            escape = True
            continue
        if ch == '"' and not escape:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ('{', '['):
            depth += 1
        elif ch in ('}', ']'):
            depth -= 1
        if ch == '}':
            last_valid = i
        elif ch == ']':
            last_valid = i

    # 如果在字符串中间截断，截到 last_valid
    if in_str:
        if last_valid >= 0:
            text = text[:last_valid + 1]
        else:
            return text  # 无法修复

    # 计算未闭合的括号
    depth = 0
    in_str = False
    escape = False
    stack = []
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\' and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            depth += 1
            stack.append('}')
        elif ch == '[':
            depth += 1
            stack.append(']')
        elif ch == '}':
            if stack and stack[-1] == '}':
                stack.pop()
                depth -= 1
        elif ch == ']':
            if stack and stack[-1] == ']':
                stack.pop()
                depth -= 1

    # 去掉末尾悬空的逗号
    text = re.sub(r',\s*$', '', text.strip())
    # 去掉末尾悬空的冒号+空值
    text = re.sub(r':\s*$', '', text.strip())

    # 补全未闭合的括号
    while stack:
        text += stack.pop()
    return text


# dramatic_function 通用别名映射（兼容各种 AI 输出）
_DF_FALLBACK_MAP: dict[str, str] = {
    "twist": "turning", "turn": "turning", "turning_point": "turning", "turning-point": "turning",
    "progressive complication": "turning", "complication": "turning",
    "hook": "inciting", "trigger": "inciting", "inciting_incident": "inciting", "inciting-incident": "inciting",
    "conflict": "crisis", "crash": "crisis", "dark night": "crisis", "all is lost": "crisis", "lowest point": "crisis",
    "battle": "climax", "peak": "climax", "climax_build": "climax", "showdown": "climax", "confrontation": "climax",
    "ending": "consequence", "result": "consequence", "resolution": "consequence", "denouement": "consequence", "new_world": "consequence",
    "info": "reveal", "discover": "reveal", "revelation": "reveal", "discovery": "reveal",
    "choice": "decision", "select": "decision", "commitment": "decision",
    "build": "setup", "establish": "setup", "intro": "setup", "introduct": "setup", "exposition": "setup",
    "bridge": "transition", "pause": "transition", "interlude": "transition",
    "middle": "midpoint", "mid_point": "midpoint", "mid-point": "midpoint",
}
_VALID_DF_SET = {"setup", "inciting", "turning", "midpoint", "crisis", "climax", "reveal", "decision", "consequence", "transition"}


def _fix_df(val: str) -> str:
    """将 AI 输出的 dramatic_function 修正为合法枚举值"""
    if val in _VALID_DF_SET:
        return val
    mapped = _DF_FALLBACK_MAP.get(val.lower().strip())
    return mapped if mapped else "transition"


def parse_llm_json_list(
    raw: str,
    schema: type[T],
    context: str = "",
    patch_fn: Callable[[dict], dict] | None = None,
) -> list[T]:
    """解析 LLM 输出的 JSON 数组

    patch_fn: 可选回调，在 Pydantic 验证前对每个 dict 项做修正（补缺字段等）
    """
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    stripped = re.sub(r"\s*```\s*$", "", stripped, flags=re.MULTILINE).strip()

    data_list = None
    try:
        data_list = json.loads(stripped)
    except json.JSONDecodeError:
        # 尝试修复截断的 JSON
        repaired = _repair_truncated_json(stripped)
        try:
            data_list = json.loads(repaired)
        except json.JSONDecodeError as e:
            ctx = f" ({context})" if context else ""
            raise LLMParseError(f"JSON 列表解析失败{ctx}: {e}", raw_output=raw)

    if not isinstance(data_list, list):
        ctx = f" ({context})" if context else ""
        raise LLMParseError(
            f"期望 JSON 数组，得到 {type(data_list).__name__}{ctx}",
            raw_output=raw,
        )

    results = []
    failures: list[str] = []
    for i, item in enumerate(data_list):
        if patch_fn and isinstance(item, dict):
            item = patch_fn(item)
        try:
            results.append(schema.model_validate(item))
        except ValidationError as e:
            # 单个元素校验失败不阻塞，尝试修复后重试
            if isinstance(item, dict) and "beats" in item:
                item_copy = dict(item)
                # 修正章节级 dramatic_function
                if item_copy.get("dramatic_function"):
                    item_copy["dramatic_function"] = _fix_df(item_copy["dramatic_function"])
                valid_beats = []
                for beat in item_copy.get("beats", []):
                    if isinstance(beat, dict):
                        # 确保 beat 有 id
                        if "id" not in beat:
                            beat["id"] = f"beat_{item_copy.get('chapter_number', i)}_{len(valid_beats)+1}"
                        # 修正 beat 的 dramatic_function
                        if beat.get("dramatic_function"):
                            beat["dramatic_function"] = _fix_df(beat["dramatic_function"])
                        # 移除可能导致验证失败的非必需字段
                        beat.pop("target_words", None)
                        beat.pop("emotional_target", None)
                        valid_beats.append(beat)
                item_copy["beats"] = valid_beats
                try:
                    results.append(schema.model_validate(item_copy))
                    continue
                except ValidationError:
                    pass
            # 记录失败项，全部解析完后统一报错（不再静默丢弃，避免用占位章掩盖问题）
            idx = item.get("chapter_number", i) if isinstance(item, dict) else i
            failures.append(f"#{idx}: {e.errors()[0].get('msg', e)}")
            continue

    if failures:
        ctx = f" ({context})" if context else ""
        raise LLMParseError(
            f"JSON 列表有 {len(failures)}/{len(data_list)} 项校验失败{ctx}："
            + "；".join(failures[:5]),
            raw_output=raw,
        )
    return results


# ── Retry 装饰器 ──────────────────────────────────────────────────────────────

# 限流(429/排队)与临时网络错误的最大重试次数（高于普通错误）
_RETRY_HARD_CAP = 7


def _retry_kind(e: Exception) -> str:
    """判断错误类型：
    - "rate_limit"：服务端限流/排队（429），应放慢指数退避多等一会儿
    - "network"   ：连接/超时/断线重置，应稍等后重连
    - ""          ：其他错误（JSON/格式等），走原快速重试
    """
    msg = str(e).lower()
    if (
        "429" in msg
        or "rate limit" in msg
        or "too many requests" in msg
        or "rate_limit_reached" in msg
    ):
        return "rate_limit"
    if (
        "timeout" in msg
        or "timed out" in msg
        or "read timed" in msg
        or "connection" in msg
        or "refused" in msg
        or "econnreset" in msg
        or "econnrefused" in msg
        or "server disconnected" in msg
        or "remote disconnected" in msg
        or "bad gateway" in msg
        or "gateway error" in msg
        or "internal server error" in msg
    ):
        return "network"
    return ""


def with_retry(
    fn: Callable[[], T],
    max_attempts: int = 3,
    delay_seconds: float = 2.0,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """
    同步重试包装器，支持排队(429)与断线优化。

    - rate_limit(限流/排队)：指数退避 + 随机抖动，最多 _RETRY_HARD_CAP 次，
      GLM-4.7-Flash 这类 1 并发模型高峰期排队时会自动等待而非失败。
    - network(连接/超时/断线)：中速退避重连，也允许更多尝试。
    - 其他错误(JSON/格式)：维持原快速重试，最多 max_attempts 次。
    """
    import random
    last_error: Exception = RuntimeError("Unknown error")
    hard_cap = int(max_attempts)  # 普通错误次数
    for attempt in range(1, _RETRY_HARD_CAP + 1):
        try:
            return fn()
        except Exception as e:
            last_error = e
            kind = _retry_kind(e)
            # 普通错误用 max_attempts，排队/断线用更大上限
            effective_max = hard_cap if not kind else _RETRY_HARD_CAP
            if attempt < effective_max:
                if on_retry:
                    on_retry(attempt, e)
                if kind == "rate_limit":
                    # 排队：指数退避 + 抖动，上限约 60s
                    backoff = min(60.0, 3.0 * (2 ** (attempt - 1)))
                    time.sleep(backoff + random.uniform(0, 2.0))
                elif kind == "network":
                    # 断线：中速退避重连，上限约 30s
                    backoff = min(30.0, 2.0 * (2 ** (attempt - 1)))
                    time.sleep(backoff + random.uniform(0, 1.0))
                else:
                    time.sleep(delay_seconds * attempt)
    raise last_error


# ── Provider 工厂 ─────────────────────────────────────────────────────────────

def create_provider(config: LLMConfig | None = None, provider_type: str | None = None) -> LLMProvider:
    """
    从环境变量或显式配置创建 Provider。
    默认读取 .env 中的 DEEPSEEK_* 配置。
    
    Args:
        config: 显式配置，如未提供则从环境变量读取
        provider_type: "deepseek" 或 "ollama"，如未指定则从 LLM_PROVIDER 环境变量读取
    """
    if provider_type is None:
        provider_type = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    
    if provider_type == "ollama":
        if config is None:
            return OllamaProvider()
        return OllamaProvider(config)
    
    # 默认使用 DeepSeek
    if config is None:
        config = LLMConfig(
            api_key  = os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model    = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
            temperature = float(os.environ.get("DEFAULT_TEMPERATURE", "0.7")),
        )
    return DeepSeekProvider(config)
