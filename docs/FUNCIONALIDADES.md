# Documentação de Funcionalidades — Jira Allocation Connector

> Documento de referência para refatoração em React.  
> Versão atual: Streamlit (Python) | App: `app.py`

---

## 1. Visão Geral

Dashboard interativo para visualização de métricas de alocação e produtividade de times de desenvolvimento, integrado com Jira. Desenvolvido para a Efí Bank (fintech brasileira).

**URL de produção:** Streamlit Cloud  
**Autenticação:** Email corporativo + senha compartilhada  
**Integração:** Jira Cloud/Server via REST API  
**Cache:** MongoDB (persistente) + session_state (memória)  
**IA:** OpenAI (GPT-4o-mini) e Google Gemini  
**Monitoramento:** Sentry

---

## 2. Autenticação e Controle de Acesso

### Fluxo de Login
1. **Verificação de IP** — Lista de IPs permitidos (`ALLOWED_IPS` env var). Se vazia, aceita todos.
2. **Bypass localhost** — Em dev local, pula autenticação automaticamente.
3. **Formulário de login:**
   - Campo: email corporativo
   - Campo: senha de acesso (compartilhada, env `ACCESS_PASSWORD`)
   - Domínios aceitos: `@sejaefi.com.br`, `@gerencianet.com.br`
   - VIPs: emails em `VIP_EMAILS` acessam sem senha
   - Rate limit: máximo 5 tentativas por sessão
4. **Sessão:** email criptografado (Fernet) armazenado no session_state
5. **Logout:** botão "Sair" no header, limpa session_state

### Eventos monitorados (Sentry)
- Login autorizado (sucesso, VIP, localhost)
- Senha incorreta
- Email não autorizado
- IP bloqueado

---

## 3. Estrutura de Abas (Navegação Principal)

| # | Aba | Descrição |
|---|-----|-----------|
| 1 | Visão Unificada | Ciclo completo Produto → Engenharia |
| 2 | Visão por Projeto | Alocação e produtividade por projeto/sprint |
| 3 | Visão por Profissional | Alocação cross-project individual |
| 4 | Relatórios | Extração de dados, classificação, análise IA |
| 5 | Times | Visualização da estrutura de times |

---

## 4. Aba: Visão Unificada (Cycle View)

### Filtros
- Projetos (multiselect)
- Modo de data: Criação / Atualização / Resolução / Criação ou Atualização
- Data início e fim

### Componentes

#### 4.1 OKRs do Ciclo
- Lead time médio (meta: 15 dias)
- Taxa de conclusão (meta: 80%)
- Taxa de handoff (meta: ≤10%)

#### 4.2 Métricas Resumo
- Total de issues
- Em Produto / Em Handoff / Em Engenharia / Concluídas
- Barra de distribuição do ciclo (stacked horizontal)

#### 4.3 Lead Time
- Médio, Mínimo, Máximo (em dias) para issues concluídas
- Cálculo: `resolution_date - started_date`

#### 4.4 Funil Duplo
- **Funil Produto:** Oportunidades → Contexto → Investigação → Definição → Aguardando Priorização
- **Funil Engenharia:** Pronto para Desenvolver → Em Desenvolvimento → Validação → Homologação → Implantação → Concluído

#### 4.5 Gráficos de Pizza por Área
- Produto: distribuição de status (paleta roxa)
- Engenharia: distribuição de status (paleta azul)

#### 4.6 Burndown do Ciclo
- Linha: issues restantes (aberto) ao longo do tempo
- Linha tracejada: burndown ideal (linear)
- Linha verde: concluídas acumuladas

#### 4.7 Detalhamento por Fase (Kanban)
- Agrupamento: 🟣 Produto / 🟡 Handoff / 🔵 Engenharia / 🟢 Concluído
- Expansível, com tabela de issues (link para Jira)

#### 4.8 Balanço de Vazão
- Tabela: Tipo | Entradas | Saídas | Saldo | Status Vazão | Eficiência %

