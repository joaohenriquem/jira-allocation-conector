# Efí React Design System — Guia de Padrões (test-app)

Este documento serve como referência completa para manter a consistência visual e de código no test-app de Negativação Serasa. O projeto usa **React 18 + TypeScript + Tailwind CSS** com custom utility classes inspiradas no Design System Efí.

---

## 1. Stack Tecnológica

| Tecnologia       | Versão  | Propósito                          |
| ---------------- | ------- | ---------------------------------- |
| React            | ^18.3.1 | UI framework                       |
| TypeScript       | ^5.4.5  | Type safety                        |
| Vite             | ^5.3.1  | Build tool + dev server            |
| Tailwind CSS     | ^3.4.4  | Utility-first CSS                  |
| React Router DOM | ^6.23.1 | Roteamento SPA                     |
| Recharts         | ^3.9.0  | Gráficos (Dashboard)               |

---

## 2. Fundamentos Visuais

### 2.1 Fonte Principal

- **Red Hat Display** (importada via Google Fonts)
- Pesos: 400 (regular), 500 (medium), 800 (bold), 900 (black)
- Configurada em `tailwind.config.js` como font-family padrão

### 2.2 Base de Tamanho

```css
html {
  font-size: 16px; /* base padrão do browser */
}
body {
  font-size: 0.875rem; /* 14px — texto base */
}
```

### 2.3 Cores (CSS Custom Properties)

Definidas em `:root` no `index.css`:

| Token             | Valor     | Uso                              |
| ----------------- | --------- | -------------------------------- |
| `--efi-primary`   | `#00b4b6` | Cor principal (teal/ciano)       |
| `--efi-primary-dark` | `#009a9c` | Hover da cor principal        |
| `--efi-orange`    | `#e85d1b` | Cor da marca Efí (sidebar card)  |
| `--efi-dark`      | `#1e293b` | Elementos escuros                |
| `--efi-dark-hover`| `#334155` | Hover escuro                     |
| `--efi-bg`        | `#f8f9fa` | Background da aplicação          |
| `--efi-border`    | `#e9ecef` | Bordas padrão                    |
| `--efi-text`      | `#2d2d2d` | Texto principal                  |
| `--efi-text-muted`| `#6c757d` | Texto secundário/mutado          |

### 2.4 Cores Tailwind Customizadas

Configuradas em `tailwind.config.js`:

```js
colors: {
  efi: {
    primary: '#00b4b6',
    dark: '#1a2332',
  }
}
```

### 2.5 Paleta de Status

| Status             | Background      | Texto           | Borda           | Uso              |
| ------------------ | --------------- | --------------- | --------------- | ---------------- |
| `under_review`     | `bg-cyan-50`    | `text-cyan-700` | `border-cyan-200` | Em análise     |
| `negativated`      | `bg-green-50`   | `text-green-700`| `border-green-200`| Negativado     |
| `cancelled`        | `bg-gray-100`   | `text-gray-600` | `border-gray-300` | Cancelado      |
| `settled`          | `bg-green-50`   | `text-green-700`| `border-green-200`| Regularizado   |
| `rejected_serasa`  | `bg-red-50`     | `text-red-700`  | `border-red-200`  | Rejeitado      |
| `settlement_pending` | `bg-cyan-50`  | `text-cyan-700` | `border-cyan-200` | Pendência removida |

---

## 3. Componentes CSS Customizados (@layer components)

### 3.1 Badges de Status

```css
.badge-under-review { @apply inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-cyan-50 text-cyan-700 border border-cyan-200; }
.badge-negativated  { @apply inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200; }
.badge-cancelled    { @apply inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200; }
.badge-settled      { @apply inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200; }
.badge-rejected-serasa { @apply inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200; }
```

**Uso em JSX:**
```tsx
<span className="badge-negativated">✓ Negativado</span>
<span className="badge-under-review">◷ Solicitação em análise</span>
```

### 3.2 Botões

| Classe         | Aparência                                           | Uso                          |
| -------------- | --------------------------------------------------- | ---------------------------- |
| `btn-primary`  | Fundo `#00b4b6`, texto branco, hover `#009a9c`     | Ação principal               |
| `btn-secondary`| Borda `#00b4b6`, texto `#00b4b6`, fundo transparente| Ação secundária              |
| `btn-outline`  | Borda cinza, texto cinza, hover bg cinza claro      | Ação neutra                  |
| `btn-danger`   | Fundo vermelho, texto branco                        | Ações destrutivas            |
| `btn-link`     | Texto `#00b4b6`, sem fundo/borda, hover underline   | Links de ação                |
| `btn-link-danger` | Texto vermelho, sem fundo/borda                  | Links destrutivos            |

