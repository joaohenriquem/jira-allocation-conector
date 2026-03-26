"""
Report View - Extração de dados para análise e classificação.

Permite exportar issues do Jira em formato planilha para análise,
com opção de classificação por IA para identificar padrões.
"""

import streamlit as st
import pandas as pd
from typing import List, Optional
from collections import defaultdict
from src.models.data_models import Issue, get_tshirt_size_label
from src.config.teams_loader import load_teams, find_team_for_member


def _build_issues_dataframe(issues: List[Issue]) -> pd.DataFrame:
    """Build a complete DataFrame from issues for export."""
    teams = load_teams()
    
    rows = []
    for issue in issues:
        team = find_team_for_member(teams, issue.assignee_name) if issue.assignee_name else "Sem time"
        
        # Calculate lead time in days
        lead_time = None
        if issue.resolution_date and issue.created_date:
            lead_time = (issue.resolution_date - issue.created_date).days
        
        # Calculate cycle time in days
        cycle_time = None
        if issue.resolution_date and issue.started_date:
            cycle_time = (issue.resolution_date - issue.started_date).days
        
        rows.append({
            "Chave": issue.key,
            "Tipo": issue.issue_type,
            "Resumo": issue.summary,
            "Status": issue.status,
            "Categoria Status": issue.status_category,
            "Responsável": issue.assignee_name or "Sem responsável",
            "Time": team or "Sem time",
            "Tamanho": get_tshirt_size_label(issue.t_shirt_size),
            "Esforço (h)": issue.story_points or 0,
            "Labels": ", ".join(issue.labels) if issue.labels else "",
            "Componentes": ", ".join(issue.components) if issue.components else "",
            "Criado": issue.created_date.strftime("%d/%m/%Y %H:%M") if issue.created_date else "",
            "Início": issue.started_date.strftime("%d/%m/%Y %H:%M") if issue.started_date else "",
            "Resolvido": issue.resolution_date.strftime("%d/%m/%Y %H:%M") if issue.resolution_date else "",
            "Lead Time (dias)": lead_time if lead_time is not None else "",
            "Cycle Time (dias)": cycle_time if cycle_time is not None else "",
        })
    
    return pd.DataFrame(rows)


def render_report_summary(df: pd.DataFrame):
    """Render summary metrics from the report data."""
    total = len(df)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total de Issues", total)
    with col2:
        by_type = df["Tipo"].value_counts()
        top_type = f"{by_type.index[0]} ({by_type.iloc[0]})" if len(by_type) > 0 else "-"
        st.metric("Tipo mais frequente", top_type)
    with col3:
        done = len(df[df["Categoria Status"] == "Done"])
        st.metric("Concluídas", done)
    with col4:
        assignees = df["Responsável"].nunique()
        st.metric("Responsáveis", assignees)
    with col5:
        teams = df["Time"].nunique()
        st.metric("Times", teams)


def render_report_analysis(df: pd.DataFrame):
    """Render analysis charts for the report."""
    
    # Issues by type
    st.markdown("#### Distribuição por Tipo")
    type_counts = df["Tipo"].value_counts().reset_index()
    type_counts.columns = ["Tipo", "Quantidade"]
    st.dataframe(type_counts, use_container_width=True, hide_index=True)
    
    # Issues by assignee
    st.markdown("#### Distribuição por Responsável")
    assignee_counts = df["Responsável"].value_counts().head(20).reset_index()
    assignee_counts.columns = ["Responsável", "Quantidade"]
    
    # Add team info
    teams = load_teams()
    assignee_counts["Time"] = assignee_counts["Responsável"].apply(
        lambda x: find_team_for_member(teams, x) or "Sem time"
    )
    st.dataframe(assignee_counts, use_container_width=True, hide_index=True)
    
    # Issues by team
    st.markdown("#### Distribuição por Time")
    team_counts = df["Time"].value_counts().reset_index()
    team_counts.columns = ["Time", "Quantidade"]
    st.dataframe(team_counts, use_container_width=True, hide_index=True)
    
    # Issues by status
    st.markdown("#### Distribuição por Status")
    status_counts = df["Status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Quantidade"]
    st.dataframe(status_counts, use_container_width=True, hide_index=True)


