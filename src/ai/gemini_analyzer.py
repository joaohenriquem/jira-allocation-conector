"""
Gemini AI Analyzer for Jira Issues.

Uses Google Gemini REST API to analyze and classify issues from Jira reports.
"""

import os
import json
import streamlit as st
from typing import Optional


def _get_gemini_api_key() -> Optional[str]:
    """Get Gemini API key from secrets or environment."""
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "")


def is_gemini_available() -> bool:
    """Check if Gemini API key is configured."""
    return bool(_get_gemini_api_key())


def analyze_issues_with_gemini(csv_data: str, prompt: str) -> Optional[str]:
    """
    Send issue data to Gemini for analysis using REST API directly.
    """
    api_key = _get_gemini_api_key()
    if not api_key:
        return None
    
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import requests
    import time
    
    _ssl_verify = os.getenv("SSL_VERIFY", "true").lower() not in ("false", "0")
    
    full_prompt = f"""{prompt}

Dados das issues (CSV):
{csv_data}
"""
    
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}]
    }

    models_to_try = [
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
    ]
    
    last_error = None
    
    for model in models_to_try:
        for attempt in range(2):
            try:
                url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
                resp = requests.post(url, json=payload, verify=_ssl_verify, timeout=120, params={"key": api_key})
                
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                    return "Resposta vazia do Gemini."
                
                elif resp.status_code == 429:
                    last_error = f"Rate limit ({model})"
                    if attempt == 0:
                        time.sleep(15)
                        continue
                    break  # Try next model
                
                elif resp.status_code == 404:
                    last_error = f"Modelo {model} não encontrado"
                    break  # Try next model
                
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    break
                    
            except Exception as e:
                last_error = str(e)
                break
    
    return f"Erro ao consultar Gemini: {last_error}"


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
