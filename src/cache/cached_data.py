"""
Cached Data Functions using @st.cache_data.

This module provides cached functions for Jira data that are shared
across all users in Streamlit Cloud.
"""

import streamlit as st
from datetime import timedelta
from typing import List, Optional, Dict, Any

# TTL padrão de 1 hora
DEFAULT_TTL = timedelta(hours=1)


def get_all_projects_cached(connector: Any, base_url: str) -> List[Any]:
    """
    Busca todos os projetos do Jira usando cache interno.
    """
    cache_key = f"cached_projects_{base_url}"
    
    if cache_key not in st.session_state:
        st.session_state[cache_key] = {
            "data": None,
            "timestamp": None
        }
    
    cache = st.session_state[cache_key]
    now = __import__('datetime').datetime.now()
    
    # Verificar se cache é válido (1 hora)
    if cache["data"] is not None and cache["timestamp"] is not None:
        age = (now - cache["timestamp"]).total_seconds()
        if age < 3600:  # 1 hora
            return cache["data"]
    
    # Buscar dados frescos
    data = connector.get_all_projects()
    cache["data"] = data
    cache["timestamp"] = now
    
    return data


def get_all_professionals_cached(
    connector: Any,
    project_keys: List[str],
    default_capacity: float,
    base_url: str,
    date_range: Optional[Any] = None
) -> List[Any]:
    """
    Busca todos os profissionais usando cache interno.
    """
    from src.metrics.professional_metrics import ProfessionalMetricsEngine
    from src.cache.cache_manager import CacheManager
    
    # Include date range in cache key
    date_key = ""
    if date_range:
        start_str = date_range.start.strftime("%Y%m%d") if date_range.start else ""
        end_str = date_range.end.strftime("%Y%m%d") if date_range.end else ""
        date_key = f"_{start_str}_{end_str}"
    
    cache_key = f"cached_professionals_{base_url}{date_key}"
    
    if cache_key not in st.session_state:
        st.session_state[cache_key] = {
            "data": None,
            "timestamp": None
        }
    
    cache = st.session_state[cache_key]
    now = __import__('datetime').datetime.now()
    
    # Verificar se cache é válido (1 hora)
    if cache["data"] is not None and cache["timestamp"] is not None:
        age = (now - cache["timestamp"]).total_seconds()
        if age < 3600:  # 1 hora
            return cache["data"]
    
    # Buscar dados frescos
    engine = ProfessionalMetricsEngine(
        connector=connector,
        cache=CacheManager,
        default_capacity=default_capacity,
        date_range=date_range
    )
    data = engine.get_all_professionals(project_keys=project_keys)
    cache["data"] = data
    cache["timestamp"] = now
    
    return data


def clear_all_caches():
    """Limpa todos os caches."""
    keys_to_remove = [k for k in st.session_state.keys() if k.startswith("cached_")]
    for key in keys_to_remove:
        del st.session_state[key]


def clear_professionals_cache():
    """Limpa apenas o cache de profissionais."""
    keys_to_remove = [k for k in st.session_state.keys() if k.startswith("cached_professionals_")]
    for key in keys_to_remove:
        del st.session_state[key]
