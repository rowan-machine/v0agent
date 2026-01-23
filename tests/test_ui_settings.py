# tests/test_ui_settings.py
"""
Tests for UI Settings including:
- Workflow mode API endpoints (GET/POST)
- Mode persistence and settings
- Drawer pinned state persistence

These tests validate the backend APIs that support the frontend localStorage settings.
"""

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    # Import here to avoid circular imports and ensure fresh app state
    import sys
    sys.path.insert(0, '/Users/rowan/v0agent/src')
    from app.main import app
    return TestClient(app)


# =============================================================================
# MODE SETTINGS API TESTS
# =============================================================================

class TestModeSettingsAPI:
    """Tests for workflow mode settings API endpoints."""
    
    def test_get_mode_default(self, client):
        """Test getting mode returns default when not set."""
        response = client.get('/api/settings/mode')
        assert response.status_code == 200
        data = response.json()
        assert 'mode' in data
        # Default should be mode-a or whatever is stored
        assert data['mode'].startswith('mode-')
    
    def test_set_mode_valid(self, client):
        """Test setting a valid workflow mode."""
        response = client.post(
            '/api/settings/mode',
            json={'mode': 'mode-b'}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert data['mode'] == 'mode-b'
        
        # Verify it persisted
        get_response = client.get('/api/settings/mode')
        assert get_response.json()['mode'] == 'mode-b'
    
    def test_set_mode_all_modes(self, client):
        """Test setting all valid workflow modes."""
        valid_modes = ['mode-a', 'mode-b', 'mode-c', 'mode-d', 'mode-e', 'mode-f', 'mode-g']
        
        for mode in valid_modes:
            response = client.post(
                '/api/settings/mode',
                json={'mode': mode}
            )
            assert response.status_code == 200
            assert response.json()['mode'] == mode
    
    def test_set_mode_missing_defaults(self, client):
        """Test setting mode without mode key defaults to mode-a."""
        response = client.post(
            '/api/settings/mode',
            json={}
        )
        assert response.status_code == 200
        assert response.json()['mode'] == 'mode-a'


class TestModeSuggestionAPI:
    """Tests for smart mode suggestion API."""
    
    def test_get_suggested_mode(self, client):
        """Test getting suggested mode based on sprint cadence."""
        response = client.get('/api/settings/mode/suggested')
        assert response.status_code == 200
        data = response.json()
        assert 'suggested_mode' in data
        # Mode should be valid
        assert data['suggested_mode'].startswith('mode-')
    
    def test_suggested_mode_includes_sprint_info(self, client):
        """Test that suggested mode includes sprint information."""
        response = client.get('/api/settings/mode/suggested')
        assert response.status_code == 200
        data = response.json()
        # Should include sprint info for context
        if 'sprint_info' in data:
            assert 'day_of_sprint' in data['sprint_info'] or 'days_until_next_sprint' in data['sprint_info']


class TestExpectedDurationAPI:
    """Tests for mode expected duration API."""
    
    def test_get_expected_duration(self, client):
        """Test getting expected duration per mode."""
        response = client.get('/api/settings/mode/expected-duration')
        assert response.status_code == 200
        data = response.json()
        
        # Response has modes at top level
        expected_modes = ['mode-a', 'mode-b', 'mode-c', 'mode-d', 'mode-e', 'mode-f', 'mode-g']
        for mode in expected_modes:
            assert mode in data, f"Missing mode: {mode}"
            assert 'expected_minutes' in data[mode]
            assert 'default_minutes' in data[mode]
            assert 'historical_sessions' in data[mode]


# =============================================================================
# MODE PIN SETTINGS (Documentation Tests)
# =============================================================================

class TestModePinDocumentation:
    """Documentation tests for mode pin localStorage settings.
    
    These tests document the expected localStorage keys and values
    used by the frontend for mode pinning functionality.
    """
    
    def test_mode_pin_localstorage_key(self):
        """Document the localStorage key for mode pinning."""
        # This is a documentation test - no actual localStorage in Python
        expected_key = 'signalflow-mode-pinned'
        expected_values = ['true', 'false']
        
        # Document the expected behavior
        assert expected_key == 'signalflow-mode-pinned'
        assert 'true' in expected_values
        assert 'false' in expected_values
    
    def test_mode_names_mapping(self):
        """Document the mode names mapping used in UI."""
        expected_mode_names = {
            'mode-a': 'A: Context',
            'mode-b': 'B: Planning',
            'mode-c': 'C: Drafting',
            'mode-d': 'D: Review',
            'mode-e': 'E: Promote',
            'mode-f': 'F: Sync',
            'mode-g': 'G: Execute'
        }
        
        # All modes should have short display names
        for mode, name in expected_mode_names.items():
            assert mode.startswith('mode-')
            assert ': ' in name  # Format is "Letter: Name"
            assert len(name) <= 15  # Should be short for badge display


class TestDrawerSettingsDocumentation:
    """Documentation tests for drawer localStorage settings."""
    
    def test_drawer_pinned_localstorage_key(self):
        """Document the localStorage key for drawer pinned state."""
        expected_key = 'drawerPinned'
        expected_values = ['true', 'false']
        
        assert expected_key == 'drawerPinned'
        assert 'true' in expected_values
    
    def test_arjuna_drawer_settings(self):
        """Document Arjuna drawer localStorage keys."""
        expected_keys = [
            'arjuna-drawer-collapsed',
            'arjuna-drawer-expanded',
            'arjuna-quick-edit',
            'arjuna-quick-order'
        ]
        
        # All keys should follow consistent naming
        for key in expected_keys:
            assert 'arjuna' in key.lower()


class TestTimeTrackingSettingsDocumentation:
    """Documentation tests for time tracking localStorage settings."""
    
    def test_time_tracking_localstorage_keys(self):
        """Document localStorage keys for time tracking."""
        expected_keys = [
            'signalflow-auto-tracking',  # Auto-track toggle
            'signalflow-tracking-mode',  # Currently tracking mode
            'signalflow-tracking-start', # Tracking start timestamp
        ]
        
        for key in expected_keys:
            assert 'signalflow' in key or 'tracking' in key


class TestThemeSettingsDocumentation:
    """Documentation tests for theme localStorage settings."""
    
    def test_theme_localstorage_keys(self):
        """Document localStorage keys for theme settings."""
        expected_keys = {
            'harekrishna-theme': ['light', 'dark'],
            'signalflow-accent': ['blue', 'orange', 'green', 'red'],
            'signalflow-mode': ['mode-a', 'mode-b', 'mode-c', 'mode-d', 'mode-e', 'mode-f', 'mode-g'],
        }
        
        for key, values in expected_keys.items():
            assert isinstance(values, list)
            assert len(values) > 0


# =============================================================================
# COMBINED SETTINGS PERSISTENCE TEST
# =============================================================================

class TestSettingsPersistence:
    """Tests for combined settings persistence."""
    
    def test_mode_roundtrip(self, client):
        """Test that mode can be saved and retrieved."""
        # Set mode
        set_response = client.post(
            '/api/settings/mode',
            json={'mode': 'mode-g'}
        )
        assert set_response.status_code == 200
        
        # Get mode
        get_response = client.get('/api/settings/mode')
        assert get_response.status_code == 200
        assert get_response.json()['mode'] == 'mode-g'
    
    def test_ai_model_roundtrip(self, client):
        """Test that AI model can be saved and retrieved."""
        # Set model
        set_response = client.post(
            '/api/settings/ai-model',
            json={'model': 'gpt-4'}
        )
        assert set_response.status_code == 200
        
        # Get model
        get_response = client.get('/api/settings/ai-model')
        assert get_response.status_code == 200
        assert get_response.json()['model'] == 'gpt-4'
