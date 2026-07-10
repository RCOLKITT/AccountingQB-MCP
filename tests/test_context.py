"""ContextVar isolation: concurrent tasks see their own QBContext."""

import asyncio

from accountingqb.context import QBContext, get_ctx, set_ctx


def test_two_tasks_see_isolated_contexts():
    observed = {}

    async def tenant(name: str, realm: str, token: str):
        set_ctx(QBContext(realm_id=realm, access_token=token, persist_tokens=False))
        # Yield control so the tasks interleave
        await asyncio.sleep(0.01)
        ctx = get_ctx()
        # Mutations must also stay task-local
        ctx.refresh_token = f"rt-{name}"
        await asyncio.sleep(0.01)
        observed[name] = (get_ctx().realm_id, get_ctx().access_token, get_ctx().refresh_token)

    async def main():
        await asyncio.gather(
            tenant("a", "realm-A", "token-A"),
            tenant("b", "realm-B", "token-B"),
        )

    asyncio.run(main())

    assert observed["a"] == ("realm-A", "token-A", "rt-a")
    assert observed["b"] == ("realm-B", "token-B", "rt-b")


def test_default_context_untouched_by_task_contexts():
    from accountingqb.context import _default_ctx

    before = (_default_ctx.realm_id, _default_ctx.access_token)

    async def tenant():
        set_ctx(QBContext(realm_id="other-realm", access_token="other-token",
                          persist_tokens=False))
        get_ctx().refresh_token = "other-rt"

    asyncio.run(tenant())
    assert (_default_ctx.realm_id, _default_ctx.access_token) == before
