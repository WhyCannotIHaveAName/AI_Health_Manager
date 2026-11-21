"""Preserve ancillary trust material used by customized Python SSL runtimes."""
from pathlib import Path
import ssl

# This runtime's SSLContext loads this file alongside ssl.py. PyInstaller
# discovers imported modules but not this implicit data dependency. Keep the
# file unchanged; never work around the failure by disabling verification.
trust_material = Path(ssl.__file__).with_name("codex-rejected-cas.pem")
datas = [(str(trust_material), ".")] if trust_material.is_file() else []
