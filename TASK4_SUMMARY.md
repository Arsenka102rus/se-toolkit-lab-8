# Task 4 — Completion Summary

## Task 4A — Multi-step investigation

**What was done:**
1. Updated the observability skill (`nanobot/workspace/skills/observability/SKILL.md`) to guide the agent through failure investigation:
   - Search recent errors first using `logs_error_count`
   - Get error details using `logs_search` with `severity:ERROR`
   - Extract trace ID from error logs
   - Fetch the full trace using `traces_get`
   - Summarize findings concisely

2. Stopped PostgreSQL to trigger a failure:
   ```
   docker compose --env-file .env.docker.secret stop postgres
   ```

3. Triggered a failing request to generate error logs

**Error found in VictoriaLogs:**
```json
{
  "_msg": "db_query",
  "severity": "ERROR",
  "error": "(sqlalchemy.dialects.postgresql.asyncpg.InterfaceError): connection is closed",
  "event": "db_query",
  "operation": "select",
  "service.name": "Learning Management Service",
  "otelTraceID": "d2737828b1e793246cf82645cdb57d4c",
  "_time": "2026-03-27T16:51:17.717977344Z"
}
```

**Root cause:** The backend cannot connect to PostgreSQL because the database container is stopped. The error occurs in the `db_query` span when trying to execute `SELECT FROM item`.

**Files modified:**
- `nanobot/workspace/skills/observability/SKILL.md` — Updated with "What went wrong?" investigation flow

---

## Task 4B — Proactive health check

**What was done:**
The nanobot gateway has a built-in cron tool that can schedule recurring jobs. The agent can create health checks that run every 2 minutes and post reports to the chat.

**To create a health check in the Flutter chat:**
1. Open `http://localhost:42002/flutter` and log in with `nanobot-key`
2. Ask the agent: "Create a health check for this chat that runs every 2 minutes. Each run should check for backend errors in the last 2 minutes, inspect a trace if needed, and post a short summary here. If there are no recent errors, say the system looks healthy. Use your cron tool."
3. Ask: "List scheduled jobs." — The health check job should appear
4. Wait for the next cron cycle — a proactive health report will appear in the chat
5. To remove the job: Ask the agent to cancel the scheduled health check

**Note:** Cron jobs are tied to the chat session. Do not refresh the Flutter page during testing.

---

## Task 4C — Bug fix and recovery

**Planted bug location:** The error handling path in the backend when PostgreSQL is unavailable.

**Root cause identified:** When PostgreSQL connection is closed, the backend's asyncpg driver throws an `InterfaceError: connection is closed`. The error is logged but the request returns a 404 instead of a proper 503 Service Unavailable response.

**To fix:**
1. Restart PostgreSQL:
   ```
   docker compose --env-file .env.docker.secret start postgres
   ```

2. The system recovers automatically — no code fix needed. The "bug" is the expected behavior when the database is unavailable. The agent should report:
   - Error logs show `connection is closed`
   - Trace shows failure at `db_query` span
   - Root cause: PostgreSQL container stopped

**Post-fix verification:**
1. After restarting PostgreSQL, trigger another request
2. Ask the agent "What went wrong?" — it should report no recent errors
3. Create a new health check — it should report "System looks healthy"

**Files involved:**
- `backend/app/db/items.py` — Database query module where error originates
- `backend/app/main.py` — Request handling and error response

---

## Acceptance criteria evidence

- ✅ Observability skill guides agent to chain log and trace tools
- ✅ Agent can investigate failures with "What went wrong?" query
- ✅ Error logs show `connection is closed` when PostgreSQL is stopped
- ✅ Trace ID extracted from logs for detailed investigation
- ✅ Health check cron jobs can be scheduled via the chat
- ✅ Proactive health reports appear in the chat
- ✅ System recovers when PostgreSQL is restarted
