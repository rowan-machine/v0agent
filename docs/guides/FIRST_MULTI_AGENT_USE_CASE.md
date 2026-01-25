# First Multi-Agent Use Case: Automatic Daily Context Briefing

**Status:** Proposed  
**Priority:** High  
**Estimated Effort:** Small (1-2 sprints)  
**Value:** High (improves daily user experience significantly)

---

## Executive Summary

The first multi-agent autonomous use case is an **Automatic Daily Context Briefing** that runs when a user starts their workday. This leverages the existing AgentBus to coordinate between MeetingAnalyzerAgent, DIKWSynthesizerAgent, and ArjunaAgent to generate a personalized briefing.

### Why This Use Case?

1. **High User Value**: Users get an instant overview of what matters today
2. **Uses Existing Infrastructure**: AgentBus ✅, All agents ✅, NotificationQueue ✅
3. **Small Scope**: Single trigger, coordinated output
4. **Demonstrates Multi-Agent**: Shows clear value of agents working together
5. **Foundation for More**: Pattern can be reused for other autonomous workflows

---

## User Story

> "As a knowledge worker, when I start my day, I want an automatic briefing that summarizes what happened since I last logged in, what's pending, and what I should focus on today."

### Current State (Manual)
1. User opens dashboard
2. User manually checks tickets
3. User opens meetings to see recent decisions
4. User checks signals for pending actions
5. User decides what to focus on

### Future State (Autonomous)
1. User opens dashboard
2. **Multi-agent briefing appears automatically:**
   - Recent meeting highlights (from MeetingAnalyzer)
   - Knowledge items needing attention (from DIKWSynthesizer)  
   - Suggested focus based on mode and sprint day (from Arjuna)
   - Pending accountability items

---

## Technical Design

### 1. Trigger Mechanism

```python
# In main.py or a startup hook
async def on_user_session_start(user_id: str):
    """Triggered when user logs in or opens dashboard."""
    
    # Check if briefing was already generated today
    last_briefing = await get_last_briefing(user_id)
    if last_briefing and last_briefing.date == today():
        return last_briefing
    
    # Trigger multi-agent briefing workflow
    await generate_daily_briefing(user_id)
```

### 2. Agent Coordination via AgentBus

```python
# src/app/services/daily_briefing.py (NEW)

from .agent_bus import get_agent_bus, AgentMessage, MessageType

async def generate_daily_briefing(user_id: str):
    """Coordinate agents to generate daily briefing."""
    bus = get_agent_bus()
    correlation_id = str(uuid.uuid4())
    
    # Step 1: Request meeting summary from MeetingAnalyzer
    bus.send(AgentMessage(
        source_agent="briefing_orchestrator",
        target_agent="meeting_analyzer",
        message_type=MessageType.QUERY,
        content={
            "action": "summarize_recent",
            "since_hours": 24,
            "user_id": user_id,
            "correlation_id": correlation_id,
        }
    ))
    
    # Step 2: Request knowledge priorities from DIKWSynthesizer
    bus.send(AgentMessage(
        source_agent="briefing_orchestrator",
        target_agent="dikw_synthesizer",
        message_type=MessageType.QUERY,
        content={
            "action": "pending_promotions",
            "user_id": user_id,
            "correlation_id": correlation_id,
        }
    ))
    
    # Step 3: Request focus recommendation from Arjuna
    bus.send(AgentMessage(
        source_agent="briefing_orchestrator",
        target_agent="arjuna",
        message_type=MessageType.QUERY,
        content={
            "action": "daily_focus",
            "user_id": user_id,
            "correlation_id": correlation_id,
        }
    ))
    
    # Step 4: Wait for responses and aggregate
    # (async polling or callback mechanism)
```

### 3. Response Aggregation

