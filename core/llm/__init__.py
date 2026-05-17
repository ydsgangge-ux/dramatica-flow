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


def _repair_truncated_json(text: str) -> str:
    """尝试修复被 max_tokens 截断的 JSON（补全未闭合的括号/大括号）"""
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
            continue
    return results


# ── Retry 装饰器 ──────────────────────────────────────────────────────────────

def with_retry(
    fn: Callable[[], T],
    max_attempts: int = 3,
    delay_seconds: float = 2.0,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """
    同步重试包装器。
    LLMParseError 会触发重试；网络错误也会重试。
    """
    last_error: Exception = RuntimeError("Unknown error")
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                if on_retry:
                    on_retry(attempt, e)
                time.sleep(delay_seconds * attempt)
    raise last_error


# ── Provider 工厂 ─────────────────────────────────────────────────────────────

def create_provider(config: LLMConfig | None = None, provider_type: str | None = None) -> LLMProvider:
    """
    从环境变量或显式配置创建 Provider。
    
    Args:
        config: 显式配置，如未提供则从环境变量读取
        provider_type: "deepseek" / "ollama" / "openai" / "zhipu" / "moonshot" / "qwen" / "custom"，
                      如未指定则从 LLM_PROVIDER 环境变量读取
    """
    if provider_type is None:
        provider_type = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    
    if provider_type == "ollama":
        if config is None:
            return OllamaProvider()
        return OllamaProvider(config)
    
    # 非 Ollama 统一走 OpenAI 兼容接口（deepseek / openai / zhipu / moonshot / qwen / custom）
    if config is None:
        env_prefix = provider_type.upper() + "_"
        config = LLMConfig(
            api_key  = os.environ.get(f"{env_prefix}API_KEY", os.environ.get("DEEPSEEK_API_KEY", "")),
            base_url = os.environ.get(f"{env_prefix}BASE_URL", os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")),
            model    = os.environ.get(f"{env_prefix}MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")),
            temperature = float(os.environ.get("DEFAULT_TEMPERATURE", "0.7")),
        )
    return DeepSeekProvider(config)
