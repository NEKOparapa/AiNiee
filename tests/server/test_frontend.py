"""Packaged static assets are public; local application data and APIs are not."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from Server.app import create_app
from Server.frontend import FrontendFiles


TOKEN = "fixed-bundle-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
HTML = {"Accept": "text/html"}
ORIGIN = "http://127.0.0.1:52345"


class RuntimeStub:
    def __init__(self):
        from ModuleFolders.Service.Cache.CacheManager import CacheManager
        self.cache_manager = CacheManager()

    def close(self):
        self.cache_manager._cleanup_event_subscriptions()


@pytest.fixture
def frontend(tmp_path):
    directory = tmp_path / "frontend"
    directory.mkdir()
    (directory / "index.html").write_text("<!doctype html><title>Fixed bundled UI</title>", encoding="utf-8")
    (directory / "assets").mkdir()
    (directory / "assets" / "app.js").write_text("export const value = 'fixed';", encoding="utf-8")
    (directory / "assets" / "app.css").write_text("body { color: black; }", encoding="utf-8")
    (directory / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    (tmp_path / "private.json").write_text('{"api_key":"should-not-be-served"}', encoding="utf-8")
    return directory


@pytest.fixture
def client(frontend):
    app = create_app(TOKEN, frontend_dir=frontend, allowed_origins=(ORIGIN,), runtime_factory=RuntimeStub)
    with TestClient(app) as result:
        yield result


def test_static_get_and_head_load_without_api_credentials(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Fixed bundled UI" in response.text
    assert TOKEN not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    for path, content_type in (("/index.html", "text/html"), ("/assets/app.js", "text/javascript"),
                               ("/assets/app.css", "text/css"), ("/favicon.svg", "image/svg+xml")):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(content_type)
        head = client.head(path)
        assert head.status_code == 200 and head.content == b""
        assert head.headers["content-length"] == response.headers["content-length"]


def test_browser_deep_links_load_the_spa_but_missing_assets_do_not(client):
    for path in ("/project", "/settings/task", "/prompts/library", "/items?file=test.txt&page=2"):
        response = client.get(path, headers=HTML)
        assert response.status_code == 200 and "Fixed bundled UI" in response.text
        assert client.head(path, headers=HTML).status_code == 200
    # The frontend router owns unknown HTML navigation routes. Ordinary unknown
    # requests still require authentication and return the backend's 404.
    assert client.get("/unknown").status_code == 401
    assert client.get("/unknown", headers=AUTH).status_code == 404
    for path in ("/missing.js", "/assets/missing.js", "/assets/missing", "/ASSETS/missing"):
        response = client.get(path, headers={**AUTH, **HTML})
        assert response.status_code == 404 and "Fixed bundled UI" not in response.text


def test_api_schema_health_and_unknown_api_paths_are_never_spa_files(client, frontend):
    (frontend / "api" / "v1").mkdir(parents=True)
    (frontend / "api" / "v1" / "unknown").write_text("accidental API-named file", encoding="utf-8")
    for path in ("/api", "/api/v1/config", "/api/v1/unknown", "/openapi.json", "/docs", "/health/missing"):
        assert client.get(path, headers=HTML).status_code == 401
        assert client.get(path + "?token=" + TOKEN, headers=HTML).status_code == 401
    assert client.get("/api/v1/unknown", headers={**AUTH, **HTML}).status_code == 404
    assert client.get("/health/missing", headers={**AUTH, **HTML}).status_code == 404
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/v1/version", headers=AUTH).status_code == 200
    schema = client.get("/openapi.json", headers=AUTH).json()
    assert schema == create_app(TOKEN, runtime_factory=RuntimeStub).openapi()


def test_public_files_do_not_allow_writes_or_foreign_browser_origins(client):
    for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
        assert client.request(method, "/index.html", headers=HTML).status_code == 401
        assert client.request(method, "/index.html", headers={**AUTH, **HTML}).status_code == 405
    assert client.patch("/api/v1/config", json={"accent_color": "#123456"}).status_code == 401
    assert client.post("/api/v1/shutdown").status_code == 401
    for path in ("/", "/assets/app.js", "/settings/task"):
        assert client.get(path, headers={**HTML, "Origin": "https://untrusted.invalid"}).status_code == 403
        assert client.get(path, headers={**HTML, "Origin": ORIGIN}).status_code == 200
    preflight = client.options("/api/v1/config", headers={
        "Origin": ORIGIN, "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "Authorization,Content-Type",
    })
    assert preflight.status_code == 200


@pytest.mark.parametrize("path", [
    "/%2e%2e/private.json", "/assets/%2e%2e/%2e%2e/private.json",
    "/%5c..%5cprivate.json", "/assets%5c..%5c..%5cprivate.json",
    "/C:/private.json", "/index.html:private", "/%00", "/%252e%252e/private.json",
    "/.env", "/assets/.secret", "/api%2fv1/unknown",
])
def test_unsafe_and_encoded_paths_never_escape_frontend_root(client, path):
    response = client.get(path, headers={**AUTH, **HTML})
    assert response.status_code == 404
    assert "should-not-be-served" not in response.text
    assert "Fixed bundled UI" not in response.text
    assert client.get(path, headers=HTML).status_code == 401


def make_symlink(link, target, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows runner lacks symlink privilege")
        raise


def test_symlink_files_and_missing_leaves_outside_root_are_not_served(client, frontend):
    make_symlink(frontend / "linked.json", frontend.parent / "private.json")
    make_symlink(frontend / "outside", frontend.parent, directory=True)
    for path in ("/linked.json", "/outside/private.json", "/outside/unknown-navigation"):
        assert client.get(path, headers=HTML).status_code == 401
        response = client.get(path, headers={**AUTH, **HTML})
        assert response.status_code == 404
        assert "should-not-be-served" not in response.text
        assert "Fixed bundled UI" not in response.text


def test_packaged_index_must_exist_inside_the_frontend_directory(tmp_path):
    directory = tmp_path / "bad-frontend"
    directory.mkdir()
    with pytest.raises(ValueError, match="index.html"):
        FrontendFiles(directory)
    private = tmp_path / "private.html"
    private.write_text("not part of the bundle", encoding="utf-8")
    make_symlink(directory / "index.html", private)
    with pytest.raises(ValueError, match="index.html"):
        FrontendFiles(directory)


def test_frontend_auth_exception_does_not_apply_to_websockets(client):
    for path in ("/api/v1/ws", "/api/v1/ws?token=wrong", "/index.html", "/settings/task"):
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(path):
                pass
        assert error.value.code == 1008
    with client.websocket_connect(f"/api/v1/ws?token={TOKEN}", headers={"Origin": ORIGIN}):
        pass


def test_source_api_mode_has_no_static_or_html_navigation_exemption():
    with TestClient(create_app(TOKEN, runtime_factory=RuntimeStub)) as client:
        for path in ("/", "/index.html", "/assets/app.js", "/settings/task"):
            assert client.get(path, headers=HTML).status_code == 401
            assert client.get(path, headers={**AUTH, **HTML}).status_code == 404