**Uso em JSX:**
```tsx
<button className="btn-primary">Salvar</button>
<button className="btn-secondary">Solicitar nova negativação</button>
<button className="btn-outline">Cancelar</button>
<button className="btn-danger" disabled={loading}>Excluir</button>
```

**Nota:** Em muitas páginas, botões são escritos diretamente com Tailwind inline em vez das classes utilitárias. Exemplo comum:
```tsx
<button className="bg-[#00b4b6] text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-[#009a9c] disabled:opacity-50 transition-colors">
  Filtrar
</button>
```

### 3.3 Cards

```css
.efi-card { @apply bg-white border border-gray-200 rounded-lg shadow-sm; }
```

**Uso em JSX:**
```tsx
<div className="efi-card p-6">
  <h4 className="font-bold text-gray-800 mb-3">Título</h4>
  <p className="text-sm text-gray-500">Conteúdo</p>
</div>
```

**Alternativa inline (mais comum nas páginas):**
```tsx
<div className="bg-white border rounded-lg p-5">...</div>
```

### 3.4 Inputs e Forms

| Classe       | Uso                          |
| ------------ | ---------------------------- |
| `efi-input`  | Text inputs padrão           |
| `efi-select` | Select dropdowns             |
| `efi-label`  | Labels de formulário         |

```tsx
<label className="efi-label">Nome completo</label>
<input className="efi-input" placeholder="Informe seu nome" value={name} onChange={e => setName(e.target.value)} />

<label className="efi-label">Estado</label>
<select className="efi-select" value={state} onChange={e => setState(e.target.value)}>
  <option value="">Selecione</option>
</select>
```

**Estilo inline equivalente (usado nas páginas de criação/listagem):**
```tsx
<input className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-[#00b4b6] focus:ring-1 focus:ring-[#00b4b6]/20 transition-colors" />
```

### 3.5 Alertas

```css
.alert-info    { @apply bg-cyan-50 border border-cyan-200 text-cyan-800 rounded-lg p-4 text-sm; }
.alert-success { @apply bg-green-50 border border-green-200 text-green-800 rounded-lg p-4 text-sm; }
.alert-warning { @apply bg-amber-50 border border-amber-200 text-amber-800 rounded-lg p-4 text-sm; }
.alert-danger  { @apply bg-red-50 border border-red-200 text-red-800 rounded-lg p-4 text-sm; }
```

### 3.6 Modais

```css
.modal-overlay { @apply fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50; }
.modal-content { @apply bg-white rounded-xl shadow-xl max-h-[85vh] overflow-y-auto; }
.modal-header  { @apply flex items-center justify-between px-6 py-4 border-b; }
.modal-body    { @apply px-6 py-4; }
.modal-footer  { @apply flex items-center justify-end gap-3 px-6 py-4 border-t; }
```

**Uso em JSX:**
```tsx
{showModal && (
  <div className="modal-overlay" onClick={() => setShowModal(false)}>
    <div className="modal-content max-w-lg w-full" onClick={e => e.stopPropagation()}>
      <div className="modal-header">
        <h3 className="font-bold text-lg">Título</h3>
        <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
      </div>
      <div className="modal-body">...</div>
      <div className="modal-footer">
        <button className="btn-outline">Cancelar</button>
        <button className="btn-primary">Confirmar</button>
      </div>
    </div>
  </div>
)}
```

### 3.7 Loading Spinner

```css
.loading-spinner { @apply inline-block w-6 h-6 border-[3px] border-gray-200 border-t-[#00b4b6] rounded-full animate-spin; }
.loading-container { @apply flex flex-col items-center justify-center py-16 gap-3 text-gray-400 text-sm; }
```

**Uso inline (padrão nas páginas):**
```tsx
<div className="flex items-center justify-center py-16 gap-3 text-gray-500">
  <div className="animate-spin rounded-full h-5 w-5 border-2 border-gray-300 border-t-[#00b4b6]"></div>
  <span>Carregando...</span>
</div>
```

---

## 4. Layout da Aplicação

### 4.1 Estrutura Geral