### Classificação de Fases (Lógica)
```
Produto: Oportunidades, Contexto e Viabilidade, Investigação, Definição da Solução, Aguardando Priorização
Handoff: Backlog Engenharia, Priorizado Engenharia
Engenharia: Pronto para Desenvolver, Em Desenvolvimento, Validação, Para Homologar, Implantação
Concluído: Itens Concluídos
```

---

## 5. Aba: Visão por Projeto

### Filtros (Inline Expander)
- Projetos (multiselect)
- Time (multiselect, carregado de `times.json`)
- Tipo de item (Bug, Task, Sub-task, Story, Improvement, Epic)
- Modo de data (seletor)
- Data início / fim
- Épicos (condicional: aparece quando tipo "Epic" selecionado)

### Componentes

#### 5.1 OKRs do Projeto
- Membros sobrecarregados (meta: 0)
- Taxa média de alocação (meta: 70-90%)

#### 5.2 Métricas de Alocação (Cards)
- Total de membros
- Taxa média de alocação
- Sobrecarregados (count)
- Subutilizados (count)

#### 5.3 Gráfico Combinado de Alocação
- Barra horizontal stacked: alocação por membro, segmentada por tipo de issue
- Linhas verticais de threshold: 50% (subutilizado) e 100% (sobrecarga)

#### 5.4 Cards por Membro
- Grid 3 colunas: nome, taxa %, issues count, esforço em horas
- Cor do indicador: verde (normal), amarelo (subutilizado), vermelho (sobrecarregado)

#### 5.5 Drill-Down por Membro
- Expandível: lista de issues com status, tipo, resumo, tamanho, link Jira

#### 5.6 Balanço de Vazão
- Mesma tabela do Cycle View (entradas vs saídas por tipo)

#### 5.7 Gráficos de Tipo por Área
- Dois pie charts: Produto vs Engenharia (exclui Epic/Story)

#### 5.8 Métricas de Produtividade
- Throughput (issues concluídas)
- Lead Time médio
- Cycle Time médio
- Velocity (soma de horas das issues concluídas)
- Taxa de conclusão

#### 5.9 Velocity Trend
- Gráfico de linha: velocity semanal (últimas 8 semanas)

#### 5.10 AI Scrum Master (Opcional)
- Análise automática quando `AI_ENABLED=true`
- Gera sugestões baseadas nas métricas atuais
- Categorias: alocação, produtividade, risco, processo, time

### Modelo de Capacidade
```
Capacidade padrão: 24h por sprint (4 dias × 6 horas)
Taxa de alocação = (soma_horas_issues / capacidade) × 100
Sobrecarga: > 100%
Subutilização: < 50%
```

---

## 6. Aba: Visão por Profissional

### Filtros
- Time (multiselect) — filtro primário
- Profissional (dropdown — carregado após selecionar projetos)
- Data início / fim
- Botão "Atualizar"

### Modos de Visualização

#### 6.1 Modo Individual (profissional selecionado)
- **Cards resumo:** Taxa de alocação, Esforço total (horas), Total issues, Status
- **Donut chart:** Distribuição de esforço por projeto
- **Timeline (8 semanas):** Evolução da taxa de alocação com linhas de threshold
- **Tabela de issues:** Por projeto, com filtro de status, link para Jira

#### 6.2 Modo Time (time selecionado)
- Renderiza todos os profissionais do time em seções expansíveis
- Cada seção usa o mesmo layout do modo individual

### Dados Carregados
- Busca via JQL: `assignee = "{id}"` com paginação
- Agrupa por projeto automaticamente
- Cache: 1 hora

---

## 7. Aba: Relatórios

### Filtros
- Projetos (multiselect)
- Quarter (Q1-Q4) — preenche datas automaticamente
- Ano
- Data início / fim
- Tipo de issue, Status, Time (filtros secundários)
- Botões: Consultar / Limpar

