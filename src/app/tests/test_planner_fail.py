# tests/test_planner_fail.py

import pytest
from app.chat.planner import plan

def test_planner_invalid_json(monkeypatch):
    class DummyResp:
        output_text = "not json"

    class DummyClient:
        class responses:
            @staticmethod
            def create(*args, **kwargs):
                return DummyResp()

    from app.chat import planner
    
    # Mock the client in the planner module
    def fake_client_once():
        return DummyClient()
    
    monkeypatch.setattr(planner, "_client_once", fake_client_once)

    with pytest.raises(ValueError):
        plan("Why am I blocked?")
