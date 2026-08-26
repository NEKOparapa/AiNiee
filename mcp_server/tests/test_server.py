def test_build_server_constructs(monkeypatch):
    # default backend is http; HttpBackend construction makes no network call.
    monkeypatch.delenv("AINIEE_MCP_BACKEND", raising=False)
    from ainiee_mcp.server import build_server

    mcp = build_server()
    assert mcp is not None
    assert mcp.name == "ainiee"
