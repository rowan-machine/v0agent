"""
LangSmith Evaluation Module for SignalFlow Agents

This module provides:
1. Evaluators to score agent outputs
2. Feedback submission to LangSmith
3. Dataset management for evaluation runs
4. Online evaluation during production

Key Concepts:
- **Evaluators**: Score agent outputs on dimensions like relevance, accuracy, helpfulness
- **Feedback**: User feedback (thumbs up/down, corrections) stored with traces
- **Datasets**: Collections of examples for systematic evaluation
- **Online Evaluation**: Real-time scoring during production use

Usage:
    # Submit feedback on a trace
    from .evaluations import submit_feedback
    submit_feedback(
        run_id="...",
        score=0.8,
        key="helpfulness",
        comment="Accurate but could be more concise"
    )
    
    # Run evaluation on an agent output
    from .evaluations import evaluate_output
    scores = evaluate_output(
        output="Agent response text",
        expected="Expected output",
        evaluators=["relevance", "accuracy"]
    )
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def is_evaluation_enabled() -> bool:
    """Check if LangSmith evaluation is enabled."""
    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY", "")
    return bool(api_key)


@dataclass
class EvaluationResult:
    """Result from an evaluation."""
    key: str  # Evaluation metric name
    score: Optional[float]  # 0.0 to 1.0
    reasoning: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# FEEDBACK SUBMISSION
# =============================================================================

def submit_feedback(
    run_id: str,
    key: str,
    score: Optional[float] = None,
    value: Optional[str] = None,
    comment: Optional[str] = None,
    correction: Optional[str] = None,
    source_info: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Submit feedback for a LangSmith trace run.
    
    This is the primary way to provide human feedback that can be used
    to improve agent prompts over time.
    
    Args:
        run_id: The LangSmith run ID to provide feedback for
        key: Feedback dimension (e.g., "helpfulness", "accuracy", "relevance")
        score: Numeric score from 0.0 to 1.0 (optional)
        value: Categorical value (e.g., "correct", "incorrect", "partial")
        comment: Freeform comment about the output
        correction: What the correct output should have been
        source_info: Metadata about who/what provided the feedback
    
    Returns:
        Feedback ID if successful, None otherwise
    """
    if not is_evaluation_enabled():
        logger.debug("Evaluation disabled, skipping feedback submission")
        return None
    
    try:
        from langsmith import Client
        
        client = Client()
        
        feedback = client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
            value=value,
            comment=comment,
            correction={"value": correction} if correction else None,
            source_info=source_info or {"type": "app"},
        )
        
        logger.info(f"Submitted feedback for run {run_id}: {key}={score or value}")
        return feedback.id
        
    except ImportError:
        logger.warning("langsmith package not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        return None


def submit_thumbs_feedback(
    run_id: str,
    is_positive: bool,
    comment: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """
    Submit simple thumbs up/down feedback.
    
    Args:
        run_id: The LangSmith run ID
        is_positive: True for thumbs up, False for thumbs down
        comment: Optional comment explaining the rating
        user_id: Optional user ID for tracking
    
    Returns:
        Feedback ID if successful
    """
    return submit_feedback(
        run_id=run_id,
        key="user_feedback",
        score=1.0 if is_positive else 0.0,
        value="positive" if is_positive else "negative",
        comment=comment,
        source_info={"type": "user", "user_id": user_id} if user_id else None,
    )


# =============================================================================
# BUILT-IN EVALUATORS
# =============================================================================

def evaluate_relevance(
    output: str,
    context: str,
    question: Optional[str] = None,
) -> EvaluationResult:
    """
    Evaluate if the output is relevant to the context/question.
    
    Uses GPT to score relevance on a 0-1 scale.
    """
    from .llm import ask as ask_llm
    
    prompt = f"""Score the relevance of the following response to the given context.

Context:
{context[:1000]}

{f"Question: {question}" if question else ""}

Response:
{output[:1000]}

Score from 0.0 (completely irrelevant) to 1.0 (highly relevant).
Respond with just the score and a one-sentence explanation.
Format: SCORE: 0.X REASON: <explanation>"""

    try:
        result = ask_llm(prompt, model="gpt-4o-mini", max_tokens=100)
        
        # Parse score from response
        import re
        match = re.search(r'SCORE:\s*([\d.]+)', result)
        score = float(match.group(1)) if match else 0.5
        
        reason_match = re.search(r'REASON:\s*(.+)', result, re.DOTALL)
        reasoning = reason_match.group(1).strip() if reason_match else result
        
        return EvaluationResult(
            key="relevance",
            score=min(1.0, max(0.0, score)),
            reasoning=reasoning,
        )
    except Exception as e:
        logger.error(f"Relevance evaluation failed: {e}")
        return EvaluationResult(key="relevance", score=None, reasoning=str(e))


def evaluate_accuracy(
    output: str,
    expected: str,
    strict: bool = False,
) -> EvaluationResult:
    """
    Evaluate if the output matches the expected output.
    
    Args:
        output: The actual output to evaluate
        expected: The expected/ground truth output
        strict: If True, requires exact match; if False, uses semantic similarity
    """
    if strict:
        # Exact match (normalized)
        normalized_output = output.strip().lower()
        normalized_expected = expected.strip().lower()
        score = 1.0 if normalized_output == normalized_expected else 0.0
        return EvaluationResult(
            key="accuracy",
            score=score,
            reasoning="Exact match" if score == 1.0 else "No exact match",
        )
    
    # Semantic similarity check
    from .llm import ask as ask_llm
    
    prompt = f"""Compare these two outputs and score their semantic similarity.

Expected Output:
{expected[:500]}

Actual Output:
{output[:500]}

Score from 0.0 (completely different) to 1.0 (semantically identical).
Consider meaning, not exact wording.
Format: SCORE: 0.X REASON: <explanation>"""

    try:
        result = ask_llm(prompt, model="gpt-4o-mini", max_tokens=100)
        
        import re
        match = re.search(r'SCORE:\s*([\d.]+)', result)
        score = float(match.group(1)) if match else 0.5
        
        reason_match = re.search(r'REASON:\s*(.+)', result, re.DOTALL)
        reasoning = reason_match.group(1).strip() if reason_match else result
        
        return EvaluationResult(
            key="accuracy",
            score=min(1.0, max(0.0, score)),
            reasoning=reasoning,
        )
    except Exception as e:
        logger.error(f"Accuracy evaluation failed: {e}")
        return EvaluationResult(key="accuracy", score=None, reasoning=str(e))


def evaluate_helpfulness(
    output: str,
    user_request: str,
) -> EvaluationResult:
    """
    Evaluate if the output is helpful for the user's request.
    """
    from .llm import ask as ask_llm
    
    prompt = f"""Evaluate how helpful this response is for the user's request.

User Request:
{user_request[:500]}

Response:
{output[:1000]}

Consider:
- Does it address the user's need?
- Is it actionable and clear?
- Does it provide useful information?

Score from 0.0 (not helpful) to 1.0 (very helpful).
Format: SCORE: 0.X REASON: <explanation>"""

    try:
        result = ask_llm(prompt, model="gpt-4o-mini", max_tokens=150)
        
        import re
        match = re.search(r'SCORE:\s*([\d.]+)', result)
        score = float(match.group(1)) if match else 0.5
        
        reason_match = re.search(r'REASON:\s*(.+)', result, re.DOTALL)
        reasoning = reason_match.group(1).strip() if reason_match else result
        
        return EvaluationResult(
            key="helpfulness",
            score=min(1.0, max(0.0, score)),
            reasoning=reasoning,
        )
    except Exception as e:
        logger.error(f"Helpfulness evaluation failed: {e}")
        return EvaluationResult(key="helpfulness", score=None, reasoning=str(e))


def evaluate_signal_quality(
    signal_text: str,
    signal_type: str,
    source_context: str,
) -> EvaluationResult:
    """
    Evaluate the quality of an extracted signal.
    
    Specific to SignalFlow's signal extraction use case.
    """
    from .llm import ask as ask_llm
    
    prompt = f"""Evaluate the quality of this extracted signal.

Signal Type: {signal_type}
Signal Text: {signal_text}

Source Context (meeting transcript excerpt):
{source_context[:500]}

Evaluate based on:
1. Is this a valid {signal_type}? (action_item, decision, blocker, risk, idea)
2. Is it actionable and specific?
3. Is it correctly extracted from the context?
4. Does it capture the right owner/assignee if applicable?

Score from 0.0 (poor quality) to 1.0 (high quality signal).
Format: SCORE: 0.X REASON: <explanation>"""

    try:
        result = ask_llm(prompt, model="gpt-4o-mini", max_tokens=200)
        
        import re
        match = re.search(r'SCORE:\s*([\d.]+)', result)
        score = float(match.group(1)) if match else 0.5
        
        reason_match = re.search(r'REASON:\s*(.+)', result, re.DOTALL)
        reasoning = reason_match.group(1).strip() if reason_match else result
        
        return EvaluationResult(
            key="signal_quality",
            score=min(1.0, max(0.0, score)),
            reasoning=reasoning,
            metadata={"signal_type": signal_type},
        )
    except Exception as e:
        logger.error(f"Signal quality evaluation failed: {e}")
        return EvaluationResult(key="signal_quality", score=None, reasoning=str(e))


def evaluate_dikw_promotion(
    original_item: str,
    original_level: str,
    promoted_item: str,
    promoted_level: str,
) -> EvaluationResult:
    """
    Evaluate if a DIKW promotion was appropriate.
    
    Specific to SignalFlow's knowledge synthesis.
    """
    from .llm import ask as ask_llm
    
    level_descriptions = {
        "data": "raw facts and observations",
        "information": "organized, contextualized data",
        "knowledge": "actionable insights and patterns",
        "wisdom": "principles and decision frameworks",
    }
    
    prompt = f"""Evaluate this DIKW pyramid promotion.

Original ({original_level} - {level_descriptions.get(original_level, '')}):
{original_item}

Promoted to ({promoted_level} - {level_descriptions.get(promoted_level, '')}):
{promoted_item}

Evaluate:
1. Is the promotion appropriate (not skipping levels)?
2. Does the promoted version add meaningful abstraction/synthesis?
3. Does it maintain accuracy while adding insight?
4. Is the new level classification correct?

Score from 0.0 (inappropriate promotion) to 1.0 (excellent promotion).
Format: SCORE: 0.X REASON: <explanation>"""

    try:
        result = ask_llm(prompt, model="gpt-4o-mini", max_tokens=200)
        
        import re
        match = re.search(r'SCORE:\s*([\d.]+)', result)
        score = float(match.group(1)) if match else 0.5
        
        reason_match = re.search(r'REASON:\s*(.+)', result, re.DOTALL)
        reasoning = reason_match.group(1).strip() if reason_match else result
        
        return EvaluationResult(
            key="dikw_promotion_quality",
            score=min(1.0, max(0.0, score)),
            reasoning=reasoning,
            metadata={
                "original_level": original_level,
                "promoted_level": promoted_level,
            },
        )
    except Exception as e:
        logger.error(f"DIKW promotion evaluation failed: {e}")
        return EvaluationResult(key="dikw_promotion_quality", score=None, reasoning=str(e))


# =============================================================================
# BATCH EVALUATION
# =============================================================================

def evaluate_output(
    output: str,
    evaluator_names: List[str],
    context: Optional[str] = None,
    expected: Optional[str] = None,
    user_request: Optional[str] = None,
    run_id: Optional[str] = None,
    submit_to_langsmith: bool = True,
) -> Dict[str, EvaluationResult]:
    """
    Run multiple evaluators on an output and optionally submit to LangSmith.
    
    Args:
        output: The output to evaluate
        evaluator_names: List of evaluators to run ["relevance", "accuracy", "helpfulness"]
        context: Context for relevance evaluation
        expected: Expected output for accuracy evaluation
        user_request: User request for helpfulness evaluation
        run_id: LangSmith run ID to attach feedback to
        submit_to_langsmith: Whether to submit feedback to LangSmith
    
    Returns:
        Dict mapping evaluator names to results
    """
    results = {}
    
    for name in evaluator_names:
        if name == "relevance" and context:
            results[name] = evaluate_relevance(output, context)
        elif name == "accuracy" and expected:
            results[name] = evaluate_accuracy(output, expected)
        elif name == "helpfulness" and user_request:
            results[name] = evaluate_helpfulness(output, user_request)
        else:
            logger.warning(f"Skipping evaluator {name}: missing required input")
            continue
        
        # Submit to LangSmith if enabled
        if submit_to_langsmith and run_id and results[name].score is not None:
            submit_feedback(
                run_id=run_id,
                key=name,
                score=results[name].score,
                comment=results[name].reasoning,
                source_info={"type": "auto_evaluator"},
            )
    
    return results


# =============================================================================
# DATASET MANAGEMENT
# =============================================================================

def create_dataset(
    name: str,
    description: Optional[str] = None,
) -> Optional[str]:
    """
    Create a new evaluation dataset in LangSmith.
    
    Returns:
        Dataset ID if successful
    """
    if not is_evaluation_enabled():
        return None
    
    try:
        from langsmith import Client
        client = Client()
        
        dataset = client.create_dataset(
            dataset_name=name,
            description=description,
        )
        
        logger.info(f"Created dataset: {name} (ID: {dataset.id})")
        return dataset.id
        
    except Exception as e:
        logger.error(f"Failed to create dataset: {e}")
        return None


def add_example_to_dataset(
    dataset_name: str,
    inputs: Dict[str, Any],
    outputs: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Add an example to an evaluation dataset.
    
    Args:
        dataset_name: Name of the dataset
        inputs: Input data for the example
        outputs: Expected outputs (for ground truth)
        metadata: Additional metadata
    
    Returns:
        Example ID if successful
    """
    if not is_evaluation_enabled():
        return None
    
    try:
        from langsmith import Client
        client = Client()
        
        example = client.create_example(
            inputs=inputs,
            outputs=outputs,
            dataset_name=dataset_name,
            metadata=metadata,
        )
        
        logger.info(f"Added example to dataset {dataset_name}")
        return example.id
        
    except Exception as e:
        logger.error(f"Failed to add example: {e}")
        return None


# =============================================================================
# ONLINE EVALUATION (PRODUCTION)
# =============================================================================

def create_online_evaluator(
    evaluator_name: str,
    run_filter: Optional[Dict[str, Any]] = None,
):
    """
    Create an online evaluator that runs automatically on matching traces.
    
    This enables continuous evaluation of production traffic.
    
    Note: Requires LangSmith Pro or Enterprise.
    """
    if not is_evaluation_enabled():
        logger.warning("Evaluation not enabled")
        return None
    
    logger.info(f"Online evaluator '{evaluator_name}' would be created (requires LangSmith Pro)")
    return None  # Placeholder - actual implementation requires LangSmith Pro API


# =============================================================================
# FEEDBACK AGGREGATION
# =============================================================================

def get_feedback_summary(
    agent_name: Optional[str] = None,
    days: int = 7,
) -> Dict[str, Any]:
    """
    Get aggregated feedback summary for an agent.
    
    Args:
        agent_name: Filter by agent name (or None for all)
        days: Number of days to look back
    
    Returns:
        Summary dict with average scores, counts, etc.
    """
    if not is_evaluation_enabled():
        return {"error": "Evaluation not enabled"}
    
    try:
        from langsmith import Client
        from datetime import timedelta
        
        client = Client()
        
        # Query runs with feedback
        start_time = datetime.now() - timedelta(days=days)
        
        runs = client.list_runs(
            project_name=os.environ.get("LANGSMITH_PROJECT", "signalflow"),
            start_time=start_time,
            filter=f'has(feedback_stats)' + (f' and eq(metadata.agent_name, "{agent_name}")' if agent_name else ''),
            limit=1000,
        )
        
        # Aggregate feedback
        feedback_counts = {}
        feedback_scores = {}
        
        for run in runs:
            if run.feedback_stats:
                for key, stats in run.feedback_stats.items():
                    if key not in feedback_counts:
                        feedback_counts[key] = 0
                        feedback_scores[key] = []
                    feedback_counts[key] += stats.get('n', 0)
                    if stats.get('avg') is not None:
                        feedback_scores[key].append(stats['avg'])
        
        # Calculate averages
        summary = {
            "agent_name": agent_name or "all",
            "period_days": days,
            "metrics": {},
        }
        
        for key in feedback_counts:
            avg_score = sum(feedback_scores.get(key, [])) / len(feedback_scores.get(key, [1])) if feedback_scores.get(key) else None
            summary["metrics"][key] = {
                "count": feedback_counts[key],
                "average_score": round(avg_score, 3) if avg_score else None,
            }
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get feedback summary: {e}")
        return {"error": str(e)}
