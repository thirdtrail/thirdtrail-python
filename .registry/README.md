# MCP registry metadata

`server.json` is what is published to the [official MCP registry](https://registry.modelcontextprotocol.io)
for `io.github.thirdtrail/thirdtrail`.

It lives here rather than in the main application repo because that repo is
private, and this file is public metadata by definition.

## Republishing

```bash
# from a checkout of this repo
mcp-publisher login github     # device flow; grants the io.github.thirdtrail/* namespace
mcp-publisher validate
mcp-publisher publish
```

Bump `version` before republishing — the registry keys on it.

## Notes

- The server is **remote**, not a package: the registry entry points at
  `https://thirdtrail.life/mcp` rather than something a client installs.
- `type: streamable-http` names the transport. Our implementation answers a
  single JSON-RPC POST with JSON rather than opening an SSE stream, which the
  spec permits for servers that never push. A client that *requires* the
  streaming variant would need that adding.
- The `Authorization` header is declared `isRequired` and `isSecret`, with the
  paid-plan requirement in its description — so a client asks for a key up
  front instead of discovering the 403 at first call.
