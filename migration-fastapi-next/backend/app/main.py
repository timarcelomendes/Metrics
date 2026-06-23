from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import charts, jira
from app.core.config import settings

app = FastAPI(
    title="Gauge Metrics API",
    version="0.1.0",
    description="Backend FastAPI para migração do Gauge Metrics com foco em Jira, permissões e construtores de gráficos.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jira.router, prefix="/api/jira", tags=["Jira"])
app.include_router(charts.router, prefix="/api/charts", tags=["Charts"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
