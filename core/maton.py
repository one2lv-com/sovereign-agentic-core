"""
Maton Bridge — External Services Gateway
=========================================
Connects the Sovereign Core to real-world services via the Maton API Gateway.
Active connections: Gmail, Drive, Docs, Contacts, Meet, Search Console,
                    Workspace Admin, Play, YouTube, GitHub, Dropbox,
                    OneDrive, Firebase
"""

import json
import os
import urllib.error
import urllib.request
from typing import Optional

MATON_API_BASE = "https://api.maton.ai"

# Active connection IDs (loaded at startup)
CONNECTIONS: dict[str, str] = {
    "google-mail":              "004ea73d-ba8a-4722-aa5d-3ff7c861c9bf",
    "google-drive":             "ea5e1faa-c7b4-4821-99a0-9297874356df",
    "google-docs":              "1c732f8d-58a5-41f7-82c5-23c7a5e8db21",
    "google-contacts":          "d007612f-02ec-4b5a-a9df-8bbcd89e4f09",
    "google-meet":              "94c2e75d-80b6-4872-a4fb-5223149de90a",
    "google-search-console":    "7a942de6-f36a-4833-a7c0-7710fe586981",
    "google-workspace-admin":   "81b40862-3b05-476e-a29f-02fdc9af76a9",
    "google-play":              "d28e8680-7982-495b-9992-25d625664086",
    "youtube":                  "0bb17955-13d5-4d4f-b6cd-b919410128f9",
    "github":                   "d90fadc6-6d5d-4e53-acea-453f262b7706",
    "dropbox":                  "722c0bb3-8786-4bf4-9122-26310c43c633",
    "one-drive":                "3ca80c51-8728-4c76-bad3-2f2aba6c580b",
    "firebase":                 "003b5e86-b6ba-4b94-9ab4-4763fec5fc89",
}

# Human-readable service labels
SERVICE_LABELS: dict[str, str] = {
    "google-mail":              "Gmail",
    "google-drive":             "Google Drive",
    "google-docs":              "Google Docs",
    "google-contacts":          "Google Contacts",
    "google-meet":              "Google Meet",
    "google-search-console":    "Search Console",
    "google-workspace-admin":   "Workspace Admin",
    "google-play":              "Google Play",
    "youtube":                  "YouTube",
    "github":                   "GitHub",
    "dropbox":                  "Dropbox",
    "one-drive":                "OneDrive",
    "firebase":                 "Firebase",
}

# Native API path prefixes per service (for Hermes to build correct URLs)
API_GUIDES: dict[str, str] = {
    "google-mail":              "Gmail REST: /gmail/v1/users/me/messages, /gmail/v1/users/me/threads, /gmail/v1/users/me/labels",
    "google-drive":             "Drive REST: /drive/v3/files, /drive/v3/files/{fileId}, /drive/v3/files/{fileId}/export",
    "google-docs":              "Docs REST: /v1/documents/{documentId}",
    "google-contacts":          "People REST: /v1/people/me/connections, /v1/people:searchContacts",
    "google-meet":              "Meet REST: /v2/spaces, /v2/conferenceRecords",
    "google-search-console":    "Search Console REST: /webmasters/v3/sites, /webmasters/v3/sites/{siteUrl}/searchAnalytics/query",
    "google-workspace-admin":   "Admin REST: /admin/directory/v1/users, /admin/directory/v1/groups",
    "google-play":              "Play REST: /androidpublisher/v3/applications/{packageName}/reviews",
    "youtube":                  "YouTube Data v3: /youtube/v3/channels?part=snippet&mine=true, /youtube/v3/videos?part=snippet&myRating=like",
    "github":                   "GitHub REST: /user, /user/repos, /repos/{owner}/{repo}/issues, /repos/{owner}/{repo}/pulls",
    "dropbox":                  "Dropbox API: /2/files/list_folder (POST), /2/files/get_metadata (POST)",
    "one-drive":                "Graph REST: /v1.0/me/drive/root/children, /v1.0/me/drive/items/{item-id}",
    "firebase":                 "Firebase REST: /v1/projects, /v1/projects/{project}/databases",
}


class MatonBridge:
    """
    Gateway to 13 connected external services via Maton.
    Used by The Hermes seat to fulfill real-world data requests.
    """

    def __init__(self):
        self.api_key = os.environ.get("MATON_API_KEY", "")
        self.connections = CONNECTIONS

    def call(
        self,
        app: str,
        path: str,
        method: str = "GET",
        body: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Execute a single API call through the Maton gateway."""
        url = f"{MATON_API_BASE}/{app}{path}"
        if params:
            qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
            url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"

        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        conn_id = self.connections.get(app)
        if conn_id:
            req.add_header("Maton-Connection", conn_id)

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode()
            except Exception:
                pass
            return {"error": f"HTTP {e.code}: {e.reason}", "detail": body_text}
        except Exception as e:
            return {"error": str(e)}

    def execute_plan(self, calls: list[dict]) -> list[dict]:
        """
        Execute a list of API call plans from Hermes.
        Each call: {app, path, method, body?, description}
        Returns list of {description, result} dicts.
        """
        results = []
        for call in calls[:5]:  # hard cap at 5 calls per plan
            app = call.get("app", "")
            path = call.get("path", "")
            method = call.get("method", "GET").upper()
            body = call.get("body")
            desc = call.get("description", f"{method} {app}{path}")

            if app not in self.connections:
                results.append({"description": desc, "result": {"error": f"Unknown service: {app}"}})
                continue

            result = self.call(app, path, method, body)
            results.append({"description": desc, "result": result})

        return results

    def get_service_manifest(self) -> str:
        """Return a compact manifest of available services for Hermes's system prompt."""
        lines = []
        for app, label in SERVICE_LABELS.items():
            guide = API_GUIDES.get(app, "")
            lines.append(f"  {label} ({app}): {guide}")
        return "\n".join(lines)

    def get_status(self) -> dict:
        return {
            "connected_services": len(self.connections),
            "services": list(SERVICE_LABELS.values()),
        }
