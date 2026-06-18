from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import CurrentUser, get_current_user
from app.models.schemas import (
    ActivateConnectionRequest,
    JiraConnectionCreate,
    JiraConnectionOut,
    JqlCountRequest,
    ProjectDataRequest,
)
from app.services.jira_service import (
    activate_connection,
    get_active_client,
    get_jira_fields,
    get_jql_issue_count,
    get_project_issues,
    get_projects,
    issues_to_rows,
    list_user_connections,
    save_connection,
)

router = APIRouter()


@router.get("/connections", response_model=list[JiraConnectionOut])
def list_connections(user: CurrentUser = Depends(get_current_user)):
    return list_user_connections(user.email)


@router.post("/connections")
def create_connection(payload: JiraConnectionCreate, user: CurrentUser = Depends(get_current_user)):
    connection = save_connection(user.email, payload)
    return {
        "id": connection["id"],
        "name": connection["name"],
        "jira_url": connection["jira_url"],
        "jira_email": connection["jira_email"],
        "active": False,
    }


@router.post("/connections/activate")
def activate(payload: ActivateConnectionRequest, user: CurrentUser = Depends(get_current_user)):
    return activate_connection(user.email, payload.connection_id)


@router.get("/projects")
def projects(user: CurrentUser = Depends(get_current_user)):
    client = get_active_client(user.email)
    return get_projects(client)


@router.get("/fields")
def fields(user: CurrentUser = Depends(get_current_user)):
    client = get_active_client(user.email)
    return get_jira_fields(client)


@router.post("/project-data")
def project_data(payload: ProjectDataRequest, user: CurrentUser = Depends(get_current_user)):
    client = get_active_client(user.email)
    fields_catalog = get_jira_fields(client)
    issues = get_project_issues(
        client,
        project_key=payload.project_key,
        jql_filter=payload.jql_filter,
        standard_fields=payload.standard_fields,
        custom_fields=payload.custom_fields,
    )
    return {
        "project_key": payload.project_key,
        "total": len(issues),
        "rows": issues_to_rows(issues, fields_catalog),
        "fields": fields_catalog,
    }


@router.post("/jql/count")
def jql_count(payload: JqlCountRequest, user: CurrentUser = Depends(get_current_user)):
    client = get_active_client(user.email)
    try:
        return {"count": get_jql_issue_count(client, payload.jql)}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Erro na JQL: {exc}") from exc
