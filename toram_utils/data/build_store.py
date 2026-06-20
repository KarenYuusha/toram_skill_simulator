from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toram_utils.data.supabase_client import SupabaseConfigError, authenticated_supabase_client, current_user_id
from toram_utils.paths import ROOT


BUILD_STORE_PATH = ROOT / "data" / "saved_builds.json"


def empty_user_record() -> dict[str, Any]:
    return {"builds": [], "preferences": {}}


def load_build_store() -> dict[str, dict[str, Any]]:
    if not BUILD_STORE_PATH.exists():
        return {}
    try:
        data = json.loads(BUILD_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    store: dict[str, dict[str, Any]] = {}
    for user, value in data.items():
        if isinstance(value, list):
            store[str(user)] = {"builds": value, "preferences": {}}
        elif isinstance(value, dict):
            store[str(user)] = {
                "builds": value.get("builds") if isinstance(value.get("builds"), list) else [],
                "preferences": value.get("preferences") if isinstance(value.get("preferences"), dict) else {},
            }
    return store


def save_build_store(store: dict[str, dict[str, Any]]) -> None:
    BUILD_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUILD_STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_user_builds(username: str) -> list[dict[str, Any]]:
    user_id = current_user_id()
    if user_id:
        try:
            response = (
                authenticated_supabase_client()
                .table("saved_builds")
                .select("name,description,build,settings")
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .execute()
            )
            return [
                {
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "build": item.get("build", {}),
                    "settings": item.get("settings", {}),
                }
                for item in (response.data or [])
            ]
        except SupabaseConfigError:
            pass
    return list(load_build_store().get(username, empty_user_record()).get("builds", []))


def save_user_builds(username: str, builds: list[dict[str, Any]]) -> None:
    user_id = current_user_id()
    if user_id:
        try:
            client = authenticated_supabase_client()
            names = [build["name"] for build in builds]
            existing = client.table("saved_builds").select("name").eq("user_id", user_id).execute().data or []
            for item in existing:
                if item.get("name") not in names:
                    client.table("saved_builds").delete().eq("user_id", user_id).eq("name", item.get("name")).execute()
            for build in builds:
                client.table("saved_builds").upsert(
                    {
                        "user_id": user_id,
                        "name": build["name"],
                        "description": build.get("description", ""),
                        "build": build.get("build", {}),
                        "settings": build.get("settings", {}),
                    },
                    on_conflict="user_id,name",
                ).execute()
            return
        except SupabaseConfigError:
            pass
    store = load_build_store()
    record = store.setdefault(username, empty_user_record())
    record["builds"] = builds
    save_build_store(store)


def load_user_preferences(username: str) -> dict[str, Any]:
    user_id = current_user_id()
    if user_id:
        try:
            response = authenticated_supabase_client().table("profiles").select("preferences").eq("id", user_id).maybe_single().execute()
            if isinstance(response.data, dict) and isinstance(response.data.get("preferences"), dict):
                return dict(response.data["preferences"])
            return {}
        except SupabaseConfigError:
            pass
    return dict(load_build_store().get(username, empty_user_record()).get("preferences", {}))


def save_user_preferences(username: str, preferences: dict[str, Any]) -> None:
    user_id = current_user_id()
    if user_id:
        try:
            authenticated_supabase_client().table("profiles").upsert(
                {"id": user_id, "username": username, "preferences": preferences},
                on_conflict="id",
            ).execute()
            return
        except SupabaseConfigError:
            pass
    store = load_build_store()
    record = store.setdefault(username, empty_user_record())
    record["preferences"] = preferences
    save_build_store(store)
