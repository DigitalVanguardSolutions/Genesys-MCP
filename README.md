# Genesys MCP

**Vendor-neutral Model Context Protocol server for Genesys Cloud.**

`genesys-mcp` is a Model Context Protocol (MCP) server that exposes Genesys Cloud
platform capabilities — queues, conversations, users, presence, analytics — as
MCP tools, resources, and prompts. Any MCP-compatible AI agent can speak to
Genesys through it: Claude Desktop, Claude Code, Cursor, Continue, Cline, and
any custom agent built on LangGraph, LangChain, CrewAI, AutoGen, or a raw
provider SDK.

## Status

**v0.1.0 — pre-release.** The framework, transports, and reliability layer are
in place. The first batch of read-only tools lands in v0.2; curated writes
(behind `--enable-writes`) and Resources/Prompts land in v0.3. The v1.0 launch
ships everything together with PyPI, Docker (GHCR), an `npx` shim, and an MCPB
bundle.

## Why

The MCP ecosystem already has a Genesys Cloud server, but it ships stdio-only
without HTTP transport, has no per-request auth context (a single module-global
boolean gates the whole process), and has no production reliability layer
(no 429 handling, no token refresh, no structured logging). `genesys-mcp` is
designed for the production surface: hosted-ready Streamable HTTP, per-request
auth, 429-aware retry, refresh-on-401, structured logs, and OpenTelemetry
tracing — all from day one, all vendor-neutral.

## Quickstart

> Tools are not yet shipped — these snippets show the install pattern. v0.2
> will list the actual tool surface here.

### Claude Desktop

Add an entry under `mcpServers` in your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "genesys": {
      "command": "uvx",
      "args": ["genesys-mcp"],
      "env": {
        "GENESYS_REGION": "mypurecloud.com",
        "GENESYS_CLIENT_ID": "...",
        "GENESYS_CLIENT_SECRET": "..."
      }
    }
  }
}
```

### Claude Code or Cursor

Add an entry to your editor's MCP server config (`.claude/settings.json` for
Claude Code, the Cursor MCP settings panel for Cursor):

```json
{
  "mcpServers": {
    "genesys": {
      "command": "genesys-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "GENESYS_REGION": "mypurecloud.com",
        "GENESYS_CLIENT_ID": "...",
        "GENESYS_CLIENT_SECRET": "..."
      }
    }
  }
}
```

### Programmatic Python

Connect via the official `mcp` Python client over stdio or HTTP:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(command="genesys-mcp", args=["--transport", "stdio"])

async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        # tools = await session.list_tools()  # available from v0.2
```

For HTTP transport, run `genesys-mcp --transport http --port 8000` and connect
your MCP client to `http://localhost:8000`.

## Install

```bash
pip install genesys-mcp
```

> Coming v1.0: published on [PyPI](https://pypi.org/project/genesys-mcp/),
> [GHCR](https://ghcr.io/digitalvanguardsolutions/genesys-mcp),
> [npm shim](https://www.npmjs.com/package/@digitalvanguardsolutions/genesys-mcp),
> and as an MCPB bundle attached to GitHub Releases.

## Transports

| Transport | Use case | CLI |
| --- | --- | --- |
| `stdio` (default) | Local clients — Claude Desktop, Claude Code, Cursor, `npx` invocation | `genesys-mcp` |
| `http` | Networked / hosted deployment, multi-agent gateways | `genesys-mcp --transport http --host 0.0.0.0 --port 8000` |

Both transports share the same tool surface. Transport selection is
environment-driven (`MCP_TRANSPORT=stdio|http`) or CLI-driven (`--transport`).

### Security

The HTTP transport in v0.x ships **unauthenticated**. The MCP framing layer
does not perform any caller authentication; the server trusts whatever
process can reach the listening port. Operators have two responsible
deployment options:

1. Bind to `127.0.0.1` only (the default `MCP_HOST`) and let local agents
   connect over loopback.
2. Bind to a non-loopback address only behind a reverse proxy (nginx, Caddy,
   Cloudflare Access, an API gateway) that performs authentication and
   authorisation before forwarding to `genesys-mcp`.

Binding to `0.0.0.0` without a fronting auth layer exposes the upstream
Genesys credentials to anyone on the network. The Docker image therefore
defaults `MCP_HOST=127.0.0.1`; operators who genuinely need a public bind
must opt in explicitly with `-e MCP_HOST=0.0.0.0`.

A hosted, multi-tenant gateway with first-class authentication, audit, and
RBAC is on the Pro/SaaS roadmap (see ADR-006 in `docs/warm/decisions.md`).

## Trust model

A few things to know before installing plugins or running this in
production:

- **Entry-point plugins** (the `genesys_mcp.plugins` group) execute in the
  server process with full access to every dependency, environment variable,
  and Genesys credential the server has. Only install plugins you trust.
- **The license hook** (`genesys_mcp.license` group) is a feature gate, not
  a security control. Any installed package can register one and any plugin
  can ignore the answer. It exists so the Pro package can express
  entitlements; treat it accordingly.
- **OAuth client secrets** are loaded from environment variables (and the
  `.env` file if present) and the server itself never logs them. We cannot
  guarantee the same of downstream plugins — vet them, or run with
  `LOG_LEVEL=INFO` and inspect output before trusting them with secrets.

## Configuration

Configuration is read from environment variables (or a `.env` file). See
`.env.example` for the full list. The most important variables:

| Variable | Default | Description |
| --- | --- | --- |
| `MCP_TRANSPORT` | `stdio` | Transport selection (`stdio` or `http`) |
| `MCP_HOST` | `127.0.0.1` | HTTP bind host |
| `MCP_PORT` | `8000` | HTTP bind port |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `GENESYS_MCP_ENABLE_WRITES` | `false` | Opt-in to low-blast-radius write tools |
| `GENESYS_REGION` | `mypurecloud.com` | Genesys Cloud region (e.g. `mypurecloud.de`, `apne2.pure.cloud`) |
| `GENESYS_CLIENT_ID` | — | OAuth Client Credentials client id |
| `GENESYS_CLIENT_SECRET` | — | OAuth Client Credentials client secret |

## Development

```bash
git clone https://github.com/digitalvanguardsolutions/genesys-mcp.git
cd genesys-mcp

uv sync --all-extras

uv run pytest
uv run ruff check src tests
uv run mypy src

uv run genesys-mcp --transport stdio
```

`pre-commit install` will wire up `ruff`, `mypy`, and a pre-push `pytest` run.

## License

MIT — see [LICENSE](LICENSE). Copyright 2026 Digital Vanguard Solutions.
