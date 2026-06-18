from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from jira import JIRA, JIRAError

from app.db.mongo import get_db
from app.models.schemas import JiraConnectionCreate

STANDARD_FIELD_API_MAP = {
    "Assignee": "assignee",
    "Created": "created",
    "DueDate": "duedate",
    "IssueType": "issuetype",
    "Labels": "labels",
    "Parent": "parent",
    "Priority": "priority",
    "Project": "project",
    "Reporter": "reporter",
    "Resolution": "resolution",
    "Resolved": "resolutiondate",
    "Status": "status",
    "StatusCategory": "statuscategory",
    "Summary": "summary",
    "Updated": "updated",
    "timespent": "timespent",
    "timeoriginalestimate": "timeoriginalestimate",
    "timeestimate": "timeestimate",
}

DEFAULT_FIELDS = [
    "summary",
    "status",
    "issuetype",
    "created",
    "updated",
    "resolutiondate",
    "assignee",
    "reporter",
    "priority",
    "components",
    "labels",
    "project",
    "statuscategory",
    "parent",
    "timespent",
    "timeestimate",
    "timeoriginalestimate",
    "comment",
]


def normalize_standard_fields_for_api(standard_fields: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for field in standard_fields or []:
        api_field = STANDARD_FIELD_API_MAP.get(field, field)
        if api_field not in normalized:
            normalized.append(api_field)
    return normalized


def connect_to_jira(server: str, user_email: str, api_token: str) -> JIRA:
    try:
        return JIRA(options={"server": server.rstrip("/")}, basic_auth=(user_email, api_token), timeout=30)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Erro ao conectar ao Jira: {exc}") from exc


def validate_jira_connection(client: JIRA) -> tuple[bool, str]:
    try:
        client.server_info()
        return True, "Conexão validada com sucesso."
    except JIRAError as exc:
        if exc.status_code == 401:
            return False, "Falha na autenticação com o Jira. Verifique e-mail e token de API."
        if exc.status_code == 404:
            return False, "URL do Jira não encontrada. Verifique o endereço informado."
        return False, f"Erro do Jira: {exc.text}"
    except Exception as exc:
        return False, f"Erro de conexão com o Jira: {exc}"


def list_user_connections(user_email: str) -> list[dict[str, Any]]:
    user = get_db().users.find_one({"email": user_email}) or {}
    active_id = user.get("last_active_connection_id")
    output = []
    for conn in user.get("jira_connections", []):
        output.append({"id": conn["id"], "name": conn["name"], "jira_url": conn["jira_url"], "jira_email": conn["jira_email"], "active": conn["id"] == active_id})
    return output


def save_connection(user_email: str, payload: JiraConnectionCreate) -> dict[str, Any]:
    client = connect_to_jira(str(payload.jira_url), payload.jira_email, payload.api_token)
    is_valid, message = validate_jira_connection(client)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    db = get_db()
    user = db.users.find_one({"email": user_email}) or {"email": user_email, "jira_connections": []}
    connection = {
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "jira_url": str(payload.jira_url).rstrip("/"),
        "jira_email": payload.jira_email,
        "api_token_pending_encryption": payload.api_token,
    }
    connections = user.get("jira_connections", []) + [connection]
    db.users.update_one({"email": user_email}, {"$set": {"email": user_email, "jira_connections": connections}}, upsert=True)
    return {**connection, "api_token_pending_encryption": None, "active": False}


def get_connection(user_email: str, connection_id: str | None = None) -> dict[str, Any]:
    user = get_db().users.find_one({"email": user_email}) or {}
    target_id = connection_id or user.get("last_active_connection_id")
    for conn in user.get("jira_connections", []):
        if conn.get("id") == target_id:
            return conn
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão Jira não encontrada ou não ativa.")


def activate_connection(user_email: str, connection_id: str) -> dict[str, str]:
    conn = get_connection(user_email, connection_id)
    client = connect_to_jira(conn["jira_url"], conn["jira_email"], conn.get("api_token_pending_encryption") or "")
    is_valid, message = validate_jira_connection(client)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    get_db().users.update_one({"email": user_email}, {"$set": {"last_active_connection_id": connection_id}}, upsert=True)
    return {"message": "Conexão ativada com sucesso."}


def get_active_client(user_email: str) -> JIRA:
    conn = get_connection(user_email)
    return connect_to_jira(conn["jira_url"], conn["jira_email"], conn.get("api_token_pending_encryption") or "")


def get_projects(client: JIRA) -> list[dict[str, str]]:
    return [{"name": project.name, "key": project.key} for project in client.projects()]


def get_jira_fields(client: JIRA) -> list[dict[str, Any]]:
    return [{"id": field.get("id"), "name": field.get("name"), "custom": bool(field.get("custom")), "type": field.get("schema", {}).get("type", "string")} for field in client.fields()]


def get_jql_issue_count(client: JIRA, jql: str) -> int:
    if not jql:
        return 0
    result = client.search_issues(jql, maxResults=0)
    return int(result.total)


def get_project_issues(client: JIRA, project_key: str, jql_filter: str | None = None, standard_fields: list[str] | None = None, custom_fields: list[str] | None = None) -> list[Any]:
    jql = f"project = '{project_key}'"
    if jql_filter:
        jql += f" AND {jql_filter}"
    final_fields = list(set(DEFAULT_FIELDS + normalize_standard_fields_for_api(standard_fields) + (custom_fields or [])))
    return client.search_issues(jql, fields=final_fields, maxResults=False, expand="changelog")


def _extract_value(raw_value: Any) -> Any:
    if raw_value is None:
        return None
    if isinstance(raw_value, (str, int, float, bool)):
        return raw_value
    if isinstance(raw_value, list):
        return ", ".join(str(_extract_value(item)) for item in raw_value if item is not None)
    for attr in ("displayName", "name", "value", "key"):
        if hasattr(raw_value, attr):
            return getattr(raw_value, attr)
    return str(raw_value)


def issues_to_rows(issues: list[Any], field_catalog: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    field_name_by_id = {field["id"]: field["name"] for field in field_catalog or [] if field.get("id")}
    rows = []
    for issue in issues:
        fields = getattr(issue, "fields", None)
        raw_fields = getattr(issue, "raw", {}).get("fields", {})
        row = {"Key": getattr(issue, "key", None)}
        for field_id, raw_value in raw_fields.items():
            name = field_name_by_id.get(field_id, field_id)
            value = getattr(fields, field_id, raw_value) if fields else raw_value
            row[name] = _extract_value(value)
        rows.append(row)
    return rows
