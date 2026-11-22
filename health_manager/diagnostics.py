"""Local diagnostics contain only exception types, numeric codes and code locations."""
import json
import platform
import tempfile
import traceback
from pathlib import Path


def describe_error(error):
    return {"type": type(error).__name__, "errno": getattr(error, "errno", None),
            "winerror": getattr(error, "winerror", None),
            "frames": [{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                       for f in traceback.extract_tb(error.__traceback__)]}


def write_error(path, error):
    try:
        Path(path).write_text(json.dumps(describe_error(error), ensure_ascii=True, indent=2), encoding="utf-8")
    except OSError:
        pass


def run(path):
    from . import ai
    from .secrets import save_key, load_key
    import ssl
    import urllib.request
    checks = {}
    for name, check in [("tls_context", ssl.create_default_context),
                        ("proxy_discovery", urllib.request.getproxies)]:
        try:
            check()
            checks[name] = {"ok": True}
        except Exception as error:
            checks[name] = {"ok": False, **describe_error(error)}
    try:
        with tempfile.TemporaryDirectory() as folder:
            secret = Path(folder) / "api.secret"
            save_key(secret, "synthetic-diagnostic-key")
            assert load_key(secret) == "synthetic-diagnostic-key"
        checks["key_storage"] = {"ok": True}
    except Exception as error:
        checks["key_storage"] = {"ok": False, **describe_error(error)}
    try:
        ai.request_json("sk-synthetic-invalid-key", "Return json", "connection diagnostic")
        checks["api_transport"] = {"ok": False, "reason": "unexpected_response"}
    except ai.AIError as error:
        # A deliberately invalid key must receive the handled HTTP 401 response.
        checks["api_transport"] = {"ok": str(error) == "密钥无效，请检查 API Key", **describe_error(error)}
    except Exception as error:
        checks["api_transport"] = {"ok": False, **describe_error(error)}
    Path(path).write_text(json.dumps({"python": platform.python_version(), "checks": checks}, indent=2), encoding="utf-8")
