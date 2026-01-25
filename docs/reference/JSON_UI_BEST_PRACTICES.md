# JSON for Swappable UIs - Implementation Guide

**Purpose:** Detailed guide on using JSON for configuration-driven UI development supporting multiple frontends (Web, Mobile, Desktop).

**Status:** Best practice recommendation with implementation examples

---

## Executive Summary

**Is JSON best practice for swappable UIs?**

**Answer: YES, with caveats.**

**Score: 8/10 for flexibility**

### Pros ✅
- Human-readable configuration
- No code changes needed for UI updates
- Supports multiple frontends in single config
- Easy A/B testing of layouts
- Version-friendly (git-tracked)
- Lightweight and fast to parse
- Standard format (widely understood)

### Cons ⚠️
- Not ideal for complex dynamic logic
- Can lead to "code in JSON" anti-pattern
- Limits creativity (must fit predefined structure)
- Requires careful schema design
- Validation complexity at scale

### When to Use JSON
✅ Layout configuration (component positions)
✅ Feature flags (enable/disable features)
✅ Theme switching (colors, fonts, spacing)
✅ Multi-frontend targeting (web/mobile/desktop)
❌ Business logic (use Python/TypeScript)
❌ Dynamic calculations (use code)
❌ Complex state management (use reducers)

---

## Architecture Pattern: Component Registry + Configuration

### Pattern Overview

```
config/ui.json          ← UI structure (what to show where)
    ↓
Component Registry      ← Maps to implementations
    ↓
Actual Components       ← React, Vue, HTML, mobile
    ↓
Rendered UI
```

### Data Flow

```
1. Application loads config/ui.json
2. Validates against schema (JSON Schema)
3. Resolves component mappings
4. Lazy-loads component implementations
5. Renders components with props
6. User sees UI
```

---

## Implementation Example

### Step 1: Define UI Configuration Schema

**File:** `config/ui.json`

```json
{
  "version": "2.0",
  "schema": "ui-config-2.0",
  "metadata": {
    "description": "UI configuration for SignalFlow",
    "lastUpdated": "2026-01-22",
    "environments": ["development", "production"]
  },
  "layouts": {
    "dashboard": {
      "description": "Main dashboard layout",
      "breakpoints": {
        "desktop": {
          "width": "> 1024px",
          "sections": [
            {
              "id": "header",
              "component": "Header",
              "position": "top",
              "props": {
                "sticky": true,
                "showMenu": true
              }
            },
            {
              "id": "sidebar",
              "component": "Sidebar",
              "position": "left",
              "props": {
                "width": "250px",
                "collapsible": true,
                "defaultOpen": true
              }
            },
            {
              "id": "main-content",
              "component": "MainContent",
              "position": "center",
              "props": {
                "padding": "20px",
                "sections": ["chat", "insights", "tasks"]
              }
            },
            {
              "id": "arjuna-drawer",
              "component": "ArjunaChat",
              "position": "bottom-right",
              "props": {
                "minimizable": true,
                "draggable": true,
                "width": "400px",
                "zIndex": 1000
              }
            }
          ]
        },
        "tablet": {
          "width": "768px - 1024px",
          "sections": [
            {
              "id": "header",
              "component": "Header",
              "props": {"sticky": true}
            },
            {
              "id": "main-content",
              "component": "MainContent",
              "position": "full-width"
            }
          ]
        },
        "mobile": {
          "width": "< 768px",
          "sections": [
            {
              "id": "header",
              "component": "MobileHeader",
              "props": {"sticky": true, "compact": true}
            },
            {
              "id": "main-content",
              "component": "MainContent",
              "position": "full-screen",
              "props": {"padding": "10px"}
            },
            {
              "id": "arjuna-drawer",
              "component": "ArjunaChat",
              "position": "bottom-sheet",
              "props": {
                "minimizable": false,
                "fullScreen": true
              }
            }
          ]
        }
      }
    }
  },
  "components": {
    "Header": {
      "description": "Top navigation header",
      "implementations": {
        "web": {
          "path": "src/components/Header.tsx",
          "type": "react"
        },
        "mobile": {
          "path": "mobile/src/components/Header.tsx",
          "type": "react-native"
        },
        "jinja": {
          "path": "templates/header.html",
          "type": "jinja2"
        }
      },
      "requiredProps": ["sticky"],
      "optionalProps": ["showMenu", "showSearch"]
    },
    "Sidebar": {
      "description": "Left sidebar navigation",
      "implementations": {
        "web": {
          "path": "src/components/Sidebar.tsx",
          "type": "react"
        },
        "mobile": {
          "path": "mobile/src/components/MobileSidebar.tsx",
          "type": "react-native"
        }
      },
      "requiredProps": ["width"],
      "optionalProps": ["collapsible", "defaultOpen"]
    },
    "ArjunaChat": {
      "description": "AI assistant chat interface",
      "implementations": {
        "web": {
          "path": "src/components/ArjunaChat.tsx",
          "type": "react"
        },
        "mobile": {
          "path": "mobile/src/components/ArjunaChat.tsx",
          "type": "react-native"
        },
        "jinja": {
          "path": "templates/arjuna_chat.html",
          "type": "jinja2"
        }
      },
      "requiredProps": [],
      "optionalProps": ["minimizable", "width", "zIndex"]
    }
  },
  "themes": {
    "light": {
      "name": "Light Theme",
      "colors": {
        "primary": "#0066cc",
        "secondary": "#666666",
        "background": "#ffffff",
        "surface": "#f5f5f5",
        "error": "#d32f2f",
        "success": "#388e3c"
      },
      "fonts": {
        "body": "system-ui, -apple-system, sans-serif",
        "mono": "Menlo, monospace",
        "size": {
          "xs": "12px",
          "sm": "14px",
          "md": "16px",
          "lg": "18px"
        }
      },
      "spacing": {
        "xs": "4px",
        "sm": "8px",
        "md": "16px",
        "lg": "24px",
        "xl": "32px"
      }
    },
    "dark": {
      "name": "Dark Theme",
      "colors": {
        "primary": "#3399ff",
        "secondary": "#999999",
        "background": "#1a1a1a",
        "surface": "#2d2d2d",
        "error": "#ff5252",
        "success": "#66bb6a"
      },
      "fonts": {
        "body": "system-ui, -apple-system, sans-serif",
        "mono": "Menlo, monospace"
      }
    }
  },
  "featureFlags": {
    "enableArjunaV2": {
      "enabled": true,
      "environments": ["development", "production"],
      "rolloutPercentage": 100
    },
    "enableCareerInsights": {
      "enabled": true,
      "environments": ["development"],
      "rolloutPercentage": 50
    },
    "enableMobileSync": {
      "enabled": false,
      "environments": ["development"],
      "rolloutPercentage": 0
    }
  }
}
```

