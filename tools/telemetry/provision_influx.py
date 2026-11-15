"""Provision only a bucket-write token; never print credentials or rotate existing state."""
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from tools.session.native import ROOT


def environment():
    # Existing deployment file uses literal NAME=value entries, optionally quoted.
    result = {}
    for line in Path("/opt/lab-kimia-suhu/.env").read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            result[name.strip()] = value
    return result


def admin_request(path, data=None):
    env = environment()
    headers = {"Authorization": "Token " + env["INFLUX_TOKEN"], "Content-Type": "application/json"}
    with urlopen(Request("http://127.0.0.1:8086" + path, headers=headers,
                         data=None if data is None else json.dumps(data).encode()), timeout=5) as response:
        return json.load(response)


def main():
    os.umask(0o077)
    folder = ROOT / "evidence/local/session-private"
    folder.mkdir(parents=True, exist_ok=True); folder.chmod(0o700)
    path = folder / "influx.json"
    buckets = admin_request("/api/v2/buckets?" + urlencode({"org": "lab-kimia", "name": "telemetry"}))["buckets"]
    if len(buckets) != 1:
        raise RuntimeError("Expected one initialized telemetry bucket; no implicit bucket creation")
    bucket = buckets[0]
    permission = {"action": "write", "resource": {"type": "buckets", "id": bucket["id"], "orgID": bucket["orgID"]}}
    if path.exists():
        stored = json.loads(path.read_text())
        authorization = admin_request("/api/v2/authorizations/" + stored["authorization_id"])
        permissions = authorization.get("permissions", [])
        if (stored.get("bucket_id") != bucket["id"] or authorization.get("status") != "active" or
                len(permissions) != 1 or permissions[0].get("action") != "write" or
                any(permissions[0].get("resource", {}).get(key) != value for key, value in permission["resource"].items())):
            raise RuntimeError("Existing authorization differs; refusing implicit rotation/expanded access")
    else:
        authorization = admin_request("/api/v2/authorizations", {"orgID": bucket["orgID"],
                      "description": "lab-kimia PQC receiver telemetry write only", "permissions": [permission]})
        path.write_text(json.dumps({"url": "http://127.0.0.1:8086", "org": "lab-kimia", "bucket": "telemetry",
                       "bucket_id": bucket["id"], "authorization_id": authorization["id"], "token": authorization["token"]}) + "\n")
    path.chmod(0o600)
    print(json.dumps({"configured": True, "write_only": True, "bucket": "telemetry", "token_printed": False}))


if __name__ == "__main__":
    main()