### Sub-abas

#### 7.1 Análise
- **Distribuição por Tipo** — Tabela com totais
- **Distribuição por Responsável** — Tabela clicável (abre dialog com issues da pessoa)
- **Distribuição por Time** — Tabela com totais
- **Distribuição por Status** — Tabela com totais

#### 7.2 Classificação Suporte vs Desenvolvimento
- **Análise de palavras-chave:** Identifica padrões nos títulos
  - Palavras de suporte: suporte, correção, bug, erro, fix, ajuste, hotfix, manutenção, configurar, liberar, monitorar...
  - Palavras de desenvolvimento: criar, novo, implementar, feature, melhoria, refatorar, api, integração, tela...
- **Classificação automática:** Pontua cada issue e classifica
- **Métricas:** Count de Suporte/Operação, Desenvolvimento, Indefinido
- **Tabela filtrada:** Issues classificadas com exportação CSV

#### 7.3 Análise com IA
- **Seleção de provedor:** OpenAI ou Gemini (detecta API keys disponíveis)
- **Prompts pré-definidos:**
  - Classificar Suporte vs Desenvolvimento
  - Identificar Padrões e Agrupamentos
  - Análise de Produtividade
  - Prompt Livre
- **Controle de volume:** Slider (10-500 issues)
- **Resultado:** Markdown renderizado + exportação .md

#### 7.4 Dados Completos
- Tabela com todos os campos calculados
- Exportação CSV completa

### OKRs do Relatório
- Mapeamento de atividades de suporte (meta: 100%)
- Migração de suporte para operações (meta: 50%)

---

## 8. Aba: Times

### Componentes
- **Métricas resumo:** Total times, Total membros, Total tech leaders
- **Busca:** Campo de texto para buscar profissionais
- **Lista de times:** Cards expansíveis
  - Nome do time
  - Tech Leader
  - Tabela de membros (nome, função)
  - Count de membros

### Dados
- Carregado de `times.json` (criptografado) via `teams_loader.py`

---

## 9. Sistema de OKRs

### Configuração (`src/config/okrs.json`)
```json
{
  "quarter": "Q2 2026",
  "objective": "...",
  "key_results": [{
    "id": "kr1",
    "description": "...",
    "metric": "lead_time_avg",
    "target": 15,
    "unit": "dias",
    "direction": "decrease | increase | target_range",
    "tab": "cycle | project | report"
  }]
}
```

### Métricas rastreadas
| ID | Descrição | Meta | Aba |
|----|-----------|------|-----|
| kr1 | Lead time médio | ≤ 15 dias | Ciclo |
| kr2 | Taxa de conclusão | ≥ 80% | Ciclo |
| kr3 | Issues em handoff | ≤ 10% | Ciclo |
| kr4 | Mapeamento de suporte | 100% | Relatório |
| kr5 | Migração de suporte | 50% | Relatório |
| kr6 | Membros sobrecarregados | 0 | Projeto |
| kr7 | Taxa média alocação | 70-90% | Projeto |

### Renderização
- Progress bar visual com cor (verde/amarelo/vermelho)
- Mostra valor atual vs meta

---

## 10. T-Shirt Size (Sistema de Estimativa)

Substitui story points por tamanhos de camiseta:

| Tamanho | Horas estimadas | Descrição |
|---------|-----------------|-----------|
| PP (XS) | 2.5h | 1-4 horas |
| P (S) | 6h | 0.5-1 dia |
| M | 16h | 1-3 dias |
| G (L) | 32h | 3-5 dias |
| GG (XL) | 60h | 1-2 semanas |
| XGG (XXL) | 100h | 2+ semanas |

**Campo Jira:** `customfield_10016` (Story Points / T-Shirt Size)  
**Lógica:** Se `t_shirt_size` definido, calcula `story_points` automaticamente em horas.

---

## 11. Integração Jira

