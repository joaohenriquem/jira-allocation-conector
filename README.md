# Jira Allocation Connector

Dashboard interativo para análise de métricas de alocação e produtividade de times de desenvolvimento, integrado com a API do Jira.

## Funcionalidades

- **Visão Unificada**: Ciclo completo Produto → Engenharia com funil, burndown, OKRs e balanço de vazão
- **Visão por Projeto**: Métricas de alocação e produtividade por projeto/sprint com filtros por time e tipo de issue
- **Visão por Profissional**: Alocação consolidada por profissional com seleção automática por time
- **Relatórios**: Extração de dados com classificação Suporte vs Desenvolvimento, análise com IA (Gemini) e exportação CSV
- **Times**: Configuração e busca de profissionais por time
- **OKRs**: Acompanhamento de Key Results integrado às visões (configurável via JSON)
- **Controle de Acesso**: Autenticação por email corporativo e filtro por IP
- **Monitoramento**: Integração com Sentry para rastreamento de erros
- **Cache Inteligente**: Reduz chamadas à API com cache em session_state e MongoDB (opcional)

## Abas do Dashboard

| Aba | Descrição |
|-----|-----------|
| 🔄 Visão Unificada | Ciclo completo dos dois boards (Produto + Engenharia) com métricas, funil, burndown e OKRs |
| 📊 Visão por Projeto | Métricas de alocação por projeto/sprint com filtros de time, tipo e datas |
| 👤 Visão por Profissional | Alocação cross-project por profissional, com seleção automática por time |
| 📄 Relatórios | Extração de dados, classificação por palavras-chave, análise com IA e exportação CSV |
| 👥 Times | Configuração de times e busca de profissionais |

## Deploy no Streamlit Cloud

### 1. Preparar o Repositório

Certifique-se de que o repositório contém:
- `app.py` (entry point)
- `requirements.txt` (dependências)
- `.streamlit/config.toml` (configurações de tema)
- `config.yaml` (configurações da aplicação)
- `src/config/times.json` (configuração de times)
- `src/config/okrs.json` (configuração de OKRs)

**IMPORTANTE**: Nunca commite `.env` ou `.streamlit/secrets.toml` com credenciais!

### 2. Configurar Secrets

No Streamlit Cloud, vá em **Settings > Secrets** e adicione:

```toml
# Jira
JIRA_BASE_URL = "https://sua-empresa.atlassian.net"
JIRA_USERNAME = "seu-email@empresa.com"
JIRA_API_TOKEN = "seu-api-token"

# IPs permitidos (vazio = sem filtro)
ALLOWED_IPS = ""

# Sentry (opcional)
SENTRY_DSN = ""
SENTRY_ENVIRONMENT = "production"

# Gemini AI (opcional - para análise com IA nos relatórios)
GEMINI_API_KEY = ""

# MongoDB Cache (opcional)
MONGODB_URI = ""
MONGODB_DATABASE = "jira_cache"
MONGODB_CACHE_ENABLED = "false"
```

## Execução Local

### Requisitos

- Python 3.10+
- Acesso à API do Jira Cloud

### Instalação

```bash
pip install -r requirements.txt
```

### Configuração

```bash
cp .env.example .env
# Edite o .env com suas credenciais
```

### Execução

```bash
streamlit run app.py
# Ou no Windows:
.\run.ps1
```

Acesse `http://localhost:8501` (login é pulado automaticamente em localhost).

## Estrutura do Projeto

```
jira-allocation-connector/
├── app.py                        # Entry point Streamlit
├── config.yaml                   # Configurações da aplicação
├── requirements.txt              # Dependências Python
├── .streamlit/config.toml        # Tema e configurações Streamlit
├── src/
│   ├── ai/
│   │   ├── assistant.py          # Assistente IA (OpenAI/Anthropic)
│   │   └── gemini_analyzer.py    # Análise com Google Gemini
│   ├── cache/                    # Cache (session_state + MongoDB)
│   ├── config/
│   │   ├── config_loader.py      # Carregamento de config.yaml
│   │   ├── teams_loader.py       # Gestão de times
│   │   ├── times.json            # Configuração de times
│   │   └── okrs.json             # Configuração de OKRs
│   ├── connector/
│   │   └── jira_connector.py     # Integração com Jira API (v3)
│   ├── metrics/
│   │   ├── metrics_engine.py     # Cálculo de métricas
│   │   └── professional_metrics.py # Métricas por profissional
│   ├── models/
│   │   └── data_models.py        # Modelos de dados
│   ├── ui/
│   │   ├── cycle_view.py         # Visão Unificada (ciclo completo)
│   │   ├── report_view.py        # Relatórios e exportação
│   │   ├── professional_view.py  # Visão por profissional
│   │   ├── okr_components.py     # Componentes de OKR
│   │   ├── charts.py             # Gráficos Plotly
│   │   ├── components.py         # Componentes UI reutilizáveis
│   │   └── styles.py             # Tema e estilos
│   └── utils/
│       ├── logging.py            # Logging estruturado
│       └── sentry_config.py      # Configuração do Sentry
└── tests/                        # Testes
```

## Configuração de OKRs

Edite `src/config/okrs.json` para definir seus OKRs. Cada KR é vinculado a uma aba:

```json
{
  "quarter": "Q2 2026",
  "objective": "Aumentar eficiência das entregas",
  "key_results": [
    {
      "id": "kr1",
      "description": "Reduzir lead time médio para 15 dias",
      "metric": "lead_time_avg",
      "target": 15,
      "unit": "dias",
      "direction": "decrease",
      "tab": "cycle"
    }
  ]
}
```

Valores de `tab`: `cycle`, `project`, `report`.
Valores de `direction`: `increase`, `decrease`, `target_range`.

## Configuração de Times

Edite `src/config/times.json` para gerenciar times e membros.

## Licença

Projeto interno Efí - uso restrito.
