"""
AI Analyzer for Jira Issues.

Supports multiple providers: OpenAI and Google Gemini.
"""

import os
import json
import streamlit as st
from typing import Optional


# =============================================================================
# API Key helpers
# =============================================================================

def _get_openai_api_key() -> Optional[str]:
    try:
        key = st.secrets.get("OPENAI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY", "")


def _get_gemini_api_key() -> Optional[str]:
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "")


def get_available_providers() -> dict:
    """Return dict of available AI providers."""
    providers = {}
    if _get_gemini_api_key():
        providers["gemini"] = "Google Gemini"
    if _get_openai_api_key():
        providers["openai"] = "OpenAI (GPT)"
    return providers


def is_ai_available() -> bool:
    return bool(get_available_providers())


# =============================================================================
# OpenAI
# =============================================================================

def _analyze_with_openai(csv_data: str, prompt: str) -> Optional[str]:
    """Send data to OpenAI for analysis."""
    api_key = _get_openai_api_key()
    if not api_key:
        return "API Key da OpenAI não configurada."
    
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import requests
    
    full_prompt = f"""{prompt}

Dados das issues (CSV):
{csv_data}
"""
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    models_to_try = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
    last_error = None
    
    for model in models_to_try:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Você é um analista de engenharia de software especializado em métricas ágeis. Responda sempre em português."},
                    {"role": "user", "content": full_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            }
            
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                verify=False,
                timeout=120
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                error_body = resp.json() if resp.text else {}
                error_detail = error_body.get("error", {}).get("message", "")
                last_error = f"{model}: {error_detail}"
                import time
                time.sleep(5)
                continue
            elif resp.status_code == 404:
                last_error = f"Modelo {model} não disponível"
                continue
            else:
                error_body = resp.json() if resp.text else {}
                error_detail = error_body.get("error", {}).get("message", resp.text[:200])
                last_error = f"{model}: {error_detail}"
                continue
                
        except Exception as e:
            last_error = str(e)
            continue
    
    return f"Erro ao consultar OpenAI: {last_error}"


# =============================================================================
# Gemini
# =============================================================================

def _analyze_with_gemini(csv_data: str, prompt: str) -> Optional[str]:
    """Send data to Gemini for analysis."""
    api_key = _get_gemini_api_key()
    if not api_key:
        return "API Key do Gemini não configurada."
    
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import requests
    import time
    
    full_prompt = f"""{prompt}

Dados das issues (CSV):
{csv_data}
"""
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    
    models_to_try = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-2.5-flash"]
    last_error = None
    
    for model in models_to_try:
        for attempt in range(2):
            try:
                url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}"
                resp = requests.post(url, json=payload, verify=False, timeout=120)
                
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                    return "Resposta vazia."
                elif resp.status_code == 429:
                    last_error = f"Rate limit ({model})"
                    if attempt == 0:
                        time.sleep(15)
                        continue
                    break
                elif resp.status_code == 404:
                    last_error = f"Modelo {model} não encontrado"
                    break
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    break
            except Exception as e:
                last_error = str(e)
                break
    
    return f"Erro ao consultar Gemini: {last_error}"


# =============================================================================
# Main dispatcher
# =============================================================================

def analyze_issues(csv_data: str, prompt: str, provider: str = "openai") -> Optional[str]:
    """
    Analyze issues using the selected AI provider.
    
    Args:
        csv_data: CSV string with issue data.
        prompt: Analysis prompt.
        provider: "openai" or "gemini".
    """
    if provider == "openai":
        return _analyze_with_openai(csv_data, prompt)
    elif provider == "gemini":
        return _analyze_with_gemini(csv_data, prompt)
    else:
        return f"Provedor '{provider}' não suportado."


# Pre-built analysis prompts
PROMPTS = {
    "classificar_suporte": """Você é um analista de engenharia de software. Analise as issues abaixo e classifique cada uma como:
- **Suporte/Operação**: atividades de manutenção, correção de bugs, configuração, liberação, monitoramento, incidentes
- **Desenvolvimento**: novas funcionalidades, melhorias, refatoração, arquitetura
- **Indefinido**: quando não for possível classificar

Retorne uma tabela markdown com as colunas: Chave | Resumo | Classificação | Justificativa
Ao final, faça um resumo com:
- Total de cada classificação
- Padrões identificados
- Recomendações sobre o que poderia ser delegado ao time de operações""",

    "identificar_padroes": """Você é um analista de dados. Analise as issues abaixo e identifique:
1. **Padrões recorrentes**: issues similares que se repetem
2. **Agrupamentos**: categorias naturais que emergem dos dados
3. **Gargalos**: onde as issues ficam mais tempo paradas
4. **Recomendações**: sugestões para melhorar o fluxo

Seja objetivo e use dados concretos da planilha para embasar suas conclusões.""",

    "analise_produtividade": """Você é um Scrum Master experiente. Analise as issues abaixo e forneça:
1. **Throughput**: quantas issues foram concluídas vs criadas
2. **Lead Time**: análise dos tempos de entrega
3. **Distribuição de trabalho**: como o trabalho está distribuído entre os membros
4. **Pontos de atenção**: riscos e problemas identificados
5. **Sugestões**: ações concretas para melhorar a produtividade

Use os dados reais para embasar cada ponto.""",

    "prompt_livre": ""
}