### Autenticação
- **Cloud:** Basic Auth (email + API Token)
- **Server/DC:** Bearer Token (PAT)

### Endpoints utilizados
- `GET /rest/api/3/search/jql` — Busca issues com paginação (nextPageToken)
- `GET /rest/api/3/project` — Lista projetos
- `GET /rest/agile/1.0/board` — Lista boards
- `GET /rest/agile/1.0/board/{id}/sprint` — Lista sprints
- `GET /rest/agile/1.0/board/{id}/issue` — Issues do board (cross-project)

### Campos buscados
```
summary, status, assignee, issuetype, created, updated, resolutiondate,
labels, components, customfield_10370 (status category change),
customfield_10016 (story points / t-shirt), customfield_10026 (?),
customfield_11891 (?), statuscategorychangedate
```

### Resiliência
- Retry com backoff exponencial (1s, 2s, 4s) para HTTP 429
- Suporte a proxy (HTTP_PROXY, HTTPS_PROXY, NO_PROXY)
- SSL verificação configurável
- Fallback para dados em cache quando API falha

---

## 12. Sistema de Cache

### Camadas
1. **MongoDB** (primário, persistente)
   - Conexão via `MONGODB_URI`
   - TTL index para expiração automática
   - Serialização pickle para objetos complexos
2. **Session State** (fallback, em memória)
   - Usado quando MongoDB não disponível
   - Perdido ao recarregar página

### TTLs
- Projetos/Sprints: 15 min (configurável via `config.yaml`)
- Profissionais/Alocações: 1 hora
- Issues: 15 min

### Invalidação
- Manual via botão na página de configuração
- Pattern-based: `CacheManager.invalidate_cache("issues_*")`

---

## 13. Inteligência Artificial

### Provedores suportados
- **OpenAI:** GPT-4o-mini, GPT-4o, GPT-3.5-turbo (fallback chain)
- **Google Gemini:** gemini-2.5-flash-lite, gemini-2.0-flash-lite, gemini-2.0-flash, gemini-2.5-flash (fallback chain)

### Funcionalidades
1. **AI Scrum Master** (tab Projeto) — Análise automática de métricas com sugestões
2. **Análise de Issues** (tab Relatório) — Classificação e identificação de padrões
3. **Prompt livre** — Usuário define a análise desejada

### Input para IA
- CSV com colunas: Chave, Tipo, Resumo, Status, Responsável, Time, Tamanho, Lead Time
- Limitado a N issues (slider, default 50)

---

## 14. Design System / Tema Visual

### Cores
| Nome | Valor | Uso |
|------|-------|-----|
| Primary Orange | `#F37021` | Destaques, botões, marca |
| Background Light | `#F5F5F5` | Fundo geral |
| Background Dark | `#1A1A1A` | Textos principais |
| Text Primary | `#1F2937` | Corpo de texto |
| Text Secondary | `#6B7280` | Labels, captions |
| Status Normal | `#22C55E` | Verde — OK |
| Status Warning | `#EAB308` | Amarelo — subutilizado |
| Status Critical | `#EF4444` | Vermelho — sobrecarregado |

### Tipografia
- Font: Inter, system-ui, sans-serif

### Charts (Plotly)
- Paleta secundária: `#1867C0, #48A9A6, #4CAF50, #FB8C00, #7C4DFF, #26A69A, #EC407A, #78909C`
- Background transparente
- Grid sutil

---

## 15. Configuração

### Arquivos
| Arquivo | Conteúdo |
|---------|----------|
| `config.yaml` | Cache TTL, thresholds, UI theme, AI settings |
| `.env` | Credenciais (Jira, MongoDB, AI, Sentry, senha) |
| `src/config/times.json.enc` | Estrutura de times (criptografado) |
| `src/config/allowed_projects.json.enc` | Projetos permitidos (criptografado) |
| `src/config/okrs.json` | Definições de OKRs |
| `.streamlit/config.toml` | Tema Streamlit |