### Step 2: JSON Schema Validation

**File:** `config/ui.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "layouts", "components", "themes"],
  "properties": {
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+$"
    },
    "layouts": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["breakpoints"],
        "properties": {
          "breakpoints": {
            "type": "object",
            "properties": {
              "desktop": { "$ref": "#/definitions/breakpoint" },
              "tablet": { "$ref": "#/definitions/breakpoint" },
              "mobile": { "$ref": "#/definitions/breakpoint" }
            }
          }
        }
      }
    },
    "components": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["implementations"],
        "properties": {
          "implementations": {
            "type": "object",
            "additionalProperties": {
              "type": "object",
              "required": ["path", "type"]
            }
          }
        }
      }
    }
  },
  "definitions": {
    "breakpoint": {
      "type": "object",
      "required": ["sections"],
      "properties": {
        "sections": {
          "type": "array",
          "items": { "$ref": "#/definitions/section" }
        }
      }
    },
    "section": {
      "type": "object",
      "required": ["id", "component"],
      "properties": {
        "id": { "type": "string" },
        "component": { "type": "string" },
        "position": { "type": "string" },
        "props": { "type": "object" }
      }
    }
  }
}
```

### Step 3: Python Component Registry

**File:** `src/app/services/ui_registry.py`

```python
import json
from pathlib import Path
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger(__name__)

class ComponentMetadata(BaseModel):
    """Metadata about a component."""
    name: str
    path: str
    type: str  # react, react-native, jinja2, vue, etc.
    required_props: list[str] = []
    optional_props: list[str] = []

class UIConfig:
    """Load and manage UI configuration from JSON."""
    
    def __init__(self, config_path: str = "config/ui.json"):
        self.config_path = Path(config_path)
        self.schema_path = Path("config/ui.schema.json")
        self.config = self._load_config()
        self.components_cache = {}
    
    def _load_config(self) -> Dict[str, Any]:
        """Load and validate configuration."""
        try:
            # Load config file
            with open(self.config_path) as f:
                config = json.load(f)
            
            # Validate against schema
            import jsonschema
            with open(self.schema_path) as f:
                schema = json.load(f)
            
            jsonschema.validate(config, schema)
            logger.info(f"✅ UI config loaded and validated: {self.config_path}")
            
            return config
        
        except FileNotFoundError as e:
            logger.error(f"❌ Config file not found: {e}")
            raise
        
        except ValidationError as e:
            logger.error(f"❌ Config validation failed: {e}")
            raise
    
    def get_layout(self, layout_name: str, breakpoint: str = "desktop") -> Dict[str, Any]:
        """Get layout sections for a specific breakpoint."""
        try:
            layout = self.config["layouts"][layout_name]
            sections = layout["breakpoints"][breakpoint]["sections"]
            return {
                "layout_name": layout_name,
                "breakpoint": breakpoint,
                "sections": sections
            }
        except KeyError as e:
            logger.error(f"Layout not found: {e}")
            return {"error": f"Layout {layout_name} or breakpoint {breakpoint} not found"}
    
    def get_component(self, component_name: str, target: str = "web") -> Optional[ComponentMetadata]:
        """Get component implementation for target platform."""
        try:
            component = self.config["components"][component_name]
            impl = component["implementations"].get(target)
            
            if not impl:
                logger.warning(f"No {target} implementation for {component_name}")
                return None
            
            return ComponentMetadata(
                name=component_name,
                path=impl["path"],
                type=impl["type"],
                required_props=component.get("requiredProps", []),
                optional_props=component.get("optionalProps", [])
            )
        
        except KeyError as e:
            logger.error(f"Component not found: {e}")
            return None
    
    def get_theme(self, theme_name: str = "light") -> Dict[str, Any]:
        """Get theme configuration."""
        return self.config["themes"].get(theme_name, self.config["themes"]["light"])
    
    def is_feature_enabled(self, feature_flag: str, environment: str = "development") -> bool:
        """Check if feature flag is enabled."""
        flag = self.config.get("featureFlags", {}).get(feature_flag, {})
        return flag.get("enabled", False) and environment in flag.get("environments", [])
    
    def reload(self):
        """Reload configuration (for development)."""
        self.config = self._load_config()
        self.components_cache.clear()
        logger.info("✅ UI config reloaded")

# Singleton instance
_ui_config = None

def get_ui_config() -> UIConfig:
    """Get UI config singleton."""
    global _ui_config
    if _ui_config is None:
        _ui_config = UIConfig()
    return _ui_config
```

