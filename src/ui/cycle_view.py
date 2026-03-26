"""
Cycle View - Visão do Ciclo Completo (Produto + Engenharia).

Mostra o fluxo completo de uma issue passando pelos dois quadros:
Produto (discovery/definição) → Engenharia (desenvolvimento/entrega).
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict, Optional
from collections import defaultdict, OrderedDict
from src.models.data_models import Issue, get_tshirt_size_label


# Fases do ciclo completo - ordem do fluxo
PRODUCT_PHASES = [
    "Oportunidades",
    "Contexto e Viabilidade",
    "Investigação",
    "Definição da Solução",
    "Aguardando Priorização",
]

HANDOFF_PHASES = [
    "Backlog Engenharia",
    "Priorizado Engenharia",
]

ENGINEERING_PHASES = [
    "Pronto para Desenvolver",
    "Em Desenvolvimento",
    "Validação",
    "Para Homologar",
    "Implantação",
    "Itens Concluídos",
]

ALL_PHASES = PRODUCT_PHASES + HANDOFF_PHASES + ENGINEERING_PHASES

# Mapeamento de status do Jira para fases do ciclo
# Será preenchido dinamicamente com os status reais das issues
PHASE_COLORS = {
    "Produto": "#8B5CF6",       # Purple
    "Handoff": "#F59E0B",       # Amber
    "Engenharia": "#3B82F6",    # Blue
    "Concluído": "#22C55E",     # Green
}


def _classify_phase(status: str) -> str:
    """Classify a status into Produto, Handoff, Engenharia or Concluído."""
    status_lower = status.lower().strip()
    
    for phase in PRODUCT_PHASES:
        if phase.lower() in status_lower or status_lower in phase.lower():
            return "Produto"
    
    for phase in HANDOFF_PHASES:
        if phase.lower() in status_lower or status_lower in phase.lower():
            return "Handoff"
    
    if "concluíd" in status_lower or "itens concluídos" in status_lower:
        return "Concluído"
    
    for phase in ENGINEERING_PHASES:
        if phase.lower() in status_lower or status_lower in phase.lower():
            return "Engenharia"
    
    # Default: try to match by keywords
    product_keywords = ["oportunidade", "contexto", "viabilidade", "investigação", "definição", "discovery"]
    eng_keywords = ["desenvolv", "validação", "homolog", "implantação", "deploy", "pronto para"]
    handoff_keywords = ["backlog eng", "priorizado eng"]
    
    for kw in handoff_keywords:
        if kw in status_lower:
            return "Handoff"
    for kw in product_keywords:
        if kw in status_lower:
            return "Produto"
    for kw in eng_keywords:
        if kw in status_lower:
            return "Engenharia"
    
    return "Engenharia"  # Default


def _get_phase_order(status: str) -> int:
    """Get the order index for a status in the full cycle."""
    status_lower = status.lower().strip()
    
    for i, phase in enumerate(ALL_PHASES):
        if phase.lower() in status_lower or status_lower in phase.lower():
            return i
    
    # Unknown status - put at end
    return len(ALL_PHASES)


def render_cycle_funnel(issues: List[Issue]):
    """Render a funnel chart showing issues in each phase of the cycle."""
    if not issues:
        st.info("Nenhuma issue encontrada.")
        return
    
    # Count issues per status
    status_counts = defaultdict(int)
    for issue in issues:
        status_counts[issue.status] += 1
    
    # Sort by phase order
    sorted_statuses = sorted(status_counts.keys(), key=_get_phase_order)
    
    # Build data
    labels = []
    values = []
    colors = []
    
    for status in sorted_statuses:
        phase = _classify_phase(status)
        labels.append(status)
        values.append(status_counts[status])
        colors.append(PHASE_COLORS.get(phase, "#6B7280"))
    
    fig = go.Figure(go.Funnel(
        y=labels,
        x=values,
        marker=dict(color=colors),
        textinfo="value+percent initial",
        textposition="inside",
    ))
    
    fig.update_layout(
        title="Funil do Ciclo Completo",
        font_family="Inter, sans-serif",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(400, len(labels) * 45),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    
    st.plotly_chart(fig, use_container_width=True, key="cycle_funnel")


def render_cycle_board(issues: List[Issue]):
    """Render a kanban-style board showing the full cycle."""
    if not issues:
        return
    
    # Group issues by status
    status_groups = defaultdict(list)
    for issue in issues:
        status_groups[issue.status].append(issue)
    
    # Sort statuses by phase order
    sorted_statuses = sorted(status_groups.keys(), key=_get_phase_order)
    
    # Group by phase category
    phase_groups = OrderedDict()
    phase_groups["🟣 Produto"] = []
    phase_groups["🟡 Handoff"] = []
    phase_groups["🔵 Engenharia"] = []
    phase_groups["🟢 Concluído"] = []
    
    phase_map = {
        "Produto": "🟣 Produto",
        "Handoff": "🟡 Handoff",
        "Engenharia": "🔵 Engenharia",
        "Concluído": "🟢 Concluído",
    }
    
    for status in sorted_statuses:
        phase = _classify_phase(status)
        group_key = phase_map.get(phase, "🔵 Engenharia")
        phase_groups[group_key].append((status, status_groups[status]))
    
    # Render phase summary cards
    cols = st.columns(4)
    phase_totals = {}
    
    for i, (phase_name, statuses) in enumerate(phase_groups.items()):
        total = sum(len(issues_list) for _, issues_list in statuses)
        phase_totals[phase_name] = total
        color = list(PHASE_COLORS.values())[i]
        
        with cols[i]:
            st.markdown(
                f"""
                <div style="
                    background: white;
                    border-left: 4px solid {color};
                    border-radius: 8px;
                    padding: 1rem;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    text-align: center;
                ">
                    <div style="font-size: 0.85rem; color: #6B7280;">{phase_name}</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: {color};">{total}</div>
                    <div style="font-size: 0.75rem; color: #9CA3AF;">issues</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    
    st.divider()
    
    # Render detailed status breakdown
    for phase_name, statuses in phase_groups.items():
        if not statuses:
            continue
        
        total = phase_totals[phase_name]
        with st.expander(f"{phase_name} ({total} issues)", expanded=False):
            for status_name, issues_list in statuses:
                st.markdown(f"**{status_name}** ({len(issues_list)})")
                
                issue_data = []
                for issue in issues_list:
                    issue_data.append({
                        "Chave": issue.key,
                        "Resumo": issue.summary[:60] + "..." if len(issue.summary) > 60 else issue.summary,
                        "Tipo": issue.issue_type,
                        "Responsável": issue.assignee_name or "Sem responsável",
                        "Tamanho": get_tshirt_size_label(issue.t_shirt_size),
                        "Criado": issue.created_date.strftime("%d/%m/%Y %H:%M") if issue.created_date else "-",
                    })
                
                if issue_data:
                    st.dataframe(issue_data, use_container_width=True, hide_index=True)
                
                st.markdown("---")


