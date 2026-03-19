"""
AI Scrum Master Assistant Module.

Provides AI-powered analysis of team metrics using OpenAI GPT.
"""

import os
from typing import List, Optional
from openai import OpenAI, RateLimitError, APIError

from ..models.data_models import AllocationMetrics, ProductivityMetrics, AllocationStatus
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AIAssistant:
    """AI Assistant for analyzing team metrics and providing recommendations."""
    
    def __init__(self):
        """Initialize the AI Assistant with OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # Cost-effective model
    
    def analyze_allocation(
        self,
        allocation_metrics: List[AllocationMetrics],
        productivity_metrics: ProductivityMetrics
    ) -> str:
        """
        Analyze team allocation and productivity metrics.
        
        Args:
            allocation_metrics: List of team member allocation metrics
            productivity_metrics: Overall productivity metrics
            
        Returns:
            AI-generated analysis and recommendations in Portuguese
        """
        # Build context from metrics
        context = self._build_metrics_context(allocation_metrics, productivity_metrics)
        
        prompt = f"""Você é um Scrum Master experiente analisando métricas de um time de desenvolvimento.

## Dados do Time:
{context}

## Sua Tarefa:
Analise os dados acima e forneça:

1. **Resumo da Situação** (2-3 frases)
2. **Pontos de Atenção** (liste os principais problemas identificados)
3. **Recomendações** (ações práticas para melhorar)
4. **Membros que precisam de atenção** (se houver sobrecarregados ou subutilizados)

Seja direto, prático e use linguagem acessível. Responda em português brasileiro."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um Scrum Master experiente que ajuda times a melhorar sua performance."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            analysis = response.choices[0].message.content
            logger.info("ai_analysis_completed", tokens_used=response.usage.total_tokens)
            return analysis
        
        except RateLimitError:
            logger.warning("ai_rate_limit_exceeded")
            return "⚠️ **Limite de requisições excedido na API da OpenAI.**\n\nSua chave de API atingiu o limite de uso. Aguarde alguns minutos e tente novamente, ou verifique sua cota em https://platform.openai.com/usage"
        
        except APIError as e:
            logger.error("ai_api_error", error=str(e))
            return f"⚠️ **Erro na API da OpenAI:** {str(e)}"
            
        except Exception as e:
            logger.error("ai_analysis_failed", error=str(e))
            return f"⚠️ **Erro ao gerar análise:** {str(e)}"
    
    def _build_metrics_context(
        self,
        allocation_metrics: List[AllocationMetrics],
        productivity_metrics: ProductivityMetrics
    ) -> str:
        """Build a text context from metrics for the AI prompt."""
        lines = []
        
        # Team summary
        total_members = len(allocation_metrics)
        overloaded = [m for m in allocation_metrics if m.status == AllocationStatus.OVERLOADED]
        underutilized = [m for m in allocation_metrics if m.status == AllocationStatus.UNDERUTILIZED]
        normal = [m for m in allocation_metrics if m.status == AllocationStatus.NORMAL]
        
        lines.append(f"### Equipe: {total_members} membros")
        lines.append(f"- Sobrecarregados (>100%): {len(overloaded)}")
        lines.append(f"- Alocação normal (50-100%): {len(normal)}")
        lines.append(f"- Subutilizados (<50%): {len(underutilized)}")
        lines.append("")
        
        # Individual allocations
        lines.append("### Alocação Individual:")
        for m in allocation_metrics:
            status_emoji = "🔴" if m.status == AllocationStatus.OVERLOADED else "🟡" if m.status == AllocationStatus.UNDERUTILIZED else "✅"
            lines.append(f"- {status_emoji} {m.entity_name}: {m.allocation_rate:.1f}% ({m.assigned_issues} issues, {m.total_story_points:.1f} SP)")
        lines.append("")
        
        # Productivity metrics
        lines.append("### Métricas de Produtividade:")
        lines.append(f"- Throughput: {productivity_metrics.throughput} issues concluídas")
        
        if productivity_metrics.velocity:
            lines.append(f"- Velocity: {productivity_metrics.velocity:.1f} story points")
        
        if productivity_metrics.lead_time_avg_hours:
            days = productivity_metrics.lead_time_avg_hours / 24
            lines.append(f"- Lead Time Médio: {days:.1f} dias")
        
        if productivity_metrics.cycle_time_avg_hours:
            days = productivity_metrics.cycle_time_avg_hours / 24
            lines.append(f"- Cycle Time Médio: {days:.1f} dias")
        
        if productivity_metrics.completion_rate:
            lines.append(f"- Taxa de Conclusão: {productivity_metrics.completion_rate:.1f}%")
        
        return "\n".join(lines)


def get_ai_assistant() -> Optional[AIAssistant]:
    """
    Get an AI Assistant instance if configured.
    
    Returns:
        AIAssistant instance or None if not configured
    """
    try:
        return AIAssistant()
    except ValueError:
        return None
