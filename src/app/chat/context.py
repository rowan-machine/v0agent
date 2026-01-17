# src/app/chat/context.py

def build_context(conversation_messages, memory_blocks, max_blocks=6):
    """
    conversation_messages: list[{role, content}]
    memory_blocks: list[str]
    """

    ctx = []

    for m in conversation_messages:
        ctx.append(f"{m['role'].capitalize()}: {m['content']}")

    for block in memory_blocks:
        if len(ctx) >= max_blocks:
            break
        ctx.append(block)

    return ctx
