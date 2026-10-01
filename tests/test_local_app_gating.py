"""Local desktop app (accountingqb-local/serve.py) revenue gate.

The local app used to run in "dev mode" (all tools unlocked) — the download
path's giveaway. serve.py now (a) sets QB_LICENSE_URL before importing the
connector so _apply_license_gating wraps every paid tool, and (b) refuses the
chat/sample surfaces unless the configured license is active. These lock both.
"""

import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "accountingqb-local"))
sys.path.insert(0, str(_ROOT / "mcpb" / "src"))

import serve  # noqa: E402


def test_serve_turns_license_enforcement_on():
    # The master switch must be set by the local app itself (so the download
    # build enforces), pointing at the hosted validator.
    assert os.environ.get("QB_LICENSE_URL", "").endswith("/api/validate")


def test_license_active_false_without_a_key(monkeypatch):
    monkeypatch.setattr(serve.qb, "_effective_license_key", lambda: "")
    assert asyncio.run(serve._license_active()) is False


class _Req:
    async def json(self):
        return {}


def test_chat_refuses_without_active_license(monkeypatch):
    async def _inactive():
        return False

    monkeypatch.setattr(serve, "_license_active", _inactive)
    res = asyncio.run(serve.chat(_Req()))
    assert res.status_code == 402


def test_sample_refuses_without_active_license(monkeypatch):
    async def _inactive():
        return False

    monkeypatch.setattr(serve, "_license_active", _inactive)
    res = asyncio.run(serve.sample(_Req()))
    assert res.status_code == 402
