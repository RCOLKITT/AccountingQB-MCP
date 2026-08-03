"""Tool-usage telemetry: tools must be tracked in the hosted (multi-tenant)
path where the module-level LICENSE_KEY is empty and the license arrives
per-request via ctx.license_key. Regression for the bug that left tool_usage
empty in production."""

import asyncio

import pytest
import respx
from httpx import Response

import accountingqb.server as qb_server

USAGE_URL = qb_server.USAGE_API_URL


async def _drain_usage_tasks():
    """Await any in-flight fire-and-forget tracking tasks."""
    if qb_server._usage_tasks:
        await asyncio.gather(*list(qb_server._usage_tasks), return_exceptions=True)


def test_tools_wrapped_even_without_module_license_key(server):
    """The core regression: LICENSE_KEY is empty in conftest (remote scenario),
    yet every registered tool must still be wrapped for usage tracking."""
    assert server.LICENSE_KEY == ""  # conftest scrubbed QB_LICENSE_KEY
    tools = server.mcp._tool_manager._tools
    assert tools, "expected registered tools"
    # track_usage uses functools.wraps, so wrapped fns expose __wrapped__.
    wrapped = [name for name, t in tools.items() if hasattr(t.fn, "__wrapped__")]
    assert len(wrapped) == len(tools), "all tools must be usage-tracked"


def test_wrapper_posts_with_ctx_license_and_realm(qb_ctx, monkeypatch):
    """A per-request (remote) license + realm on the context are reported."""
    monkeypatch.setattr(qb_server, "LICENSE_KEY", "")  # no single-tenant key
    qb_ctx.license_key = "LK-REMOTE-TEST"
    qb_ctx.realm_id = "9130350000000000"

    async def _dummy():
        return "ok"

    wrapped = qb_server.track_usage(_dummy)

    with respx.mock(assert_all_called=True) as router:
        route = router.post(USAGE_URL).mock(return_value=Response(200, json={"tracked": True}))

        async def _run():
            result = await wrapped()
            await _drain_usage_tasks()
            return result

        result = asyncio.run(_run())

    assert result == "ok"
    body = route.calls[0].request.read()
    import json
    payload = json.loads(body)
    assert payload["licenseKey"] == "LK-REMOTE-TEST"
    assert payload["realmId"] == "9130350000000000"
    assert payload["toolName"] == "_dummy"


def test_wrapper_no_post_without_license(qb_ctx, monkeypatch):
    """No effective license (dev/anonymous) -> no telemetry POST at all."""
    monkeypatch.setattr(qb_server, "LICENSE_KEY", "")
    qb_ctx.license_key = ""

    async def _dummy():
        return "ok"

    wrapped = qb_server.track_usage(_dummy)

    with respx.mock(assert_all_called=False) as router:
        route = router.post(USAGE_URL).mock(return_value=Response(200))

        async def _run():
            result = await wrapped()
            await _drain_usage_tasks()
            return result

        result = asyncio.run(_run())

    assert result == "ok"
    assert route.call_count == 0


def test_tracking_task_reference_retained(qb_ctx, monkeypatch):
    """GC-safety: the scheduled task is held in _usage_tasks until it finishes,
    so it can't be garbage-collected mid-flight."""
    monkeypatch.setattr(qb_server, "LICENSE_KEY", "")
    qb_ctx.license_key = "LK-REMOTE-TEST"
    qb_ctx.realm_id = "R1"

    async def _dummy():
        return "ok"

    wrapped = qb_server.track_usage(_dummy)

    with respx.mock(assert_all_called=True) as router:
        router.post(USAGE_URL).mock(return_value=Response(200))

        async def _run():
            await wrapped()
            # Before draining, the in-flight task must be tracked.
            assert len(qb_server._usage_tasks) >= 1
            await _drain_usage_tasks()
            # done_callback clears finished tasks.
            assert len(qb_server._usage_tasks) == 0

        asyncio.run(_run())
