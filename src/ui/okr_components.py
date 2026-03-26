"""
OKR Components for Dashboard.

Renders OKR progress indicators that can be embedded in different tabs.
"""

import json
import os
import streamlit as st
from typing import Optional


def load_okrs() -> list:
    """Load OKRs from JSON config."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "okrs.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _progress_color(current: float, target: float, direction: str) -> str:
    """Get color based on progress toward target."""
    if direction == "decrease":
        ratio = target / max(current, 0.1)  # Lower is better
    elif direction == "target_range":
        return "#22C55E"  # Handled separately
    else:
        ratio = current / max(target, 0.1)  # Higher is better
    
    if ratio >= 0.9:
        return "#22C55E"  # Green
    elif ratio >= 0.6:
        return "#F59E0B"  # Amber
    else:
        return "#EF4444"  # Red


def _progress_pct(current: float, target: float, direction: str, range_min: float = 0, range_max: float = 0) -> float:
    """Calculate progress percentage."""
    if direction == "decrease":
        if current <= target:
            return 100.0
        # How far from start to target
        return max(0, min(100, (1 - (current - target) / max(current, 1)) * 100))
    elif direction == "target_range":
        if range_min <= current <= range_max:
            return 100.0
        if current < range_min:
            return max(0, (current / range_min) * 100)
        return max(0, (range_max / current) * 100)
    else:
        return min(100, (current / max(target, 0.1)) * 100)


def render_okr_card(kr: dict, current_value: float):
    """Render a single KR progress card."""
    target = kr["target"]
    direction = kr["direction"]
    unit = kr["unit"]
    range_min = kr.get("range_min", 0)
    range_max = kr.get("range_max", 0)
    
    pct = _progress_pct(current_value, target, direction, range_min, range_max)
    color = _progress_color(current_value, target, direction)
    
    if direction == "target_range":
        target_label = f"{range_min}-{range_max}{unit}"
        in_range = range_min <= current_value <= range_max
        color = "#22C55E" if in_range else "#F59E0B"
    elif direction == "decrease":
        target_label = f"≤ {target}{unit}"
    else:
        target_label = f"≥ {target}{unit}"
    
    status_icon = "✅" if pct >= 100 else "🔄" if pct >= 60 else "⚠️"
    
    st.markdown(
        f"""
        <div style="
            background: white;
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: 0.8rem 1rem;
            margin-bottom: 0.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-size: 0.8rem; color: #6B7280; flex: 1;">
                    {status_icon} {kr['description']}
                </div>
                <div style="font-size: 0.9rem; font-weight: 600; color: {color}; white-space: nowrap; margin-left: 1rem;">
                    {current_value:.0f}{unit} / {target_label}
                </div>
            </div>
            <div style="
                background: #E5E7EB;
                border-radius: 4px;
                height: 6px;
                margin-top: 0.4rem;
                overflow: hidden;
            ">
                <div style="
                    background: {color};
                    height: 100%;
                    width: {min(pct, 100):.0f}%;
                    border-radius: 4px;
                    transition: width 0.3s;
                "></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_okrs_for_tab(tab_name: str, metrics: dict):
    """
    Render OKR section for a specific tab.
    
    Args:
        tab_name: Tab identifier (cycle, project, report).
        metrics: Dict with metric_id -> current_value.
    """
    okrs = load_okrs()
    if not okrs:
        return
    
    # Collect KRs for this tab
    relevant_krs = []
    for okr in okrs:
        for kr in okr.get("key_results", []):
            if kr.get("tab") == tab_name and kr["metric"] in metrics:
                relevant_krs.append((okr["objective"], kr))
    
    if not relevant_krs:
        return
    
    with st.expander("🎯 OKRs", expanded=True):
        current_obj = None
        for objective, kr in relevant_krs:
            if objective != current_obj:
                current_obj = objective
                st.caption(f"**{objective}**")
            render_okr_card(kr, metrics[kr["metric"]])
