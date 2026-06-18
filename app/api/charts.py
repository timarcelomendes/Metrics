import uuid

from fastapi import APIRouter, Depends

from app.core.security import CurrentUser, get_current_user
from app.db.mongo import get_db
from app.models.schemas import ChartPreviewRequest, ChartPreviewResponse, DashboardChartSaveRequest
from app.services.chart_service import build_chart_preview
from app.services.jira_service import get_active_client

router = APIRouter()


@router.post("/preview", response_model=ChartPreviewResponse)
def preview_chart(payload: ChartPreviewRequest, user: CurrentUser = Depends(get_current_user)):
    client = get_active_client(user.email) if payload.config.source_type == "jql" else None
    return build_chart_preview(payload.rows or [], payload.config, client)


@router.post("/save")
def save_chart(payload: DashboardChartSaveRequest, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    config = payload.config.model_dump(mode="json")
    config["id"] = config.get("id") or str(uuid.uuid4())
    user_doc = db.users.find_one({"email": user.email}) or {"email": user.email}
    layout = user_doc.get("dashboard_layout", {})
    project_layout = layout.setdefault(payload.project_key, {"active_dashboard_id": payload.dashboard_id, "dashboards": {payload.dashboard_id: {"id": payload.dashboard_id, "name": "Dashboard Principal", "tabs": {payload.tab_name: []}}}})
    dashboard = project_layout.setdefault("dashboards", {}).setdefault(payload.dashboard_id, {"id": payload.dashboard_id, "name": "Dashboard Principal", "tabs": {payload.tab_name: []}})
    tab = dashboard.setdefault("tabs", {}).setdefault(payload.tab_name, [])
    existing_index = next((idx for idx, item in enumerate(tab) if item.get("id") == config["id"]), None)
    if existing_index is None:
        tab.append(config)
    else:
        tab[existing_index] = config
    db.users.update_one({"email": user.email}, {"$set": {"dashboard_layout": layout}}, upsert=True)
    return {"message": "Gráfico salvo com sucesso.", "chart_id": config["id"]}


@router.get("/dashboard/{project_key}")
def get_dashboard(project_key: str, user: CurrentUser = Depends(get_current_user)):
    user_doc = get_db().users.find_one({"email": user.email}) or {}
    return user_doc.get("dashboard_layout", {}).get(project_key, {})
