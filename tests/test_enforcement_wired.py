"""License-enforcement wiring invariant — "no holes" guardrail.

The product is given away for free the moment ANY shipped surface runs the
connector in dev-mode (license validation off). That happened once already
(QB_LICENSE_URL unset everywhere → every tool unlocked). These static checks
fail CI if enforcement is ever un-wired again, on any distribution:

  1. the raw package is GATED BY DEFAULT (server.py defaults QB_LICENSE_URL to
     the hosted validator, so a bare `pip install` / self-host still enforces),
  2. the hosted connector (remote/fly.toml),
  3. the Claude Desktop extension (mcpb/manifest.json server env),
  4. the desktop app (accountingqb-local/serve.py, set before the import).

Import-order-independent on purpose: they read the source/config, not the live
module (whose QB_LICENSE_URL env can be seeded by other tests).
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VALIDATE = "/api/validate"


def test_raw_package_is_gated_by_default():
    src = (REPO / "mcpb" / "src" / "accountingqb" / "server.py").read_text()
    # No empty default (that was the dev-mode hole)…
    assert (
        '"QB_LICENSE_URL", ""' not in src
    ), "server.py defaults to dev-mode (ungated)!"
    # …and the default points at the hosted validator.
    assert (
        VALIDATE in src
    ), "server.py must default QB_LICENSE_URL to the hosted validator"


def test_hosted_connector_sets_validation_url():
    fly = (REPO / "remote" / "fly.toml").read_text()
    assert "QB_LICENSE_URL" in fly and VALIDATE in fly


def test_mcpb_extension_sets_validation_url():
    manifest = json.loads((REPO / "mcpb" / "manifest.json").read_text())
    env = manifest["server"]["mcp_config"]["env"]
    assert VALIDATE in (env.get("QB_LICENSE_URL") or ""), (
        "mcpb manifest server env must set QB_LICENSE_URL (the extension would "
        "otherwise run ungated)"
    )


def test_desktop_app_sets_validation_url():
    serve = (REPO / "accountingqb-local" / "serve.py").read_text()
    assert (
        "QB_LICENSE_URL" in serve and VALIDATE in serve
    ), "serve.py must set QB_LICENSE_URL before importing the connector"
