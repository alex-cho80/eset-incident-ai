from eset_incident_ai.main import app


def test_main_exports_app() -> None:
    assert app.title == "eset-incident-ai"
