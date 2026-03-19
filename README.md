# Jira Allocation Connector

Dashboard interativo para análise de métricas de alocação e produtividade de times de desenvolvimento, integrado com a API do Jira.

## Funcionalidades

- **Visão por Projeto**: Métricas de alocação e produtividade por projeto/sprint
- **Visão por Profissional**: Alocação consolidada por profissional em todos os projetos
- **Legado**: Dashboard com KPIs, Net Flow, Capacity e Backlog detalhado
- **Cache Inteligente**: Reduz chamadas à API (TTL de 1 hora)
- **Exportação CSV**: Exportação de dados para análise externa

## Deploy no Streamlit Cloud

### 1. Preparar o Repositório

Certifique-se de que o repositório contém:
- `app.py` (entry point)
- `requirements.txt` (dependências)
- `.streamlit/config.toml` (configurações de tema)
- `config.yaml` (configurações da aplicação)

**IMPORTANTE**: Nunca commite o arquivo `.env` com suas credenciais!

### 2. Criar Conta no Streamlit Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io)
2. Faça login com sua conta GitHub

### 3. Deploy da Aplicação

1. Clique em "New app"
2. Selecione o repositório e branch
3. Configure:
   - **Main file path**: `jira-allocation-connector/app.py`
   - **App URL**: escolha um nome único

### 4. Configurar Secrets (Variáveis de Ambiente)

No Streamlit Cloud, vá em **Settings > Secrets** e adicione:

```toml
JIRA_BASE_URL = "https://sua-empresa.atlassian.net/"
JIRA_USERNAME = "seu-email@exemplo.com"
JIRA_API_TOKEN = "seu-api-token-jira"
```

**Para obter o API Token do Jira:**
1. Acesse [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Clique em "Create API token"
3. Copie o token gerado

### 5. Reiniciar a Aplicação

Após configurar os secrets, clique em "Reboot app" para aplicar as mudanças.

---

## Execução Local

### Requisitos

- Python 3.10+
- Acesso à API do Jira Cloud

### Instalação

```bash
cd jira-allocation-connector
pip install -r requirements.txt
```

### Configuração

1. Copie o arquivo de exemplo:
```bash
cp .env.example .env
```

2. Configure suas credenciais no `.env`:
```env
JIRA_BASE_URL=https://sua-empresa.atlassian.net/
JIRA_USERNAME=seu-email@exemplo.com
JIRA_API_TOKEN=seu-api-token
```

### Execução

```bash
streamlit run app.py
```

Acesse `http://localhost:8501`

---

## Estrutura do Projeto

```
jira-allocation-connector/
├── app.py                    # Entry point Streamlit
├── config.yaml               # Configurações da aplicação
├── requirements.txt          # Dependências Python
├── .streamlit/config.toml    # Tema e configurações Streamlit
├── src/
│   ├── connector/            # Integração com Jira API
│   ├── metrics/              # Cálculo de métricas
│   ├── cache/                # Gerenciamento de cache
│   ├── config/               # Carregamento de configuração
│   ├── models/               # Modelos de dados
│   ├── ui/                   # Componentes de interface
│   └── utils/                # Utilitários (logging)
└── tests/                    # Testes
```

## Limitações no Streamlit Cloud

- **Cache por sessão**: O cache usa `session_state`, então cada usuário tem seu próprio cache
- **Timeout**: Requisições longas podem dar timeout (limite de ~30s por request)
- **Memória**: Limite de 1GB de RAM no plano gratuito

## Licença

Projeto interno Efí - uso restrito.
