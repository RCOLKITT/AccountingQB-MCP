-- Schema-drift introspection (VASPERA-SPINE G3).
--
-- schema_snapshot() returns the public schema's columns + indexes as deterministic
-- JSON, callable via the service role (rpc) — so CI can diff LIVE vs the committed
-- web/schema-snapshot.json without a direct Postgres connection string. See
-- web/scripts/check-schema-drift.mjs. Read-only; safe to re-create.

CREATE OR REPLACE FUNCTION schema_snapshot()
RETURNS jsonb
LANGUAGE sql STABLE SET search_path = public AS $$
  SELECT jsonb_build_object(
    'columns', (
      SELECT coalesce(jsonb_agg(c ORDER BY c->>'table', c->>'column'), '[]'::jsonb)
      FROM (
        SELECT jsonb_build_object(
          'table', table_name,
          'column', column_name,
          'type', data_type,
          'nullable', is_nullable,
          'default', column_default
        ) AS c
        FROM information_schema.columns
        WHERE table_schema = 'public'
      ) x
    ),
    'indexes', (
      SELECT coalesce(jsonb_agg(i ORDER BY i->>'name'), '[]'::jsonb)
      FROM (
        SELECT jsonb_build_object('name', indexname, 'table', tablename, 'def', indexdef) AS i
        FROM pg_indexes WHERE schemaname = 'public'
      ) y
    )
  );
$$;