### Step 4: React Component Loader

**File:** `src/components/LayoutRenderer.tsx`

```typescript
import React from "react";
import { UIConfig } from "../services/uiRegistry";

interface LayoutRendererProps {
  layoutName: string;
  breakpoint: "mobile" | "tablet" | "desktop";
}

/**
 * Dynamically render layout based on config.
 * Loads components on-demand, supports multiple implementations.
 */
export const LayoutRenderer: React.FC<LayoutRendererProps> = ({
  layoutName,
  breakpoint,
}) => {
  const ui = UIConfig.getInstance();
  
  // Get layout sections from config
  const layout = ui.getLayout(layoutName, breakpoint);
  const theme = ui.getTheme();
  
  if (!layout) {
    return <div>Layout not found: {layoutName}</div>;
  }
  
  return (
    <div style={{ fontFamily: theme.fonts.body }}>
      {layout.sections.map((section) => (
        <SectionRenderer
          key={section.id}
          section={section}
          breakpoint={breakpoint}
          theme={theme}
        />
      ))}
    </div>
  );
};

interface SectionRendererProps {
  section: any;
  breakpoint: string;
  theme: any;
}

/**
 * Render individual section with lazy-loaded component.
 */
const SectionRenderer: React.FC<SectionRendererProps> = ({
  section,
  breakpoint,
  theme,
}) => {
  const [Component, setComponent] = React.useState<any>(null);
  const [error, setError] = React.useState<string | null>(null);
  
  const ui = UIConfig.getInstance();
  
  React.useEffect(() => {
    // Get component metadata
    const metadata = ui.getComponent(section.component, "react");
    
    if (!metadata) {
      setError(`Component not found: ${section.component}`);
      return;
    }
    
    // Dynamically import component
    const importComponent = async () => {
      try {
        const mod = await import(metadata.path);
        setComponent(mod.default);
      } catch (e) {
        setError(`Failed to load ${section.component}: ${e}`);
      }
    };
    
    importComponent();
  }, [section.component]);
  
  if (error) {
    return <div style={{ color: "red" }}>❌ {error}</div>;
  }
  
  if (!Component) {
    return <div>⏳ Loading {section.component}...</div>;
  }
  
  // Render component with theme and props
  return (
    <div
      style={{
        position: "absolute",
        [section.position]: 0,
        width: section.props.width,
        ...getThemeStyles(section.position, theme),
      }}
    >
      <Component {...section.props} theme={theme} />
    </div>
  );
};

function getThemeStyles(position: string, theme: any) {
  // Apply theme based on position
  return {
    backgroundColor:
      position === "left" || position === "top"
        ? theme.colors.surface
        : theme.colors.background,
    color: theme.colors.primary,
  };
}
```