def render_cycle_metrics(issues: List[Issue]):
    """Render cycle time metrics between phases."""
    if not issues:
        return
    
    done_issues = [i for i in issues if _classify_phase(i.status) == "Concluído"]
    in_progress = [i for i in issues if _classify_phase(i.status) == "Engenharia"]
    in_product = [i for i in issues if _classify_phase(i.status) == "Produto"]
    in_handoff = [i for i in issues if _classify_phase(i.status) == "Handoff"]
    
    total = len(issues)
    
    # WIP metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total de Issues", total)
    with col2:
        st.metric("Em Produto", len(in_product),
                  help="Issues na fase de discovery/definição")
    with col3:
        st.metric("Em Handoff", len(in_handoff),
                  help="Issues aguardando ou priorizadas para engenharia")
    with col4:
        st.metric("Em Engenharia", len(in_progress),
                  help="Issues em desenvolvimento/validação")
    with col5:
        st.metric("Concluídas", len(done_issues),
                  help="Issues entregues")
    
    # Completion rate
    if total > 0:
        completion_pct = (len(done_issues) / total) * 100
        product_pct = (len(in_product) / total) * 100
        eng_pct = (len(in_progress) / total) * 100
        
        # Progress bar
        st.markdown("**Distribuição do Ciclo**")
        
        fig = go.Figure(go.Bar(
            x=[product_pct, (len(in_handoff) / total) * 100, eng_pct, completion_pct],
            y=["Ciclo"],
            orientation="h",
            marker_color=[
                PHASE_COLORS["Produto"],
                PHASE_COLORS["Handoff"],
                PHASE_COLORS["Engenharia"],
                PHASE_COLORS["Concluído"],
            ],
            text=[
                f"Produto {product_pct:.0f}%",
                f"Handoff {(len(in_handoff)/total)*100:.0f}%",
                f"Eng. {eng_pct:.0f}%",
                f"Done {completion_pct:.0f}%",
            ],
            textposition="inside",
        ))
        
        fig.update_layout(
            barmode="stack",
            height=80,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(visible=False, range=[0, 100]),
            yaxis=dict(visible=False),
        )
        
        st.plotly_chart(fig, use_container_width=True, key="cycle_distribution_bar")
    
    # Lead time for done issues
    if done_issues:
        lead_times = []
        for issue in done_issues:
            if issue.resolution_date and issue.created_date:
                delta = (issue.resolution_date - issue.created_date).days
                if delta >= 0:
                    lead_times.append(delta)
        
        if lead_times:
            avg_lt = sum(lead_times) / len(lead_times)
            min_lt = min(lead_times)
            max_lt = max(lead_times)
            
            st.markdown("**Lead Time (Ciclo Completo - Criação até Conclusão)**")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Médio", f"{avg_lt:.0f} dias")
            with c2:
                st.metric("Mínimo", f"{min_lt} dias")
            with c3:
                st.metric("Máximo", f"{max_lt} dias")