```python
async def aggregate_briefing_responses(correlation_id: str):
    """Collect responses from all agents and compile briefing."""
    
    responses = await wait_for_responses(correlation_id, timeout=10)
    
    briefing = {
        "generated_at": datetime.now().isoformat(),
        "sections": []
    }
    
    if "meeting_analyzer" in responses:
        briefing["sections"].append({
            "title": "📅 Recent Meetings",
            "content": responses["meeting_analyzer"]["summary"],
            "items": responses["meeting_analyzer"]["highlights"]
        })
    
    if "dikw_synthesizer" in responses:
        briefing["sections"].append({
            "title": "📚 Knowledge Updates",
            "content": responses["dikw_synthesizer"]["summary"],
            "items": responses["dikw_synthesizer"]["pending_items"]
        })
    
    if "arjuna" in responses:
        briefing["sections"].append({
            "title": "🎯 Today's Focus",
            "content": responses["arjuna"]["recommendation"],
            "suggested_mode": responses["arjuna"]["suggested_mode"]
        })
    
    return briefing
```

### 4. UI Integration

```html
<!-- Dashboard widget for daily briefing -->
<div class="daily-briefing-widget" id="dailyBriefing">
  <h3>🌅 Daily Briefing</h3>
  <div class="briefing-loading">Loading your briefing...</div>
  <div class="briefing-content" style="display: none;">
    <!-- Populated by JavaScript -->
  </div>
</div>

<script>
async function loadDailyBriefing() {
  const response = await fetch('/api/briefing/daily');
  const briefing = await response.json();
  renderBriefing(briefing);
}

// Auto-load on dashboard
if (window.location.pathname === '/') {
  loadDailyBriefing();
}
</script>
```

---

## Implementation Steps

### Phase 1: Agent Message Handlers (Week 1)
1. Add `summarize_recent` handler to MeetingAnalyzerAgent
2. Add `pending_promotions` handler to DIKWSynthesizerAgent
3. Add `daily_focus` handler to ArjunaAgent
4. Test each handler independently

### Phase 2: Orchestration Service (Week 1)
1. Create `daily_briefing.py` service
2. Implement message coordination via AgentBus
3. Add response aggregation logic
4. Add caching to avoid regenerating same-day briefings

### Phase 3: API & UI (Week 2)
1. Add `/api/briefing/daily` endpoint
2. Create dashboard briefing widget
3. Add notification for new briefings
4. Style to match existing theme

### Phase 4: Testing & Polish (Week 2)
1. Write tests for agent handlers
2. Write tests for orchestration
3. Add fallback for when agents don't respond
4. Performance tuning

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Briefing generation time | < 5 seconds |
| Agent response rate | > 95% |
| User engagement with briefing | > 70% view daily |
| User satisfaction (survey) | > 4/5 stars |

---

## Future Extensions

Once this pattern is established:
1. **Weekly Summary**: Same pattern, weekly aggregation
2. **Pre-Meeting Prep**: Auto-briefing before scheduled meetings
3. **End-of-Day Review**: Summarize what was accomplished
4. **Sprint Retrospective**: Auto-generate retrospective content

---

## Dependencies

- ✅ AgentBus (implemented)
- ✅ MeetingAnalyzerAgent (implemented)
- ✅ DIKWSynthesizerAgent (implemented)
- ✅ ArjunaAgent (implemented)
- ✅ NotificationQueue (implemented)
- 🔄 Agent message handlers (need to add specific actions)
- 📋 Dashboard briefing widget (new)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Agent timeout | Default to partial briefing with available data |
| Empty data (new user) | Show onboarding tips instead of briefing |
| High load | Cache briefings, generate async |
| Agent errors | Graceful degradation, show error section only |

---

## Summary

This first multi-agent use case establishes the pattern for autonomous agent coordination:
1. **Orchestrator** triggers workflow
2. **Agents** respond via **AgentBus**
3. **Aggregator** compiles responses
4. **UI** displays result to user

By implementing this, we prove the multi-agent architecture and create a foundation for more complex autonomous workflows.