### Step 5: Mobile Implementation (React Native)

**File:** `mobile/src/services/ui_registry.ts`

```typescript
import * as FileSystem from "expo-file-system";
import schema from "../../config/ui.json";

export class MobileUIRegistry {
  private static instance: MobileUIRegistry;
  private config: any;
  
  private constructor() {
    this.config = schema;
  }
  
  static getInstance(): MobileUIRegistry {
    if (!MobileUIRegistry.instance) {
      MobileUIRegistry.instance = new MobileUIRegistry();
    }
    return MobileUIRegistry.instance;
  }
  
  /**
   * Get layout optimized for mobile (full-screen, single column).
   */
  getLayout(layoutName: string) {
    const baseLayout = this.config.layouts[layoutName];
    const mobileLayout = baseLayout.breakpoints.mobile;
    
    // Transform for mobile (single column, full screen)
    return mobileLayout.sections.map((section: any) => ({
      ...section,
      position: "full-screen",
      props: {
        ...section.props,
        fullScreen: true,
        compact: true,
      },
    }));
  }
  
  /**
   * Get theme for mobile.
   */
  getTheme(themeName: string = "light") {
    const theme = this.config.themes[themeName];
    
    // Adjust for mobile screens (larger touch targets)
    return {
      ...theme,
      spacing: {
        xs: "8px", // Larger than desktop
        sm: "12px",
        md: "16px",
        lg: "20px",
        xl: "24px",
      },
      fonts: {
        ...theme.fonts,
        size: {
          xs: "14px",
          sm: "16px",
          md: "18px",
          lg: "20px",
        },
      },
    };
  }
}
```

### Step 6: FastAPI Endpoint for UI Config

**File:** `src/app/api/v1/ui.py`

```python
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from src.app.services.ui_registry import get_ui_config

router = APIRouter(prefix="/api/v1/ui", tags=["ui"])

@router.get("/layout/{layout_name}")
async def get_layout(
    layout_name: str,
    breakpoint: str = Query("desktop", enum=["mobile", "tablet", "desktop"])
):
    """Get layout configuration for a specific breakpoint."""
    ui = get_ui_config()
    layout = ui.get_layout(layout_name, breakpoint)
    return JSONResponse(layout)

@router.get("/theme/{theme_name}")
async def get_theme(theme_name: str = "light"):
    """Get theme configuration."""
    ui = get_ui_config()
    return JSONResponse(ui.get_theme(theme_name))

@router.get("/feature-flag/{flag_name}")
async def check_feature_flag(
    flag_name: str,
    environment: str = Query("development")
):
    """Check if feature flag is enabled."""
    ui = get_ui_config()
    enabled = ui.is_feature_enabled(flag_name, environment)
    return {"flag": flag_name, "enabled": enabled}

@router.get("/config")
async def get_full_config():
    """Get complete UI configuration (development only)."""
    ui = get_ui_config()
    return JSONResponse(ui.config)

@router.post("/reload")
async def reload_config():
    """Reload configuration (development only)."""
    ui = get_ui_config()
    ui.reload()
    return {"status": "config reloaded"}
```

---

## Best Practices

### 1. Keep Logic Separate from Configuration

**❌ BAD: Logic in JSON**
```json
{
  "sections": [
    {
      "id": "tasks",
      "component": "TaskList",
      "filter": "status === 'active' && priority > 3"  // Logic in JSON!
    }
  ]
}
```

