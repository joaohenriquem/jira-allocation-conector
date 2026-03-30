"""
Legacy Dashboard View - Funcionalidades do dashboard HTML v17 adaptadas para Streamlit.

Inclui:
- KPIs: Criadas, Média Entradas, Vazão Média Saídas, Concluídas, Backlog Acumulado
- Balanço de Vazão (Net Flow) por Tipo
- Capacity do Time vs Backlog
- Top Responsáveis e Relatores
- Demandas por Tipo e Status
- Evolução Mensal
- Backlog Detalhado com Export
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from src.models.data_models import Issue, Project
from src.connector.jira_connector import JiraConnector
from src.cache.cache_manager import CacheManager


# Cores por tipo de issue (similar ao HTML)
TIPO_COLORS = {
    'Bug': '#EF5350',
    'Task': '#42A5F5', 
    'Sub-task': '#90CAF9',
    'Story': '#66BB6A',
    'Improvement': '#FFCA28',
    'Epic': '#7E57C2',
    'Outros': '#78909C'
}


def render_legacy_view(
    connector: Optional[JiraConnector],
    config: Any,
    connection_status: Any
):
    """Renderiza a aba Legado com funcionalidades do dashboard HTML."""
    # Import inside function to avoid circular imports
    from src.ui.components import (
        render_loading_skeleton,
        render_loading_card_skeleton,
        render_loading_selector_skeleton,
    )
    
    st.header("📋 Dashboard Legado")
    st.markdown("Visualização de métricas no formato do dashboard HTML original.")
    
    st.divider()
    
    if not connection_status.connected:
        st.warning("⚠️ Não conectado ao Jira. Conecte-se na aba Configuração.")
        return
    
    if not connector:
        st.error("❌ Conector Jira não disponível.")
        return
    
    # Carregar todos os projetos
    cache_key = "legacy_all_projects"
    all_projects = CacheManager.get_cached_data(cache_key)
    
    if all_projects is None:
        # Show loading skeleton while loading projects
        loading_placeholder = st.empty()
        with loading_placeholder.container():
            render_loading_selector_skeleton("Carregando projetos do Jira...")
            render_loading_card_skeleton(5)
            render_loading_skeleton(4, "100px", "Preparando dashboard...")
        
        try:
            all_projects = connector.get_all_projects()
            CacheManager.set_cached_data(cache_key, all_projects, 3600)
        except Exception as e:
            loading_placeholder.empty()
            st.error(f"Erro ao carregar projetos: {e}")
            return
        
        loading_placeholder.empty()
    
    # Filtros
    _render_legacy_filters(all_projects)
    
    # Verificar se há projetos selecionados
    projects = st.session_state.get('legacy_projects', [])
    if not projects:
        st.info("👆 Selecione um ou mais projetos nos filtros acima para visualizar as métricas.")
        return
    
    # Carregar issues com base nos filtros
    issues = _load_filtered_issues(connector, config)
    
    if not issues:
        st.info("Nenhuma issue encontrada com os filtros selecionados.")
        return
    
    # Renderizar seções
    _render_kpis(issues)
    st.divider()
    _render_net_flow(issues)
    st.divider()
    _render_capacity_section(issues, config)
    st.divider()
    _render_rankings(issues)
    st.divider()
    _render_distribution_tables(issues)
    st.divider()
    _render_monthly_charts(issues)
    st.divider()
    _render_backlog_table(issues)


def _render_legacy_filters(projects: List[Project]):
    """Renderiza os filtros da aba legado."""
    
    with st.expander("🔍 Filtros", expanded=True):
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
        
        with col1:
            project_options = {p.key: f"{p.key} - {p.name}" for p in projects}
            st.multiselect(
                "Projetos",
                options=list(project_options.keys()),
                format_func=lambda x: project_options.get(x, x),
                key="legacy_projects",
                help="Selecione os projetos",
                placeholder="Selecione os projetos"
            )
        
        with col2:
            # Filtro de tipo - múltipla seleção
            tipo_options = ["Bug", "Task", "Sub-task", "Story", "Improvement", "Epic"]
            st.multiselect(
                "Tipo de Item",
                options=tipo_options,
                key="legacy_tipos",
                help="Selecione os tipos de item (vazio = todos)",
                placeholder="Todos os tipos"
            )
        
        with col3:
            # Filtro de status
            status_options = ["", "To Do", "In Progress", "Done", "Cancelled"]
            st.selectbox(
                "Status",
                options=status_options,
                format_func=lambda x: "Todos" if x == "" else x,
                key="legacy_status"
            )
        
        with col4:
            # Filtro de ano
            current_year = datetime.now().year
            year_options = [""] + list(range(current_year, current_year - 5, -1))
            st.selectbox(
                "Ano",
                options=year_options,
                format_func=lambda x: "Todos" if x == "" else str(x),
                key="legacy_year"
            )
        
        with col5:
            # Filtro de mês
            month_options = [""] + list(range(1, 13))
            selected_year = st.session_state.get("legacy_year", "")
            st.selectbox(
                "Mês",
                options=month_options,
                format_func=lambda x: "Todos" if x == "" else f"{x:02d}",
                key="legacy_month",
                disabled=selected_year == ""
            )


def _load_filtered_issues(connector: JiraConnector, config: Any) -> List[Issue]:
    """Carrega issues filtradas do Jira."""
    from src.ui.components import (
        render_loading_skeleton,
        render_loading_card_skeleton,
    )
    
    projects = st.session_state.get('legacy_projects', [])
    if not projects:
        return []
    
    tipos = st.session_state.get('legacy_tipos', [])
    status = st.session_state.get('legacy_status', "")
    year = st.session_state.get('legacy_year', "")
    month = st.session_state.get('legacy_month', "")
    
    # Construir JQL
    jql_parts = [f"project IN ({', '.join(projects)})"]
    
    if tipos:
        tipos_str = ', '.join(f'"{t}"' for t in tipos)
        jql_parts.append(f'issuetype IN ({tipos_str})')
    
    if status:
        if status == "Done":
            jql_parts.append('status IN ("Done", "Concluído", "Resolved")')
        elif status == "Cancelled":
            jql_parts.append('status IN ("Cancelled", "Cancelado")')
        else:
            jql_parts.append(f'status = "{status}"')
    
    if year:
        if month:
            # Primeiro e último dia do mês
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            jql_parts.append(f'created >= "{start_date}" AND created < "{end_date}"')
        else:
            jql_parts.append(f'created >= "{year}-01-01" AND created < "{year + 1}-01-01"')
    
    jql = " AND ".join(jql_parts)
    cache_key = f"legacy_issues_{hash(jql)}"
    
    cached = CacheManager.get_cached_data(cache_key)
    if cached:
        return cached
    
    # Show loading skeleton while loading issues
    loading_placeholder = st.empty()
    with loading_placeholder.container():
        render_loading_card_skeleton(5)
        render_loading_skeleton(4, "80px", f"Carregando issues de {len(projects)} projeto(s)...")
    
    try:
        fields = [
            "summary", "status", "assignee", "issuetype", "created",
            "resolutiondate", "reporter", "labels", "components",
            "customfield_10016", "statuscategorychangedate"
        ]
        result = connector.get_issues(jql, fields)
        CacheManager.set_cached_data(cache_key, result.issues, 3600)
        loading_placeholder.empty()
        return result.issues
    except Exception as e:
        loading_placeholder.empty()
        st.warning(f"Erro ao carregar issues: {e}")
        return []


def _render_kpis(issues: List[Issue]):
    """Renderiza os KPIs principais."""
    
    total = len(issues)
    done_issues = [i for i in issues if i.status_category == "Done"]
    concluidas = len(done_issues)
    
    # Backlog = issues não concluídas
    backlog = [i for i in issues if i.status_category != "Done"]
    backlog_count = len(backlog)
    
    # Calcular médias
    year = st.session_state.get('legacy_year', "")
    month = st.session_state.get('legacy_month', "")
    
    if year and month:
        # Média por dia útil (assumindo 17 dias úteis/mês)
        dias_uteis = 17
        media_entradas = total / dias_uteis if dias_uteis > 0 else 0
        media_saidas = concluidas / dias_uteis if dias_uteis > 0 else 0
        label_media = "/dia útil"
    else:
        # Média por mês
        meses = set()
        for issue in issues:
            if issue.created_date:
                meses.add((issue.created_date.year, issue.created_date.month))
        num_meses = len(meses) if meses else 1
        media_entradas = total / num_meses
        media_saidas = concluidas / num_meses
        label_media = "/mês"
    
    # Renderizar KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "📥 Criadas no Período",
            total,
            help="Total de issues criadas no período selecionado"
        )
    
    with col2:
        st.metric(
            "📊 Média Entradas",
            f"{media_entradas:.1f}{label_media}",
            help="Média de novas issues por período"
        )
    
    with col3:
        st.metric(
            "📈 Vazão Média",
            f"{media_saidas:.1f}{label_media}",
            help="Média de issues concluídas por período"
        )
    
    with col4:
        st.metric(
            "✅ Concluídas",
            concluidas,
            help="Total de issues concluídas no período"
        )
    
    with col5:
        st.metric(
            "📦 Backlog",
            backlog_count,
            help="Issues pendentes (não concluídas)"
        )


def _render_net_flow(issues: List[Issue]):
    """Renderiza o Balanço de Vazão (Net Flow) por Tipo."""
    
    st.subheader("📉 Balanço de Vazão por Tipo (Entradas vs. Saídas)")
    
    # Agrupar por tipo
    flow_map: Dict[str, Dict[str, int]] = defaultdict(lambda: {"entradas": 0, "saidas": 0})
    
    for issue in issues:
        tipo = issue.issue_type or "Outros"
        flow_map[tipo]["entradas"] += 1
        if issue.status_category == "Done":
            flow_map[tipo]["saidas"] += 1
    
    # Criar DataFrame
    data = []
    for tipo, values in sorted(flow_map.items(), key=lambda x: x[1]["entradas"], reverse=True):
        entradas = values["entradas"]
        saidas = values["saidas"]
        saldo = saidas - entradas
        eficiencia = (saidas / entradas * 100) if entradas > 0 else 0
        
        data.append({
            "Tipo": tipo,
            "Novas (Entradas)": entradas,
            "Entregues (Saídas)": saidas,
            "Saldo (Net Flow)": saldo,
            "Status Vazão": "📈 Positiva" if saldo >= 0 else "📉 Negativa",
            "% Eficiência": f"{eficiencia:.1f}%"
        })
    
    if data:
        df = pd.DataFrame(data)
        
        # Estilizar a tabela
        def style_saldo(val):
            if isinstance(val, (int, float)):
                color = '#2E7D32' if val >= 0 else '#C62828'
                return f'color: {color}; font-weight: bold'
            return ''
        
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={
                "Tipo": st.column_config.TextColumn("Tipo de Item"),
                "Novas (Entradas)": st.column_config.NumberColumn("Novas (Entradas)"),
                "Entregues (Saídas)": st.column_config.NumberColumn("Entregues (Saídas)"),
                "Saldo (Net Flow)": st.column_config.NumberColumn("Saldo (Net Flow)"),
                "Status Vazão": st.column_config.TextColumn("Status de Vazão"),
                "% Eficiência": st.column_config.TextColumn("% Eficiência")
            }
        )
    else:
        st.info("Sem dados para exibir")


def _render_capacity_section(issues: List[Issue], config: Any):
    """Renderiza a seção de Capacity do Time."""
    
    st.subheader("⚡ Capacity do Time vs. Backlog")
    
    # Configurações de capacity
    pessoas = 3  # Padrão
    dias_semana = 4  # Efí trabalha 4 dias/semana
    horas_dia = 6  # 6 horas produtivas
    
    # Calcular dias úteis do mês
    year = st.session_state.get('legacy_year', "")
    month = st.session_state.get('legacy_month', "")
    
    if year and month:
        dias_uteis = 17  # Aproximado para um mês
    else:
        dias_uteis = 17
    
    capacity_total = pessoas * dias_uteis
    
    # Info de configuração
    st.caption(f"👥 {pessoas} pessoas | 📅 {dias_semana} dias/semana | ⏰ {horas_dia}h produtivas/dia")
    
    # Calcular carga por tipo
    done_issues = [i for i in issues if i.status_category == "Done"]
    backlog_issues = [i for i in issues if i.status_category != "Done"]
    
    # Throughput médio por tipo (dias para resolver)
    throughput: Dict[str, Dict[str, float]] = defaultdict(lambda: {"sum": 0, "count": 0})
    
    for issue in done_issues:
        if issue.created_date and issue.resolution_date:
            dias = (issue.resolution_date - issue.created_date).days
            if dias >= 0:
                tipo = issue.issue_type or "Outros"
                # Ajustar para dias úteis (4/7)
                throughput[tipo]["sum"] += dias * (4/7)
                throughput[tipo]["count"] += 1
    
    # Calcular carga
    capacity_data: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"res_dias": 0, "res_qtd": 0, "back_dias": 0, "back_qtd": 0}
    )
    
    for issue in done_issues:
        tipo = issue.issue_type or "Outros"
        if issue.created_date and issue.resolution_date:
            dias = (issue.resolution_date - issue.created_date).days * (4/7)
            capacity_data[tipo]["res_dias"] += max(0.1, dias)
            capacity_data[tipo]["res_qtd"] += 1
    
    for issue in backlog_issues:
        tipo = issue.issue_type or "Outros"
        # Estimar dias baseado no throughput médio do tipo
        if throughput[tipo]["count"] > 0:
            media_dias = throughput[tipo]["sum"] / throughput[tipo]["count"]
        else:
            media_dias = 2  # Padrão
        capacity_data[tipo]["back_dias"] += media_dias
        capacity_data[tipo]["back_qtd"] += 1
    
    # Totais
    total_res_dias = sum(v["res_dias"] for v in capacity_data.values())
    total_back_dias = sum(v["back_dias"] for v in capacity_data.values())
    pct_ocupacao = ((total_res_dias + total_back_dias) / capacity_total * 100) if capacity_total > 0 else 0
    
    # KPIs de Capacity
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "📊 Capacidade Líquida",
            f"{capacity_total:.0f} dias",
            help=f"{pessoas} pessoas × {dias_uteis} dias úteis"
        )
    
    with col2:
        st.metric(
            "📦 Carga Backlog",
            f"{total_back_dias:.1f} dias",
            help="Estimativa para resolver todos itens pendentes"
        )
    
    with col3:
        delta_color = "inverse" if pct_ocupacao >= 100 else "normal"
        st.metric(
            "⚡ % Ocupação",
            f"{pct_ocupacao:.1f}%",
            delta="Excedeu!" if pct_ocupacao >= 100 else "OK",
            delta_color=delta_color
        )
    
    # Tabela de detalhamento
    st.write("**Detalhamento por Tipo:**")
    
    table_data = []
    for tipo, values in sorted(capacity_data.items(), key=lambda x: x[1]["res_dias"] + x[1]["back_dias"], reverse=True):
        total_dias = values["res_dias"] + values["back_dias"]
        pct_cap = (total_dias / capacity_total * 100) if capacity_total > 0 else 0
        
        table_data.append({
            "Tipo": tipo,
            "Resolvidos": f"{values['res_qtd']:.0f} ({values['res_dias']:.1f}d)",
            "Backlog": f"{values['back_qtd']:.0f} ({values['back_dias']:.1f}d)",
            "Total (Dias)": f"{total_dias:.1f}",
            "% Cap": f"{pct_cap:.1f}%"
        })
    
    if table_data:
        st.dataframe(pd.DataFrame(table_data), width="stretch", hide_index=True)


def _render_rankings(issues: List[Issue]):
    """Renderiza os rankings de Responsáveis e Relatores."""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👤 Top Responsáveis")
        
        resp_count: Dict[str, int] = defaultdict(int)
        for issue in issues:
            resp = issue.assignee_name or "Sem responsável"
            resp_count[resp] += 1
        
        total = len(issues)
        data = []
        for resp, count in sorted(resp_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            pct = (count / total * 100) if total > 0 else 0
            data.append({"Responsável": resp, "Qtd": count, "%": f"{pct:.1f}%"})
        
        if data:
            st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
        else:
            st.info("Sem dados")
    
    with col2:
        st.subheader("✍️ Top Relatores")
        
        relator_count: Dict[str, int] = defaultdict(int)
        for issue in issues:
            # Reporter está no campo reporter_name ou similar
            relator = getattr(issue, 'reporter_name', None) or "Sem relator"
            relator_count[relator] += 1
        
        total = len(issues)
        data = []
        for relator, count in sorted(relator_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            pct = (count / total * 100) if total > 0 else 0
            data.append({"Relator": relator, "Qtd": count, "%": f"{pct:.1f}%"})
        
        if data:
            st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
        else:
            st.info("Sem dados")


def _render_distribution_tables(issues: List[Issue]):
    """Renderiza tabelas de distribuição por Tipo e Status."""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🗂 Demandas por Tipo")
        
        tipo_count: Dict[str, int] = defaultdict(int)
        for issue in issues:
            tipo = issue.issue_type or "Outros"
            tipo_count[tipo] += 1
        
        total = len(issues)
        data = []
        for tipo, count in sorted(tipo_count.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total * 100) if total > 0 else 0
            data.append({"Tipo": tipo, "Qtd": count, "%": f"{pct:.1f}%"})
        
        if data:
            st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
    
    with col2:
        st.subheader("📋 Demandas por Status")
        
        status_count: Dict[str, int] = defaultdict(int)
        for issue in issues:
            status = issue.status or "Sem status"
            status_count[status] += 1
        
        total = len(issues)
        data = []
        for status, count in sorted(status_count.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total * 100) if total > 0 else 0
            data.append({"Status": status, "Qtd": count, "%": f"{pct:.1f}%"})
        
        if data:
            st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)


def _render_monthly_charts(issues: List[Issue]):
    """Renderiza gráficos de evolução mensal."""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Evolução Mensal de Criação")
        
        monthly: Dict[str, int] = defaultdict(int)
        for issue in issues:
            if issue.created_date:
                key = issue.created_date.strftime("%Y-%m")
                monthly[key] += 1
        
        if monthly:
            df = pd.DataFrame([
                {"Mês": k, "Criadas": v}
                for k, v in sorted(monthly.items())
            ])
            st.line_chart(df.set_index("Mês"))
        else:
            st.info("Sem dados")
    
    with col2:
        st.subheader("⏱ Média de Atendimento (dias) por Mês")
        
        atend: Dict[str, Dict[str, float]] = defaultdict(lambda: {"sum": 0, "count": 0})
        
        for issue in issues:
            if issue.created_date and issue.resolution_date and issue.status_category == "Done":
                dias = (issue.resolution_date - issue.created_date).days
                if dias >= 0:
                    key = issue.created_date.strftime("%Y-%m")
                    atend[key]["sum"] += dias
                    atend[key]["count"] += 1
        
        if atend:
            df = pd.DataFrame([
                {"Mês": k, "Média (dias)": v["sum"] / v["count"] if v["count"] > 0 else 0}
                for k, v in sorted(atend.items())
            ])
            st.bar_chart(df.set_index("Mês"))
        else:
            st.info("Sem dados de resolução")


def _render_backlog_table(issues: List[Issue]):
    """Renderiza tabela de backlog detalhado com export."""
    
    st.subheader("📦 Backlog Detalhado")
    
    # Filtrar apenas backlog (não concluídos)
    backlog = [i for i in issues if i.status_category != "Done"]
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.caption(f"{len(backlog)} itens pendentes")
    
    with col2:
        # Botão de export
        if backlog:
            export_data = []
            for issue in backlog:
                export_data.append({
                    "Chave": issue.key,
                    "Tipo": issue.issue_type or "",
                    "Resumo": issue.summary or "",
                    "Responsável": issue.assignee_name or "",
                    "Status": issue.status or "",
                    "Criado": issue.created_date.strftime("%d/%m/%Y %H:%M") if issue.created_date else ""
                })
            
            df_export = pd.DataFrame(export_data)
            csv = df_export.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="📥 Exportar Backlog (CSV)",
                data=csv,
                file_name="backlog_acumulado.csv",
                mime="text/csv",
                key="export_backlog"
            )
    
    # Tabela
    if backlog:
        table_data = []
        for issue in backlog[:100]:  # Limitar a 100 itens
            table_data.append({
                "Chave": issue.key,
                "Tipo": issue.issue_type or "",
                "Resumo": (issue.summary[:60] + "...") if issue.summary and len(issue.summary) > 60 else (issue.summary or ""),
                "Responsável": issue.assignee_name or "Sem responsável",
                "Status": issue.status or "",
                "Criado": issue.created_date.strftime("%d/%m/%Y %H:%M") if issue.created_date else "-",
                "Início": issue.started_date.strftime("%d/%m/%Y %H:%M") if issue.started_date else "-",
                "Fim": issue.resolution_date.strftime("%d/%m/%Y %H:%M") if issue.resolution_date else "-"
            })
        
        st.dataframe(
            pd.DataFrame(table_data),
            width="stretch",
            hide_index=True,
            column_config={
                "Chave": st.column_config.TextColumn("Chave", width="small"),
                "Tipo": st.column_config.TextColumn("Tipo", width="small"),
                "Resumo": st.column_config.TextColumn("Resumo", width="large"),
                "Responsável": st.column_config.TextColumn("Responsável", width="medium"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Criado": st.column_config.TextColumn("Criado", width="small"),
                "Início": st.column_config.TextColumn("Início", width="small"),
                "Fim": st.column_config.TextColumn("Fim", width="small")
            }
        )
        
        if len(backlog) > 100:
            st.caption(f"Mostrando 100 de {len(backlog)} itens. Exporte para ver todos.")
    else:
        st.success("🎉 Nenhum item pendente no backlog!")
