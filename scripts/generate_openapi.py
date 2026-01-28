#!/usr/bin/env python3
"""
Generate OpenAPI specification from FastAPI app.

Usage:
    python scripts/generate_openapi.py

Output:
    docs/api/openapi.json
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.main import app


def main():
    """Generate and save OpenAPI spec."""
    # Get OpenAPI schema from FastAPI
    openapi_schema = app.openapi()
    
    # Enhance with additional metadata
    openapi_schema["info"]["description"] = """
# SignalFlow API

SignalFlow is a meeting intelligence platform that extracts signals, manages knowledge,
and provides career development insights.

## Authentication

Most endpoints require authentication. Pass your API key in the `Authorization` header:

```
Authorization: Bearer your-api-key
```

## Rate Limits

- Standard: 100 requests/minute
- Bulk operations: 10 requests/minute

## Versioning

The API is versioned via URL path. Current version: v1

Endpoints under `/api/v1/` are stable and follow semantic versioning.
Endpoints under `/api/` without version may change without notice.
"""
    
    openapi_schema["info"]["contact"] = {
        "name": "SignalFlow Support",
        "email": "support@signalflow.dev",
    }
    
    openapi_schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }
    
    # Add server definitions
    openapi_schema["servers"] = [
        {"url": "http://localhost:8001", "description": "Local development"},
        {"url": "https://v0agent-staging.up.railway.app", "description": "Staging"},
        {"url": "https://v0agent-production.up.railway.app", "description": "Production"},
    ]
    
    # Save to file
    output_path = Path(__file__).parent.parent / "docs" / "api" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)
    
    print(f"✅ OpenAPI spec generated: {output_path}")
    print(f"   - {len(openapi_schema.get('paths', {}))} endpoints documented")
    print(f"   - {len(openapi_schema.get('components', {}).get('schemas', {}))} schemas defined")


if __name__ == "__main__":
    main()