def render_cycle_burndown(issues: List[Issue]):
    """Render burndown chart based on issue creation and resolution dates."""
    from datetime import timedelta
    
    if not issues:
        return
    
    st.markdown("### 📉 Burndown do Ciclo")
    
    # Get date boundaries
    dates_created = [i.created_date.date() for i in issues if i.created_date]
    dates_resolved = [i.resolution_date.date() for i in issues if i.resolution_date]
    
    if not dates_created:
        st.info("Sem dados de datas para gerar o burndown.")
        return
    
    min_date = min(dates_created)
    max_date = max(dates_created + dates_resolved) if dates_resolved else max(dates_created)
    
    # Extend to today if max_date is in the past
    from datetime import date as date_type
    today = date_type.today()
    if max_date < today:
        max_date = today
    
    # Build daily cumulative data
    total_issues = len(issues)
    current_date = min_date
    
    chart_dates = []
    remaining = []
    created_cumulative = []
    resolved_cumulative = []
    
    cum_created = 0
    cum_resolved = 0
    
    while current_date <= max_date:
        # Count issues created on this date
        created_today = sum(1 for d in dates_created if d <= current_date)
        resolved_today = sum(1 for d in dates_resolved if d <= current_date)
        
        chart_dates.append(current_date)
        created_cumulative.append(created_today)
        resolved_cumulative.append(resolved_today)
        remaining.append(created_today - resolved_today)
        
        current_date += timedelta(days=1)
    
    # Ideal burndown line (linear from total to 0)
    if chart_dates:
        total_at_start = created_cumulative[-1]  # Total issues created
        ideal_line = []
        num_days = len(chart_dates)
        for i in range(num_days):
            ideal_val = total_at_start - (total_at_start * i / max(num_days - 1, 1))
            ideal_line.append(ideal_val)
    
    # Create chart
    fig = go.Figure()
    
    # Remaining issues (actual burndown)
    fig.add_trace(go.Scatter(
        x=chart_dates,
        y=remaining,
        mode="lines+markers",
        name="Restantes (aberto)",
        line=dict(color="#F37021", width=3),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor="rgba(243, 112, 33, 0.1)",
    ))
    
    # Ideal burndown
    fig.add_trace(go.Scatter(
        x=chart_dates,
        y=ideal_line,
        mode="lines",
        name="Ideal",
        line=dict(color="#9CA3AF", width=2, dash="dash"),
    ))
    
    # Resolved cumulative
    fig.add_trace(go.Scatter(
        x=chart_dates,
        y=resolved_cumulative,
        mode="lines",
        name="Concluídas (acumulado)",
        line=dict(color="#22C55E", width=2),
    ))
    
    fig.update_layout(
        font_family="Inter, sans-serif",
        font_color="#6B7280",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=20, b=20),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        xaxis=dict(gridcolor="#E5E7EB", gridwidth=0.5),
        yaxis=dict(gridcolor="#E5E7EB", gridwidth=0.5, title="Issues"),
    )
    
    st.plotly_chart(fig, use_container_width=True, key="cycle_burndown")


