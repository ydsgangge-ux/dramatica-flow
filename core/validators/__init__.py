"""
写后验证器
纯规则检测，零 LLM 成本
借鉴 InkOS 设计，但聚焦叙事质量而非平台合规
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ValidationIssue:
    rule: str
    severity: Literal["error", "warning"]
    description: str
    excerpt: str | None = None


@dataclass
class ValidationResult:
    passed: bool  # error 级别为 0
    issues: list[ValidationIssue]
    word_count: int

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ── 规则库 ────────────────────────────────────────────────────────────────────

# 每 3000 字最多出现 1 次的 AI 标记词
AI_MARKER_WORDS = [
    "仿佛", "忽然", "竟然", "不禁", "宛如",
    "猛地", "顿时", "霎时", "不由得",
]

# 绝对禁止的句式
FORBIDDEN_PHRASES = [
    "不是……而是……",
    "全场震惊",
    "众人哗然",
    "所有人都",
    "不言而喻",
]

# 元叙事（编剧旁白式）
META_NARRATIVE_PATTERNS = [
    (r"核心动机",     "元叙事"),
    (r"信息落差",     "元叙事"),
    (r"叙事节奏",     "元叙事"),
    (r"情节推进",     "元叙事"),
    (r"人物弧线",     "元叙事"),
    (r"显然[，,。]",  "作者说教"),  # "显然，" 通常是说教；"显然是" 可能合法
    (r"毫无疑问",     "作者说教"),
]

# 报告式语言
REPORT_STYLE_PATTERNS = [
    r"分析了.*?(?:情况|局势|形势)",
    r"从.*?(?:角度|层面)(?:来|而言|看)",
    r"综合考虑",
]

# 集体反应套话
COLLECTIVE_PATTERNS = [
    r"(?:在场|全场)(?:之人|人|众人)(?:皆|都|全)",
    r"(?:众人|所有人)(?:齐声|异口同声)",
    r"一时间.*?(?:哗然|震动|沸腾)",
]


# ── PostWriteValidator ────────────────────────────────────────────────────────

class PostWriteValidator:
    def __init__(self, custom_forbidden_words: list[str] | None = None):
        self.custom_forbidden_words = custom_forbidden_words or []

    def validate(self, content: str, target_words: int) -> ValidationResult:
        issues: list[ValidationIssue] = []
        word_count = len(content)  # 中文用字符数近似

        # ── 规则 1：AI 标记词密度 ──────────────────────────────────────────────
        for word in AI_MARKER_WORDS:
            count = len(re.findall(word, content))
            if count == 0:
                continue
            per_3000 = (count / word_count) * 3000 if word_count > 0 else 0
            if per_3000 > 1:
                issues.append(ValidationIssue(
                    rule="AI_MARKER_DENSITY",
                    severity="warning",
                    description=f"「{word}」出现 {count} 次（每3000字 {per_3000:.1f} 次，上限 1 次）",
                    excerpt=word,
                ))

        # ── 规则 2：禁止句式 ────────────────────────────────────────────────────
        for phrase in FORBIDDEN_PHRASES:
            if phrase in content:
                issues.append(ValidationIssue(
                    rule="FORBIDDEN_PHRASE",
                    severity="error",
                    description=f"禁止句式：「{phrase}」",
                    excerpt=phrase,
                ))

        # ── 规则 3：元叙事 ─────────────────────────────────────────────────────
        for pattern, label in META_NARRATIVE_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(ValidationIssue(
                    rule="META_NARRATIVE",
                    severity="warning",
                    description=f"{label}：「{matches[0]}」（共 {len(matches)} 处）",
                    excerpt=matches[0],
                ))

        # ── 规则 4：报告式语言 ─────────────────────────────────────────────────
        for pattern in REPORT_STYLE_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(ValidationIssue(
                    rule="REPORT_STYLE",
                    severity="warning",
                    description=f"报告式语言：「{matches[0]}」",
                    excerpt=matches[0],
                ))

        # ── 规则 5：集体反应套话 ───────────────────────────────────────────────
        for pattern in COLLECTIVE_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(ValidationIssue(
                    rule="COLLECTIVE_REACTION",
                    severity="warning",
                    description=f"集体反应套话：「{matches[0]}」",
                    excerpt=matches[0],
                ))

        # ── 规则 6：连续"了"字 ───────────────────────────────────────────────
        sentences = re.split(r"[。！？!?]", content)
        max_consecutive_le = 0
        consecutive = 0
        for s in sentences:
            if "了" in s:
                consecutive += 1
                max_consecutive_le = max(max_consecutive_le, consecutive)
            else:
                consecutive = 0
        if max_consecutive_le >= 6:
            issues.append(ValidationIssue(
                rule="CONSECUTIVE_LE",
                severity="warning",
                description=f"连续 {max_consecutive_le} 句含「了」字（上限 6 句）",
            ))

        # ── 规则 7：段落过长 ───────────────────────────────────────────────────
        paragraphs = [p for p in re.split(r"\n{2,}", content) if p.strip()]
        long_paragraphs = [p for p in paragraphs if len(p) > 300]
        if len(long_paragraphs) >= 2:
            issues.append(ValidationIssue(
                rule="LONG_PARAGRAPH",
                severity="warning",
                description=f"{len(long_paragraphs)} 个段落超过 300 字",
            ))

        # ── 规则 8：字数偏差 ───────────────────────────────────────────────────
        if target_words > 0:
            deviation = abs(word_count - target_words) / target_words
            if deviation > 0.2:
                issues.append(ValidationIssue(
                    rule="WORD_COUNT_DEVIATION",
                    severity="warning",
                    description=f"实际 {word_count} 字，目标 {target_words} 字，偏差 {deviation*100:.0f}%（上限 20%）",
                ))

        # ── 规则 9：自定义禁止词 ───────────────────────────────────────────────
        for word in self.custom_forbidden_words:
            count = len(re.findall(re.escape(word), content))
            if count > 1:
                issues.append(ValidationIssue(
                    rule="CUSTOM_FORBIDDEN_WORD",
                    severity="warning",
                    description=f"自定义禁止词「{word}」出现 {count} 次（每章上限 1 次）",
                    excerpt=word,
                ))

        has_error = any(i.severity == "error" for i in issues)
        return ValidationResult(passed=not has_error, issues=issues, word_count=word_count)

    def summarize(self, results: list[ValidationResult]) -> dict[str, int]:
        """统计所有章节的规则触发频率（用于 analytics）"""
        counts: dict[str, int] = {}
        for r in results:
            for issue in r.issues:
                counts[issue.rule] = counts.get(issue.rule, 0) + 1
        return counts
