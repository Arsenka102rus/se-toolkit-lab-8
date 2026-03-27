"""MCP server exposing VictoriaLogs and VictoriaTraces as typed tools."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

server = Server("observability")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_victorialogs_url: str = ""
_victoriatraces_url: str = ""


def _get_victorialogs_url() -> str:
    return os.environ.get("VICTORIALOGS_URL", "http://localhost:42010")


def _get_victoriatraces_url() -> str:
    return os.environ.get("VICTORIATRACES_URL", "http://localhost:42011")


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class _LogsSearchQuery(BaseModel):
    query: str = Field(
        default="*",
        description="LogsQL query string. Use _stream:{service.name=\"backend\"} to filter by service.",
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Max logs to return.")


class _LogsErrorCountQuery(BaseModel):
    service: str = Field(default="", description="Service name to filter (optional).")
    minutes: int = Field(
        default=60, ge=1, le=1440, description="Time window in minutes."
    )


class _TracesListQuery(BaseModel):
    service: str = Field(
        default="Learning Management Service", description="Service name."
    )
    limit: int = Field(default=10, ge=1, le=100, description="Max traces to return.")


class _TracesGetQuery(BaseModel):
    trace_id: str = Field(description="Trace ID (hex string).")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text(data: Any) -> list[TextContent]:
    """Serialize data to JSON text."""
    if isinstance(data, (dict, list)):
        content = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        content = str(data)
    return [TextContent(type="text", text=content)]


async def _http_get(url: str, params: dict[str, str] | None = None) -> Any:
    """Make HTTP GET request."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool handlers - VictoriaLogs
# ---------------------------------------------------------------------------


async def _logs_search(args: _LogsSearchQuery) -> list[TextContent]:
    """Search logs in VictoriaLogs using LogsQL."""
    url = f"{_victorialogs_url}/select/logsql/query"
    params = {"query": args.query, "limit": str(args.limit)}
    try:
        result = await _http_get(url, params)
        return _text(result)
    except Exception as exc:
        return _text({"error": f"VictoriaLogs query failed: {exc}"})


async def _logs_error_count(args: _LogsErrorCountQuery) -> list[TextContent]:
    """Count errors per service over a time window."""
    # Build LogsQL query for errors
    if args.service:
        query = f'_stream:{{service.name="{args.service}"}} severity:ERROR'
    else:
        query = "_stream:{*} severity:ERROR"
    
    url = f"{_victorialogs_url}/select/logsql/query"
    params = {"query": query, "limit": "1000"}
    
    try:
        result = await _http_get(url, params)
        # Count errors from result
        if isinstance(result, list):
            error_count = len(result)
        else:
            error_count = len(result.get("values", [])) if isinstance(result, dict) else 0
        
        return _text({
            "query": query,
            "time_window_minutes": args.minutes,
            "error_count": error_count,
            "sample_errors": result[:10] if isinstance(result, list) else result,
        })
    except Exception as exc:
        return _text({"error": f"VictoriaLogs error count failed: {exc}"})


# ---------------------------------------------------------------------------
# Tool handlers - VictoriaTraces
# ---------------------------------------------------------------------------


async def _traces_list(args: _TracesListQuery) -> list[TextContent]:
    """List recent traces for a service."""
    url = f"{_victoriatraces_url}/jaeger/api/traces"
    params = {"service": args.service, "limit": str(args.limit)}
    try:
        result = await _http_get(url, params)
        # Extract trace summaries
        traces = []
        if isinstance(result, dict) and "data" in result:
            for trace in result["data"]:
                traces.append({
                    "trace_id": trace.get("traceID"),
                    "span_count": len(trace.get("spans", [])),
                    "start_time": trace.get("startTime"),
                    "duration_ms": trace.get("duration"),
                })
        return _text({"traces": traces, "total": len(traces)})
    except Exception as exc:
        return _text({"error": f"VictoriaTraces list failed: {exc}"})


async def _traces_get(args: _TracesGetQuery) -> list[TextContent]:
    """Fetch a specific trace by ID."""
    url = f"{_victoriatraces_url}/jaeger/api/traces/{args.trace_id}"
    try:
        result = await _http_get(url)
        # Extract span hierarchy
        if isinstance(result, dict) and "data" in result:
            trace = result["data"][0] if result["data"] else {}
            spans = []
            for span in trace.get("spans", []):
                spans.append({
                    "span_id": span.get("spanID"),
                    "operation_name": span.get("operationName"),
                    "service_name": span.get("process", {}).get("serviceName"),
                    "duration_ms": span.get("duration"),
                    "tags": {t["key"]: t["value"] for t in span.get("tags", [])},
                })
            return _text({
                "trace_id": args.trace_id,
                "spans": spans,
                "total_spans": len(spans),
            })
        return _text(result)
    except Exception as exc:
        return _text({"error": f"VictoriaTraces get failed: {exc}"})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_Registry = tuple[type[BaseModel], Callable[..., Awaitable[list[TextContent]]], Tool]

_TOOLS: dict[str, _Registry] = {}


def _register(
    name: str,
    description: str,
    model: type[BaseModel],
    handler: Callable[..., Awaitable[list[TextContent]]],
) -> None:
    schema = model.model_json_schema()
    schema.pop("$defs", None)
    schema.pop("title", None)
    _TOOLS[name] = (model, handler, Tool(name=name, description=description, inputSchema=schema))


_register(
    "logs_search",
    "Search logs in VictoriaLogs using LogsQL. Use _stream:{service.name=\"...\"} to filter by service, severity:ERROR for errors.",
    _LogsSearchQuery,
    _logs_search,
)
_register(
    "logs_error_count",
    "Count errors in VictoriaLogs over a time window. Returns error count and sample error logs.",
    _LogsErrorCountQuery,
    _logs_error_count,
)
_register(
    "traces_list",
    "List recent traces for a service from VictoriaTraces.",
    _TracesListQuery,
    _traces_list,
)
_register(
    "traces_get",
    "Fetch a specific trace by ID from VictoriaTraces. Returns span hierarchy.",
    _TracesGetQuery,
    _traces_get,
)


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [entry[2] for entry in _TOOLS.values()]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    entry = _TOOLS.get(name)
    if entry is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    model_cls, handler, _ = entry
    try:
        args = model_cls.model_validate(arguments or {})
        return await handler(args)
    except Exception as exc:
        return [TextContent(type="text", text=f"Error: {type(exc).__name__}: {exc}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    global _victorialogs_url, _victoriatraces_url
    _victorialogs_url = _get_victorialogs_url()
    _victoriatraces_url = _get_victoriatraces_url()
    
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
