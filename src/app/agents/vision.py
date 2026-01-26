# src/app/agents/vision.py
"""
VisionAgent - AI-powered image analysis.

Handles image analysis using GPT-4 Vision for:
- Meeting screenshot analysis
- Diagram/chart interpretation
- Document OCR and extraction
- Visual content summarization

Part of Phase 1 agent extraction (Checkpoint 1.x).
"""

from .base import BaseAgent, AgentConfig


class VisionAgent(BaseAgent):
    """
    Agent for analyzing images using GPT-4 Vision.
    
    Extracts text, diagrams, and context from screenshots
    to enrich meeting and document records.
    """
    
    def __init__(self):
        config = AgentConfig(
            name="vision",
            description="Analyzes images using GPT-4 Vision",
            model="gpt-4o",  # Vision requires gpt-4o
            max_tokens=1000,
            temperature=0.3,  # Lower temp for factual extraction
        )
        super().__init__(config)
    
    def _get_system_prompt(self) -> str:
        return """You are an image analysis assistant. Your job is to:
1. Extract all visible text accurately
2. Describe diagrams, charts, and visual elements
3. Identify key information (names, dates, action items)
4. Summarize the content for searchability

Be thorough but concise. Structure your output for easy parsing."""
    
    async def analyze(self, image_base64: str, context: str = None) -> str:
        """
        Analyze an image and return structured description.
        
        Args:
            image_base64: Base64-encoded image data
            context: Optional context about what to look for
            
        Returns:
            Structured text description of the image
        """
        prompt = context or """Analyze this image and provide a detailed description. 
If it's a screenshot of a meeting, diagram, or document:
- Summarize the key information visible
- Extract any text, names, dates, or action items
- Describe any diagrams, charts, or visual elements
- Note anything that seems important for meeting context

Return the analysis as structured text that can be stored and searched."""
        
        # Use the raw LLM call for vision (needs special message format)
        from ..llm import _openai_client_once
        
        resp = _client_once().chat.completions.create(
            model=self.config.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=self.config.max_tokens
        )
        
        return resp.choices[0].message.content.strip()
    
    def analyze_sync(self, image_base64: str, context: str = None) -> str:
        """Synchronous wrapper for analyze()."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.analyze(image_base64, context)
        )


# Singleton instance
_vision_agent = None


def get_vision_agent() -> VisionAgent:
    """Get or create the singleton VisionAgent instance."""
    global _vision_agent
    if _vision_agent is None:
        _vision_agent = VisionAgent()
    return _vision_agent


# -------------------------
# Adapter Functions (Backward Compatibility)
# -------------------------

def analyze_image_adapter(image_base64: str, prompt: str = None) -> str:
    """
    Backward-compatible adapter for analyze_image().
    
    Replaces direct llm.analyze_image calls.
    Use lazy import in endpoint files:
        from .agents.vision import analyze_image_adapter
    """
    agent = get_vision_agent()
    return agent.analyze_sync(image_base64, prompt)