**✅ GOOD: Configuration in JSON, Logic in Code**
```json
{
  "sections": [
    {
      "id": "tasks",
      "component": "TaskList",
      "props": {
        "filterType": "active_high_priority"  // Just reference
      }
    }
  ]
}
```

```typescript
// Logic lives here
const filterTasks = (tasks, filterType) => {
  if (filterType === "active_high_priority") {
    return tasks.filter(t => t.status === "active" && t.priority > 3);
  }
  // ...
};
```

### 2. Use Schema Validation

Always validate configuration at load time:

```python
import jsonschema

def load_config(path: str):
    with open(path) as f:
        config = json.load(f)
    
    with open("config/ui.schema.json") as f:
        schema = json.load(f)
    
    # Validate immediately
    jsonschema.validate(config, schema)
    
    return config  # Only return if valid
```

### 3. Version Your Schema

```json
{
  "version": "2.0",
  "schema": "ui-config-2.0",
  "migrations": {
    "1.0": "src/migrations/ui_config_v1_to_v2.py"
  }
}
```

When upgrading:
```python
def migrate_v1_to_v2(old_config):
    """Migrate from UI config v1.0 to v2.0."""
    # Handle breaking changes
    return new_config
```

### 4. Support Multiple Environments

```json
{
  "environments": {
    "development": {
      "featureFlags": {
        "enableDebugPanel": true
      }
    },
    "production": {
      "featureFlags": {
        "enableDebugPanel": false
      }
    }
  }
}
```

### 5. Cache Component Implementations

```python
class UIRegistry:
    def __init__(self):
        self.components_cache = {}  # Avoid re-importing
    
    def get_component(self, name: str, target: str):
        cache_key = f"{name}:{target}"
        
        if cache_key in self.components_cache:
            return self.components_cache[cache_key]
        
        # Load and cache
        component = self._load_component(name, target)
        self.components_cache[cache_key] = component
        
        return component
```

### 6. Hot Reload in Development

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if "ui.json" in event.src_path:
            logger.info("🔄 UI config changed, reloading...")
            get_ui_config().reload()

# Watch for changes
observer = Observer()
observer.schedule(
    ConfigFileHandler(),
    path="config",
    recursive=False
)
observer.start()
```

---

## When NOT to Use JSON for UI

### ❌ Complex Interactions
```json
{
  "modal": {
    "actions": [
      {
        "label": "Save",
        "handler": "if (formValid) { saveData(); closeModal(); } else { showError(); }"
      }
    ]
  }
}
```

**Use code instead:**
```typescript
const handleSave = () => {
  if (validateForm()) {
    saveData();
    closeModal();
  } else {
    showError();
  }
};
```

### ❌ Dynamic Lists
```json
{
  "items": ["item1", "item2", "item3"]  // Hard-coded
}
```

**Use API instead:**
```typescript
const items = await fetch("/api/v1/items").then(r => r.json());
```

### ❌ Computed Values
```json
{
  "greeting": "Hello " + userName  // Can't compute in JSON
}
```

**Use code:**
```typescript
const greeting = `Hello ${userName}`;
```

---

## Comparison: JSON vs Alternatives

| Aspect | JSON | YAML | TOML | Custom DSL |
|--------|------|------|------|-----------|
| **Readability** | Good | Excellent | Good | ★★★ |
| **Parsing** | Fast | Slow | Medium | Slow |
| **Validation** | Excellent (JSON Schema) | Good | Good | Custom |
| **Comments** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Nesting** | Deep | Medium | Flat | Varies |
| **IDE Support** | Excellent | Good | Good | Minimal |
| **Learning Curve** | Easy | Easy | Medium | Hard |
| **Multi-Frontend** | ✅ Great | Good | Fair | Custom |

### Recommendation

- **JSON:** Best for strict, validated configs (UI layouts, feature flags)
- **YAML:** Better for hand-edited configs (CI/CD, deployment)
- **Custom DSL:** Only if you have unique needs (rarely needed)

---

## Summary

**Using JSON for swappable UIs is best practice when:**

✅ You have multiple frontend targets (web, mobile, desktop)  
✅ You want to change UI without recompiling  
✅ You need A/B testing and feature flags  
✅ You have strict validation requirements  
✅ You want git-tracked configuration  

**Don't use JSON for:**

❌ Complex business logic  
❌ Dynamic data fetching  
❌ Real-time calculations  
❌ State management  

**Final Score: 8.5/10 for UI configuration** 🎯

