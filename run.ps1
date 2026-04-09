# Jira Allocation Connector - Script de Execução
Write-Host "Iniciando Jira Allocation Connector..." -ForegroundColor Green
Write-Host "Limpando cache..." -ForegroundColor Yellow
python -c "from src.cache.cache_manager import CacheManager; CacheManager.clear_all(); print('Cache limpo!')"
python -m streamlit run app.py
