from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import LOCAL_ORIGIN_REGEX, parse_cors_origins
from app.routers import system


def test_parse_cors_origins_normalizes_paths_and_slashes() -> None:
    raw = (
        " https://willor16.github.io/app-slug/ , "
        "https://api.example.org/ , https://willor16.github.io "
    )
    assert parse_cors_origins(raw) == [
        "https://willor16.github.io",
        "https://api.example.org",
    ]


def test_cors_allows_configured_pages_origin_and_local_regex() -> None:
    probe = FastAPI()
    probe.add_middleware(
        CORSMiddleware,
        allow_origins=parse_cors_origins("https://spacescan.me,https://www.spacescan.me/"),
        allow_origin_regex=LOCAL_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @probe.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(probe) as test_client:
        pages_preflight = test_client.options(
            "/ping",
            headers={
                "Origin": "https://spacescan.me",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert pages_preflight.status_code == 200
        assert (
            pages_preflight.headers.get("access-control-allow-origin")
            == "https://spacescan.me"
        )

        www_resp = test_client.get("/ping", headers={"Origin": "https://www.spacescan.me"})
        assert www_resp.headers.get("access-control-allow-origin") == "https://www.spacescan.me"

        lan_resp = test_client.get("/ping", headers={"Origin": "http://192.168.1.56:3000"})
        assert lan_resp.headers.get("access-control-allow-origin") == "http://192.168.1.56:3000"

        blocked_resp = test_client.get("/ping", headers={"Origin": "https://untrusted.example.com"})
        assert "access-control-allow-origin" not in blocked_resp.headers


def test_sse_telemetry_sets_proxy_unbuffered_headers(client, monkeypatch) -> None:
    monkeypatch.setattr(system, "STREAM_LIFETIME_SEC", 0.0)
    response = client.get("/api/v1/stream/telemetry")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    assert "retry: 2000" in response.text