def render_keyword_analysis(df: pd.DataFrame):
    """Analyze issue summaries for keyword patterns to identify support tasks."""
    st.markdown("#### 🔍 Análise de Palavras-chave nos Resumos")
    st.caption("Identifica padrões nos títulos das issues para classificação de suporte vs. desenvolvimento")
    
    # Common support keywords
    support_keywords = [
        "suporte", "correção", "corrigir", "bug", "erro", "fix",
        "ajuste", "ajustar", "problema", "incidente", "urgente",
        "hotfix", "patch", "rollback", "reverter", "manutenção",
        "atualizar", "atualização", "migração", "migrar",
        "configurar", "configuração", "habilitar", "desabilitar",
        "liberar", "liberação", "permissão", "acesso",
        "monitorar", "monitoramento", "alerta", "log",
    ]
    
    dev_keywords = [
        "criar", "novo", "nova", "implementar", "desenvolver",
        "feature", "funcionalidade", "melhoria", "melhorar",
        "redesign", "refatorar", "refatoração", "arquitetura",
        "api", "endpoint", "integração", "integrar",
        "tela", "página", "componente", "módulo",
    ]
    
    summaries = df["Resumo"].str.lower()
    
    # Count keyword matches
    support_matches = defaultdict(int)
    dev_matches = defaultdict(int)
    
    for kw in support_keywords:
        count = summaries.str.contains(kw, na=False).sum()
        if count > 0:
            support_matches[kw] = count
    
    for kw in dev_keywords:
        count = summaries.str.contains(kw, na=False).sum()
        if count > 0:
            dev_matches[kw] = count
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("**🔧 Palavras de Suporte/Operação**")
        if support_matches:
            support_df = pd.DataFrame(
                sorted(support_matches.items(), key=lambda x: x[1], reverse=True),
                columns=["Palavra-chave", "Ocorrências"]
            )
            st.dataframe(support_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhuma palavra-chave de suporte encontrada")
    
    with c2:
        st.markdown("**🚀 Palavras de Desenvolvimento**")
        if dev_matches:
            dev_df = pd.DataFrame(
                sorted(dev_matches.items(), key=lambda x: x[1], reverse=True),
                columns=["Palavra-chave", "Ocorrências"]
            )
            st.dataframe(dev_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhuma palavra-chave de desenvolvimento encontrada")
    
    # Auto-classify issues
    st.divider()
    st.markdown("#### 🤖 Classificação Automática (por palavras-chave)")
    
    def classify_issue(summary: str) -> str:
        s = summary.lower()
        support_score = sum(1 for kw in support_keywords if kw in s)
        dev_score = sum(1 for kw in dev_keywords if kw in s)
        
        if support_score > dev_score:
            return "Suporte/Operação"
        elif dev_score > support_score:
            return "Desenvolvimento"
        else:
            return "Indefinido"
    
    df_classified = df.copy()
    df_classified["Classificação"] = df_classified["Resumo"].apply(classify_issue)
    
    class_counts = df_classified["Classificação"].value_counts()
    
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        st.metric("🔧 Suporte/Operação", class_counts.get("Suporte/Operação", 0))
    with cc2:
        st.metric("🚀 Desenvolvimento", class_counts.get("Desenvolvimento", 0))
    with cc3:
        st.metric("❓ Indefinido", class_counts.get("Indefinido", 0))
    
    return df_classified


def render_report_tab(issues: List[Issue], type_filter: list = None, status_filter: list = None, team_filter: list = None):
    """
    Main render function for the Report tab.
    
    Args:
        issues: All issues from the selected project/filters.
        type_filter: Optional list of issue types to filter.
        status_filter: Optional list of statuses to filter.
        team_filter: Optional list of teams to filter.
    """
    st.subheader("📄 Relatório e Extração de Dados")
    st.caption("Extraia dados do Jira para análise, identifique padrões de suporte e exporte para planilha")
    
    if not issues:
        st.info("Selecione um projeto e aplique os filtros para gerar o relatório.")
        return
    
    # Build dataframe
    df = _build_issues_dataframe(issues)
    
    # Apply filters from top bar
    filtered_df = df.copy()
    if type_filter:
        filtered_df = filtered_df[filtered_df["Tipo"].isin(type_filter)]
    if status_filter:
        filtered_df = filtered_df[filtered_df["Status"].isin(status_filter)]
    if team_filter:
        filtered_df = filtered_df[filtered_df["Time"].isin(team_filter)]
    
    # Summary
    render_report_summary(filtered_df)
    
    # OKRs for report tab
    from src.ui.okr_components import render_okrs_for_tab
    # Calculate support classification metrics
    _support_kws = ["suporte", "correção", "corrigir", "bug", "erro", "fix", "ajuste", "problema", "incidente", "hotfix", "manutenção", "configurar", "liberar", "monitorar"]
    _dev_kws = ["criar", "novo", "nova", "implementar", "desenvolver", "feature", "funcionalidade", "melhoria", "refatorar", "api", "endpoint", "integração", "tela", "componente"]
    
    def _classify(s):
        sl = s.lower()
        sup = sum(1 for k in _support_kws if k in sl)
        dev = sum(1 for k in _dev_kws if k in sl)
        return "support" if sup > dev else ("dev" if dev > sup else "unknown")
    
    _classifications = filtered_df["Resumo"].apply(_classify)
    _total_classified = len(_classifications[_classifications != "unknown"])
    _total_all = len(filtered_df)
    _support_mapped_pct = (_total_classified / _total_all * 100) if _total_all > 0 else 0
    
    render_okrs_for_tab("report", {
        "support_mapped": _support_mapped_pct,
        "support_migrated": 0,  # Manual tracking
    })
    
    if len(filtered_df) < len(df):
        st.caption(f"📊 {len(filtered_df)} issues após filtros (de {len(df)} total)")
    
    st.divider()
    
    # Analysis tabs
    analysis_tab, keywords_tab, ai_tab, data_tab = st.tabs([
        "📊 Análise",
        "🔍 Classificação Suporte vs Dev",
        "🤖 Análise com IA",
        "📋 Dados Completos"
    ])
    
    with analysis_tab:
        render_report_analysis(filtered_df)
    
    with keywords_tab:
        df_classified = render_keyword_analysis(filtered_df)
        
        st.divider()
        
        # Show classified issues
        st.markdown("#### 📋 Issues Classificadas")
        
        class_filter = st.selectbox(
            "Filtrar por classificação",
            options=["Todas", "Suporte/Operação", "Desenvolvimento", "Indefinido"],
            key="report_class_filter"
        )
        
        display_df = df_classified
        if class_filter != "Todas":
            display_df = df_classified[df_classified["Classificação"] == class_filter]
        
        st.dataframe(
            display_df[["Chave", "Tipo", "Resumo", "Status", "Responsável", "Time", "Classificação"]],
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
        # Export classified
        csv_classified = display_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"📥 Exportar Classificadas ({len(display_df)} issues)",
            data=csv_classified,
            file_name="issues_classificadas.csv",
            mime="text/csv",
            key="export_classified"
        )
    
    with ai_tab:
        render_ai_analysis(filtered_df)
    
    with data_tab:
        st.markdown("#### 📋 Todos os Dados")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=500)
        
        # Export full data
        csv_full = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"📥 Exportar CSV Completo ({len(filtered_df)} issues)",
            data=csv_full,
            file_name="relatorio_jira.csv",
            mime="text/csv",
            key="export_full_report"
        )


