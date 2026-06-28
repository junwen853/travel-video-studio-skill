#!/usr/bin/env python3
"""Audience-facing caption and narration text policy helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("editor_report_to_user", re.compile(r"(本次|这次).{0,12}(剪辑|剪完|剪好|做完|交付|导出|渲染|完成|修复|去掉|删掉|删除|优化)")),
    ("repair_report", re.compile(r"(已|已经|成功).{0,12}(修复|去掉|删掉|删除|解决|优化|完成|替换|导出|渲染)")),
    ("internal_workflow", re.compile(r"(交付包|时间线|蓝图|审计|质检|回归检查|回归测试|质量门|最终QA|QA|V\d{1,3}|baseline)", re.IGNORECASE)),
    ("tooling_terms", re.compile(r"(DaVinci|Resolve|Final Cut|Premiere|FFmpeg|Codex|skill|workflow|pipeline|A1|A2|A3|BGM-only|SRT|TXT)", re.IGNORECASE)),
    ("asset_or_source_report", re.compile(r"(源素材|素材库|素材文件|素材已经|素材里|竖屏修复|横竖屏|orientation|portrait regression)", re.IGNORECASE)),
    ("direct_user_address", re.compile(r"(给你|帮你|你要的|按你的要求|根据你的要求|我已经|我们已经)")),
]


def normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def audience_text_violations(text: Any) -> list[dict[str, str]]:
    normalized = normalize_text(text)
    violations: list[dict[str, str]] = []
    if not normalized:
        return violations
    for rule, pattern in FORBIDDEN_PATTERNS:
        match = pattern.search(normalized)
        if match:
            violations.append({"rule": rule, "match": match.group(0), "text": normalized[:240]})
    return violations


def is_audience_safe_text(text: Any) -> bool:
    return not audience_text_violations(text)


def clean_audience_text(text: Any) -> str:
    """Normalize a generated audience line without adding editor-facing language."""
    normalized = normalize_text(text)
    normalized = re.sub(r"^(旁白|字幕|画面|提示|说明)[:：]\s*", "", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def audience_safe_lines(lines: list[str], fallback: str = "这段旅程继续往前，画面会把答案慢慢说出来。") -> list[str]:
    safe: list[str] = []
    for line in lines:
        cleaned = clean_audience_text(line)
        if cleaned and is_audience_safe_text(cleaned):
            safe.append(cleaned)
    return safe or [fallback]


def srt_blocks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    blocks: list[dict[str, Any]] = []
    for raw in re.split(r"\n\s*\n", path.read_text(encoding="utf-8", errors="ignore").strip()):
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            continue
        body = [line for line in lines if "-->" not in line and not line.isdigit()]
        text = " ".join(body).strip()
        if text:
            blocks.append({"text": text, "raw": raw})
    return blocks


def text_file_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        text = line.strip()
        if text:
            rows.append({"line": index, "text": text})
    return rows


def file_violations(path: Path) -> list[dict[str, Any]]:
    rows = srt_blocks(path) if path.suffix.lower() in {".srt", ".vtt"} else text_file_lines(path)
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        text = row.get("text") or ""
        for violation in audience_text_violations(text):
            out.append({"path": str(path), "index": row.get("line") or index, **violation})
    return out