def render_cycle_flow_balance(issues: List[Issue]):
    """Render flow balance showing entries vs exits by type."""
    if not issues:
        return
    
    st.markdown("### 📉 Balanço de Vazão por Tipo")
    
    flow_map = defaultdict(lambda: {"entradas": 0, "saidas": 0})
    
    for issue in issues:
        tipo = issue.issue_type or "Outros"
        flow_map[tipo]["entradas"] += 1
        if _classify_phase(issue.status) == "Concluído":
            flow_map[tipo]["saidas"] += 1
    
    data = []
    for tipo, values in sorted(flow_map.items(), key=lambda x: x[1]["entradas"], reverse=True):
        entradas = values["entradas"]
        saidas = values["saidas"]
        saldo = saidas - entradas
        eficiencia = (saidas / entradas * 100) if entradas > 0 else 0
        
        data.append({
            "Tipo": tipo,
            "Entradas": entradas,
            "Saídas (Concluídas)": saidas,
            "Saldo": saldo,
            "Vazão": "📈 Positiva" if saldo >= 0 else "📉 Negativa",
            "Eficiência": f"{eficiencia:.1f}%"
        })
    
    if data:
        st.dataframe(data, use_container_width=True, hide_index=True)


def render_cycle_view_tab(issues: List[Issue]):
    """
    Main render function for the Cycle View tab.
    
    Args:
        issues: All issues from the project (both boards).
    """
    st.subheader("🔄 Visão do Ciclo Completo")
    st.caption("Acompanhamento unificado do fluxo Produto → Engenharia")
    
    if not issues:
        st.info("Selecione um projeto e aplique os filtros para visualizar o ciclo completo.")
        return
    
    # Calculate OKR metrics
    total = len(issues)
    done_issues = [i for i in issues if _classify_phase(i.status) == "Concluído"]
    in_handoff = [i for i in issues if _classify_phase(i.status) == "Handoff"]
    
    completion_rate = (len(done_issues) / total * 100) if total > 0 else 0
    handoff_rate = (len(in_handoff) / total * 100) if total > 0 else 0
    
    lead_times = []
    for issue in done_issues:
        if issue.resolution_date and issue.created_date:
            delta = (issue.resolution_date - issue.created_date).days
            if delta >= 0:
                lead_times.append(delta)
    lead_time_avg = sum(lead_times) / len(lead_times) if lead_times else 0
    
    # Render OKRs
    from src.ui.okr_components import render_okrs_for_tab
    render_okrs_for_tab("cycle", {
        "lead_time_avg": lead_time_avg,
        "completion_rate": completion_rate,
        "handoff_rate": handoff_rate,
    })
    
    # Metrics summary
    render_cycle_metrics(issues)
    
    st.divider()
    
    # Funnel
    render_cycle_funnel(issues)
    
    st.divider()
    
    # Burndown
    render_cycle_burndown(issues)
    
    st.divider()
    
    # Kanban board view
    st.markdown("### 📋 Detalhamento por Fase")
    render_cycle_board(issues)
    
    st.divider()
    
    # Flow balance
    render_cycle_flow_balance(issues)