### Variáveis de Ambiente Críticas
```
JIRA_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN
MONGODB_URI, MONGODB_DATABASE, MONGODB_CACHE_ENABLED
ENCRYPTION_KEY
ACCESS_PASSWORD, ALLOWED_IPS, VIP_EMAILS
SENTRY_DSN
OPENAI_API_KEY, GEMINI_API_KEY
AI_ENABLED
```

---

## 16. Modelos de Dados (para referência no React)

### Issue
```typescript
interface Issue {
  jiraId: string;
  key: string;
  summary: string;
  issueType: string;
  status: string;
  statusCategory: 'To Do' | 'In Progress' | 'Done';
  assigneeAccountId?: string;
  assigneeName?: string;
  projectKey?: string;
  tShirtSize?: 'PP' | 'P' | 'M' | 'G' | 'GG' | 'XGG';
  storyPoints?: number; // calculado do tShirtSize em horas
  labels: string[];
  components: string[];
  createdDate: Date;
  updatedDate?: Date;
  resolutionDate?: Date;
  startedDate?: Date;
}
```

### AllocationMetrics
```typescript
interface AllocationMetrics {
  entityId: string;
  entityName: string;
  allocationRate: number; // 0-100+
  assignedIssues: number;
  totalStoryPoints: number;
  status: 'Normal' | 'Sobrecarregado' | 'Subutilizado';
}
```

### ProfessionalAllocation
```typescript
interface ProfessionalAllocation {
  professionalId: string;
  professionalName: string;
  totalAllocationRate: number;
  totalStoryPoints: number;
  totalIssues: number;
  projectBreakdown: ProjectAllocation[];
  status: AllocationStatus;
  capacity: number;
}

interface ProjectAllocation {
  projectKey: string;
  projectName: string;
  storyPoints: number;
  issueCount: number;
  allocationPercentage: number;
  issues: Issue[];
}
```

### Filters
```typescript
interface Filters {
  projectKeys: string[];
  sprintIds: number[];
  dateRange?: { start?: Date; end?: Date };
  assignees: string[];
  issueTypes: string[];
  epicKeys: string[];
  dateMode: 'created' | 'updated' | 'resolved' | 'created_or_updated';
}
```

---

## 17. Fluxo de Dados (Arquitetura)

```
[Jira API] 
    ↓ (REST)
[JiraConnector] — retry, auth, pagination
    ↓
[CacheManager] — MongoDB + session_state
    ↓
[MetricsEngine / ProfessionalMetricsEngine] — cálculos
    ↓
[UI Components] — Streamlit + Plotly
    ↓
[Browser]
```

### Para React (sugestão de arquitetura)
```
[Jira API]
    ↓
[Backend API (Node/Python)] — auth, cache, pagination
    ↓ (REST/GraphQL)
[React Frontend]
    ├── Auth (email/senha)
    ├── React Router (tabs → routes)
    ├── Recharts/Plotly.js (gráficos)
    ├── TanStack Query (cache/state)
    └── Tailwind/MUI (design system)
```

---

## 18. Funcionalidades de Exportação

| Local | Formato | Conteúdo |
|-------|---------|----------|
| Relatório - Dados completos | CSV | Todas as issues com métricas |
| Relatório - Classificadas | CSV | Issues com classificação suporte/dev |
| Relatório - Por pessoa | CSV | Issues de um responsável |
| Relatório - Análise IA | Markdown | Resultado da análise |
| Projeto - Alocação | CSV | Métricas de alocação por membro |

---

## 19. Segurança

- Emails/IPs criptografados com Fernet (AES-128-CBC)
- Dados sensíveis (times, projetos) em arquivos `.enc`
- Senha de acesso em variável de ambiente (não hardcoded)
- Rate limiting no login (5 tentativas)
- Validação de domínio no email
- Sentry para auditoria de acessos
- PII mascarada em logs (`j***@sejaefi.com.br`, `192.168.0.***`)
