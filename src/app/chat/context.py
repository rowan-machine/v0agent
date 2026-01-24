# src/app/chat/context.py

def build_context(conversation_messages, memory_blocks, max_blocks=6, include_mindmap=True):
    """
    Build conversation context with memory blocks and optional mindmap synthesis.
    
    Args:
        conversation_messages: list[{role, content}]
        memory_blocks: list[str]
        max_blocks: maximum memory blocks to include
        include_mindmap: whether to include mindmap synthesis
    """

    ctx = []

    # Add recent conversation messages
    for m in conversation_messages:
        ctx.append(f"{m['role'].capitalize()}: {m['content']}")

    # Add memory blocks (documents, meetings, signals)
    for block in memory_blocks:
        if len(ctx) >= max_blocks:
            break
        ctx.append(block)

    # Add mindmap synthesis if available and requested
    if include_mindmap:
        try:
            from ..services.mindmap_synthesis import MindmapSynthesizer
            synthesis = MindmapSynthesizer.get_current_synthesis()
            
            if synthesis:
                synthesis_text = synthesis.get('synthesis_text', '')
                key_topics = synthesis.get('key_topics', [])
                
                # Create formatted mindmap context
                mindmap_context = "[Knowledge Synthesis from Mindmaps]:\n"
                mindmap_context += synthesis_text[:500]  # Limit to first 500 chars
                
                if key_topics:
                    mindmap_context += "\n\nKey Topics: " + ", ".join(key_topics[:10])
                
                ctx.append(mindmap_context)
        except Exception as e:
            # Fail silently if mindmap service has issues
            import logging
            logging.warning(f"Error including mindmap context: {e}")

    return ctx