```
┌──────────────────────────────────────────────────────┐
│  Header (h=52px, fixed, z-50)                        │
├────────┬─────────────────────────────────────────────┤
│        │                                             │
│ Sidebar│   Main Content                              │
│ (fixed)│   (pt-76px, p-6, bg-[var(--efi-bg)])       │
│        │                                             │
│ w=64px │                                             │
│ ou     │                                             │
│ w=260px│                                             │
└────────┴─────────────────────────────────────────────┘
```

### 4.2 Header

- Altura: `52px` fixa
- Background: branco com borda inferior `var(--efi-border)`
- Contém: logo Efí à esquerda, botão hamburger à direita
- z-index: 50

### 4.3 Sidebar

- **Colapsada:** `w-[64px]` — mostra apenas ícones
- **Expandida:** `w-[260px]` — mostra ícones + labels
- Background: branco com borda direita
- Transição: `transition-all duration-200`
- Contém:
  - Card de conta (laranja, estilo Efí Pro)
  - Navegação com itens ativos marcados por `border-l-[3px] border-l-[var(--efi-primary)]`

### 4.4 Main Content

- Margem à esquerda acompanha a sidebar (`ml-[64px]` ou `ml-[260px]`)
- Padding top: `76px` (52px header + 24px espaço)
- Padding geral: `24px` (p-6)
- Background: `var(--efi-bg)` (#f8f9fa)

---

## 5. Padrões de Página

### 5.1 Cabeçalho de Página

```tsx
// Breadcrumb + Título + Ação
<div className="flex items-center justify-between mb-1">
  <p className="text-xs text-gray-400">Receber › Negativações Serasa</p>
</div>
<div className="flex items-center justify-between mb-6">
  <h2 className="text-2xl font-bold text-gray-800">Título da Página</h2>
  <button className="btn-secondary">
    <span>👤</span> Ação principal
  </button>
</div>
```

### 5.2 Card de Filtros

```tsx
<div className="bg-white border rounded-lg p-4 mb-5">
  <div className="flex gap-3 items-end">
    <div className="flex-[2]">
      <label className="block text-xs text-gray-500 mb-1">Buscar por</label>
      <input className="w-full border border-gray-300 rounded-lg pl-9 pr-3 py-2.5 text-sm placeholder-gray-400 focus:outline-none focus:border-[#00b4b6]" />
    </div>
    <div>
      <button className="btn-primary">Filtrar</button>
    </div>
  </div>
</div>
```

### 5.3 Tabela de Dados

```tsx
<div className="bg-white border rounded-lg overflow-visible">
  {/* Pagination top */}
  <div className="flex items-center justify-between px-5 py-3 border-b text-sm text-gray-500">
    <select className="border border-gray-200 rounded px-2 py-1 text-xs">...</select>
    <div className="flex items-center gap-3 text-xs">
      <button>‹ Anterior</button>
      <span className="bg-gray-100 text-gray-700 px-2.5 py-1 rounded font-medium">{page}</span>
      <button>Próxima ›</button>
    </div>
  </div>

  {/* Table */}
  <table className="w-full text-sm">
    <thead>
      <tr className="border-b text-left text-xs text-gray-500 font-medium">
        <th className="px-5 py-3">Coluna ↕</th>
      </tr>
    </thead>
    <tbody>
      <tr className="border-b hover:bg-gray-50/50 transition-colors">
        <td className="px-5 py-3.5 font-medium text-gray-800">Valor</td>
      </tr>
    </tbody>
  </table>
</div>
```

### 5.4 KPI Cards (Dashboard)

```tsx
<div className="grid grid-cols-4 gap-4 mb-6">
  <div className="bg-white border rounded-lg p-4">
    <p className="text-xs text-gray-500">Label do KPI</p>
    <p className="text-2xl font-bold text-gray-800">{valor}</p>
  </div>
</div>
```

### 5.5 Gráficos (Dashboard)

```tsx
<div className="bg-white border rounded-lg p-5">
  <h3 className="font-bold text-gray-800 mb-4">Título do gráfico</h3>
  <ResponsiveContainer width="100%" height={220}>
    <BarChart data={data}>
      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
      <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
      <Tooltip />
      <Legend wrapperStyle={{ fontSize: 11 }} />
      <Bar dataKey="total" fill="#64748b" radius={[3, 3, 0, 0]} />
    </BarChart>
  </ResponsiveContainer>
</div>
```

---

## 6. Componentes React do Projeto

### 6.1 Toast (notificações)

```tsx
import { useToast } from '../Toast'

const toast = useToast()

// Sucesso (verde)
toast.show('Operação concluída com sucesso')

// Erro (vermelho)
toast.show('Falha ao processar', 'error')

// Info (teal)
toast.show('Informação importante', 'info')
```

- Auto-dismiss após 4 segundos
- Posição: topo direito (`fixed top-16 right-4 z-[100]`)
- Animação: `animate-slide-in`

### 6.2 Modal de Feedback (sucesso/erro)

Implementado inline em cada página (sem componente reutilizável). Padrão:

```tsx
{modal === 'success' && (
  <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
    <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-8 text-center relative">
      <button onClick={() => setModal('none')} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 text-xl">×</button>
      {/* Ícone */}
      <div className="mx-auto w-16 h-16 rounded-full border-2 border-gray-400 flex items-center justify-center mb-6">
        <span className="text-gray-500 text-2xl font-serif">i</span>
      </div>
      <h3 className="text-xl font-bold text-gray-800 mb-4">Título</h3>
      <p className="text-sm text-gray-600 mb-6">Mensagem descritiva.</p>
      <button className="bg-gray-800 text-white px-8 py-3 rounded-lg text-sm font-medium hover:bg-gray-900">
        Entendi
      </button>
    </div>
  </div>
)}
```

### 6.3 Toggle Switch (customizado)

```tsx
<button onClick={() => setEnabled(!enabled)}
  className={`relative w-11 h-6 rounded-full transition-colors ${enabled ? 'bg-[#00b4b6]' : 'bg-gray-300'}`}>
  <span className="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform"
    style={{ transform: enabled ? 'translateX(22px)' : 'translateX(0)' }} />
</button>
```

---

## 7. Breakpoints (Tailwind padrão)

| Breakpoint | Largura mín. | Uso                |
| ---------- | ------------ | ------------------ |
| `sm`       | 640px        | Mobile landscape   |
| `md`       | 768px        | Tablet             |
| `lg`       | 1024px       | Desktop            |
| `xl`       | 1280px       | Desktop wide       |
| `2xl`      | 1536px       | Ultra-wide         |

---

## 8. Padrões de Código

### 8.1 Estrutura de Arquivo de Página

```tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFunction } from '../api'
import { useToast } from '../Toast'

export default function PageName() {
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    const res = await apiFunction()
    if (res.ok) setData(res.data)
    setLoading(false)
  }

  return (
    <div>
      {/* Header */}
      {/* Filtros */}
      {/* Loading state */}
      {/* Conteúdo */}
      {/* Modais */}
    </div>
  )
}
```

### 8.2 Convenções

| Aspecto              | Padrão                                           |
| -------------------- | ------------------------------------------------ |
| Exportação           | `export default function`                        |
| State                | React hooks (`useState`, `useEffect`)            |
| Tipagem              | `any` para dados da API (app de teste)           |
| Requests             | Via `../api.ts` (wrapper sobre `fetch`)           |
| Roteamento           | React Router v6 (`useNavigate`, `useParams`)     |
| Notificações         | `useToast()` hook                                |
| Autenticação         | `localStorage` (JWT, accountNumber, accountCode) |
| Formatação monetária | `(cents / 100).toLocaleString('pt-BR', {...})`   |
| Formatação doc       | Máscara CPF/CNPJ manual                          |
| Formatação data      | `new Date(str).toLocaleDateString('pt-BR')`      |

### 8.3 API Client (`src/api.ts`)

```tsx
// Todas as funções retornam { status, data, ok }
const res = await createNegativacao(body)
if (res.ok) {
  toast.show('Sucesso!')
} else {
  toast.show(`Erro HTTP ${res.status}: ${res.data?.errors?.[0]?.message}`, 'error')
}
```

Headers automáticos:
- `Authorization: Bearer {jwt}` (se JWT presente)
- `x-account-number: {accountNumber}` (preferencial)
- `x-account-code: {accountCode}` (fallback)
- `Content-Type: application/json`

### 8.4 Tratamento de Erros

```tsx
// Padrão de exibição de erro da API
{result?.data?.errors?.[0]?.friendly_message || result?.data?.errors?.[0]?.message || 'Erro desconhecido'}

// Detalhes para debugging
<details className="mb-4 text-left">
  <summary className="text-xs text-gray-400 cursor-pointer">Detalhes do erro</summary>
  <pre className="mt-2 text-xs bg-gray-50 p-3 rounded overflow-x-auto">
    {JSON.stringify(result.data, null, 2)}
  </pre>
</details>
```

---

## 9. Rotas da Aplicação

| Rota              | Componente         | Descrição                          |
| ----------------- | ------------------ | ---------------------------------- |
| `/`               | Dashboard          | KPIs e gráficos                    |
| `/create`         | CreateNegativacao  | Formulário de nova negativação     |
| `/list`           | ListNegativacoes   | Tabela + detalhe N2 em modal       |
| `/debtors`        | Debtors            | Lista de devedores                 |
| `/debtors/:doc`   | DebtorDetail       | Histórico detalhado por devedor    |
| `/webhook`        | SimulateWebhook    | Envio de webhooks de teste         |
| `/settings`       | Settings           | Configuração de autenticação       |

---

## 10. Animações

```css
@keyframes slide-in {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
.animate-slide-in { animation: slide-in 0.3s ease-out; }
```

Usada nos Toasts. Demais animações via Tailwind (`transition-colors`, `transition-all duration-200`, `animate-spin`).

---

## 11. Ícones

O projeto **não usa** uma biblioteca de ícones. Ícones são representados por:
- **Emojis** para navegação e feedback visual: `📊`, `➕`, `📋`, `🔔`, `⚙️`, `💬`, `🏦`
- **SVGs inline** para ações específicas (busca, calendário, detalhes)
- **Caracteres Unicode** para badges de status: `◷`, `✓`, `✕`, `⚠`, `•`

---

## 12. Checklist de Nova Página

Ao criar uma nova página no test-app:

- [ ] Arquivo em `src/pages/NomeDaPagina.tsx`
- [ ] Export default function (não arrow function)
- [ ] Importar `useToast` para feedback ao usuário
- [ ] Importar funções necessárias de `../api`
- [ ] Adicionar rota em `App.tsx`
- [ ] Adicionar item de navegação em `navItems` (se aplicável)
- [ ] Implementar estado de loading com spinner Efí
- [ ] Implementar tratamento de erros com toast ou modal
- [ ] Seguir padrão de header (breadcrumb + título + ação)
- [ ] Usar paleta de cores via CSS variables ou Tailwind colors
- [ ] Garantir `transition-colors` em elementos interativos

---

## 13. Relação com o Design System Efí Original (Vue)

Este test-app é uma **reimplementação simplificada** dos padrões visuais do Efí Bank Pro para fins de teste da API de Negativação. As correspondências com o DS original:

| Conceito DS Original   | Implementação no test-app            |
| ---------------------- | ------------------------------------ |
| `@efi/components`     | Classes Tailwind + CSS custom        |
| `GBtn`                | `btn-primary`, `btn-secondary`, etc. |
| `GCard`               | `efi-card` ou `bg-white border rounded-lg` |
| `GTextField`          | `efi-input`                          |
| `GChip` (status)      | `badge-{status}`                     |
| `GModalAction`        | Modal inline com `modal-overlay`     |
| `GDataTable`          | `<table>` com Tailwind              |
| `GAlert`              | `alert-{kind}`                       |
| `GTooltip`            | Atributo `title` nativo              |
| `GSkeleton`           | Loading spinner simples              |
| ThemeProvider          | CSS variables no `:root`             |
| Ícones `gerencianet-icons` | Emojis + SVG inline           |

---

## 14. Referência Rápida de Classes Mais Usadas

```tsx
// Cards e containers
"bg-white border rounded-lg p-4"
"bg-white border rounded-lg p-5"
"bg-white border rounded-lg p-8"

// Textos
"text-2xl font-bold text-gray-800"     // Títulos
"text-sm text-gray-500"                 // Descrições
"text-xs text-gray-400"                 // Labels/Captions
"text-sm font-medium text-gray-800"     // Texto enfatizado
"font-mono text-xs"                     // Códigos/IDs

// Botões inline
"bg-[#00b4b6] text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-[#009a9c] disabled:opacity-50 transition-colors"
"border border-gray-300 rounded-lg px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50"
"bg-gray-800 text-white px-8 py-3 rounded-lg text-sm font-medium hover:bg-gray-900"

// Inputs inline
"w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-[#00b4b6] focus:ring-1 focus:ring-[#00b4b6]/20"

// Status badges inline
"inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border"

// Grid layouts
"grid grid-cols-2 gap-4"
"grid grid-cols-4 gap-4"
"flex gap-3 items-end"
"d-flex flex-column gap-4" // ← NÃO usar (Bootstrap), preferir Tailwind

// Espaçamento padrão
"mb-6"   // Entre seções
"mb-4"   // Entre elementos dentro de seção
"gap-3"  // Entre itens em flex/grid
"px-5 py-3"  // Padding de células de tabela
```