def render_ai_analysis(df: pd.DataFrame):
    """Render AI analysis section using Gemini."""
    from src.ai.gemini_analyzer import is_gemini_available, analyze_issues_with_gemini, PROMPTS
    
    st.markdown("#### 🤖 Análise com Inteligência Artificial")
    
    if not is_gemini_available():
        st.warning(
            "⚠️ API Key do Gemini não configurada. "
            "Adicione `GEMINI_API_KEY` nas variáveis de ambiente ou no secrets.toml."
        )
        return
    
    st.caption(f"📊 {len(df)} issues serão enviadas para análise")
    
    # Prompt selection
    prompt_options = {
        "classificar_suporte": "🔧 Classificar Suporte vs Desenvolvimento",
        "identificar_padroes": "🔍 Identificar Padrões e Agrupamentos",
        "analise_produtividade": "📈 Análise de Produtividade",
        "prompt_livre": "✏️ Prompt Livre",
    }
    
    selected_prompt_key = st.selectbox(
        "Tipo de Análise",
        options=list(prompt_options.keys()),
        format_func=lambda x: prompt_options[x],
        key="ai_prompt_select"
    )
    
    # Show/edit prompt
    prompt_text = PROMPTS[selected_prompt_key]
    
    if selected_prompt_key == "prompt_livre":
        prompt_text = st.text_area(
            "Escreva seu prompt",
            value="",
            height=150,
            key="ai_custom_prompt",
            placeholder="Ex: Analise as issues e identifique quais são atividades de suporte que poderiam ser executadas pelo time de operações..."
        )
    else:
        with st.expander("Ver prompt que será enviado"):
            st.code(prompt_text, language=None)
    
    # Limit data to avoid token limits
    max_issues = st.slider(
        "Máximo de issues para análise",
        min_value=10,
        max_value=min(500, len(df)),
        value=min(50, len(df)),
        step=10,
        key="ai_max_issues",
        help="Limite para evitar exceder o limite de tokens da API"
    )
    
    # Prepare CSV data (limited columns for token efficiency)
    export_cols = ["Chave", "Tipo", "Resumo", "Status", "Responsável", "Time", "Tamanho", "Lead Time (dias)"]
    available_cols = [c for c in export_cols if c in df.columns]
    csv_for_ai = df[available_cols].head(max_issues).to_csv(index=False)
    
    # Run analysis
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run_analysis = st.button(
            "🚀 Analisar com IA",
            key="btn_run_ai_analysis",
            type="primary",
            use_container_width=True
        )
    with col_info:
        st.caption(f"Serão enviadas {min(max_issues, len(df))} issues ({len(csv_for_ai)} caracteres)")
    
    if run_analysis:
        if not prompt_text.strip():
            st.warning("Escreva um prompt para a análise.")
            return
        
        with st.spinner("🤖 Analisando... isso pode levar alguns segundos"):
            result = analyze_issues_with_gemini(csv_for_ai, prompt_text)
        
        if result:
            st.session_state.ai_analysis_result = result
            st.session_state.ai_analysis_prompt = prompt_options.get(selected_prompt_key, "Prompt Livre")
    
    # Show result
    if "ai_analysis_result" in st.session_state and st.session_state.ai_analysis_result:
        st.divider()
        st.markdown(f"**Resultado da análise** ({st.session_state.get('ai_analysis_prompt', '')})")
        st.markdown(st.session_state.ai_analysis_result)
        
        # Export result
        st.download_button(
            label="📥 Exportar Análise (Markdown)",
            data=st.session_state.ai_analysis_result.encode("utf-8"),
            file_name="analise_ia.md",
            mime="text/markdown",
            key="export_ai_analysis"
        )
