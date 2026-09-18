-- Client-selectable read-only connector mode.
--
-- When true, the remote connector runs the license in READ-ONLY mode: the server
-- refuses every book-mutating tool before it executes (server._apply_readonly_gating)
-- and filters tools/list to read/report tools only. This is a hard, server-enforced
-- lock — beyond the client's per-action approval. Toggled by the user in the dashboard
-- (POST /api/user/read-only) and read by the connector via /api/license/default-realm.
-- Additive + safe: default false preserves current behavior for everyone.

ALTER TABLE licenses ADD COLUMN IF NOT EXISTS read_only BOOLEAN NOT NULL DEFAULT false;
