# tests/test_planner_valid.py

from app.chat.planner import plan

def test_planner_returns_valid_schema(monkeypatch):
    class DummyResp:
        output_text = """
        {
          "keywords": ["blocked"],
          "concepts": ["dependency", "delay"],
          "source_preference": "meetings",
          "time_hint": "recent",
          "notes": null
        }
        """

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

    data = plan("Why am I blocked?")
    assert "blocked" in data["keywords"]
    assert "dependency" in data["concepts"]
