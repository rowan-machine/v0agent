# sdk/signalflow/analyst.py
"""
SignalFlow Analyst Client

Client for analytics, observability, and LangSmith integration.
Provides access to trace data, feedback, and agent performance metrics.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from .models import (
    TraceFeedback,
    AgentPerformance,
    FeedbackSummary,
)

logger = logging.getLogger(__name__)


@dataclass 
class LangSmithConfig:
    """LangSmith configuration."""
    api_key: str
    project_name: str = "signalflow"
    endpoint: str = "https://api.smith.langchain.com"


class AnalystClient:
    """
    Client for SignalFlow analytics and observability.
    
    Integrates with LangSmith for:
    - Trace exploration and analysis
    - Feedback collection and aggregation
    - Agent performance metrics
    - Cost and latency tracking
    
    Example:
        ```python
        analyst = AnalystClient()
        
        # Get feedback summary
        summary = analyst.get_feedback_summary(days=7)
        print(f"Average score: {summary.avg_score}")
        
        # Get agent performance
        perf = analyst.get_agent_performance("Arjuna")
        print(f"Error rate: {perf.error_rate}%")
        
        # Submit feedback for a trace
        analyst.submit_feedback(run_id="xxx", score=0.9, comment="Helpful!")
        ```
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        project_name: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        """
        Initialize the analyst client.
        
        Args:
            api_key: LangSmith API key (or LANGSMITH_API_KEY env var)
            project_name: LangSmith project name (or LANGSMITH_PROJECT env var)
            endpoint: LangSmith API endpoint (optional)
        """
        self._config = LangSmithConfig(
            api_key=api_key or os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY", ""),
            project_name=project_name or os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT", "signalflow"),
            endpoint=endpoint or os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
        )
        
        self._client = None
        self._initialized = False
    
    def _ensure_client(self):
        """Lazily initialize the LangSmith client."""
        if self._initialized:
            return self._client is not None
        
        self._initialized = True
        
        if not self._config.api_key:
            logger.warning("LangSmith API key not configured. Set LANGSMITH_API_KEY.")
            return False
        
        try:
            from langsmith import Client
            self._client = Client(
                api_key=self._config.api_key,
                api_url=self._config.endpoint,
            )
            logger.info(f"LangSmith client initialized for project: {self._config.project_name}")
            return True
        except ImportError:
            logger.warning("langsmith package not installed. Run: pip install langsmith")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith client: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        """Check if the analyst client is properly configured."""
        return self._ensure_client()
    
    def submit_feedback(
        self,
        run_id: str,
        score: float,
        comment: Optional[str] = None,
        feedback_type: str = "user_rating",
    ) -> bool:
        """
        Submit feedback for a LangSmith trace.
        
        Args:
            run_id: The LangSmith run ID
            score: Score from 0.0 to 1.0
            comment: Optional feedback comment
            feedback_type: Type of feedback (default: user_rating)
            
        Returns:
            True if feedback was submitted successfully
        """
        if not self._ensure_client():
            return False
        
        try:
            self._client.create_feedback(
                run_id=run_id,
                key=feedback_type,
                score=score,
                comment=comment,
            )
            logger.info(f"Submitted feedback for run {run_id}: score={score}")
            return True
        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")
            return False
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific trace run.
        
        Args:
            run_id: The LangSmith run ID
            
        Returns:
            Run details or None if not found
        """
        if not self._ensure_client():
            return None
        
        try:
            run = self._client.read_run(run_id)
            return {
                "id": str(run.id),
                "name": run.name,
                "run_type": run.run_type,
                "status": run.status,
                "start_time": run.start_time,
                "end_time": run.end_time,
                "latency_ms": run.latency_ms,
                "total_tokens": run.total_tokens,
                "total_cost": run.total_cost,
                "error": run.error,
                "inputs": run.inputs,
                "outputs": run.outputs,
                "tags": run.tags,
                "metadata": run.extra,
            }
        except Exception as e:
            logger.error(f"Failed to get run {run_id}: {e}")
            return None
    
    def list_runs(
        self,
        days: int = 7,
        run_type: Optional[str] = None,
        filter_tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List recent trace runs.
        
        Args:
            days: Number of days to look back
            run_type: Filter by run type (e.g., "chain", "llm", "tool")
            filter_tags: Filter by tags
            limit: Maximum number of runs to return
            
        Returns:
            List of run summaries
        """
        if not self._ensure_client():
            return []
        
        try:
            start_time = datetime.now() - timedelta(days=days)
            
            runs = self._client.list_runs(
                project_name=self._config.project_name,
                start_time=start_time,
                run_type=run_type,
                filter=filter_tags,
                limit=limit,
            )
            
            return [
                {
                    "id": str(run.id),
                    "name": run.name,
                    "run_type": run.run_type,
                    "status": run.status,
                    "start_time": run.start_time,
                    "latency_ms": run.latency_ms,
                    "total_tokens": run.total_tokens,
                    "tags": run.tags,
                }
                for run in runs
            ]
        except Exception as e:
            logger.error(f"Failed to list runs: {e}")
            return []
    
    def get_feedback_for_run(self, run_id: str) -> List[TraceFeedback]:
        """
        Get all feedback for a specific run.
        
        Args:
            run_id: The LangSmith run ID
            
        Returns:
            List of feedback items
        """
        if not self._ensure_client():
            return []
        
        try:
            feedbacks = self._client.list_feedback(run_ids=[run_id])
            return [
                TraceFeedback(
                    run_id=str(fb.run_id),
                    score=fb.score or 0,
                    comment=fb.comment,
                    feedback_type=fb.key,
                    created_at=fb.created_at,
                )
                for fb in feedbacks
            ]
        except Exception as e:
            logger.error(f"Failed to get feedback for run {run_id}: {e}")
            return []
    
    def get_feedback_summary(self, days: int = 7) -> FeedbackSummary:
        """
        Get aggregated feedback summary.
        
        Args:
            days: Number of days to aggregate
            
        Returns:
            FeedbackSummary with aggregated metrics
        """
        if not self._ensure_client():
            return FeedbackSummary(
                total_runs=0,
                rated_runs=0,
                period_days=days,
            )
        
        try:
            start_time = datetime.now() - timedelta(days=days)
            
            # Get all runs in the period
            runs = list(self._client.list_runs(
                project_name=self._config.project_name,
                start_time=start_time,
                limit=1000,
            ))
            
            total_runs = len(runs)
            
            # Get feedback
            run_ids = [str(r.id) for r in runs]
            all_feedback = list(self._client.list_feedback(run_ids=run_ids)) if run_ids else []
            
            # Calculate metrics
            scores = [fb.score for fb in all_feedback if fb.score is not None]
            avg_score = sum(scores) / len(scores) if scores else None
            
            # Score distribution
            distribution = {"0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
            for score in scores:
                if score <= 0.2:
                    distribution["0-0.2"] += 1
                elif score <= 0.4:
                    distribution["0.2-0.4"] += 1
                elif score <= 0.6:
                    distribution["0.4-0.6"] += 1
                elif score <= 0.8:
                    distribution["0.6-0.8"] += 1
                else:
                    distribution["0.8-1.0"] += 1
            
            return FeedbackSummary(
                total_runs=total_runs,
                rated_runs=len(scores),
                avg_score=avg_score,
                score_distribution=distribution,
                period_days=days,
            )
        except Exception as e:
            logger.error(f"Failed to get feedback summary: {e}")
            return FeedbackSummary(
                total_runs=0,
                rated_runs=0,
                period_days=days,
            )
    
    def get_agent_performance(
        self,
        agent_name: str,
        days: int = 7,
    ) -> AgentPerformance:
        """
        Get performance metrics for a specific agent.
        
        Args:
            agent_name: Name of the agent (e.g., "Arjuna", "DIKWSynthesizer")
            days: Number of days to analyze
            
        Returns:
            AgentPerformance metrics
        """
        if not self._ensure_client():
            return AgentPerformance(
                agent_name=agent_name,
                total_runs=0,
                avg_latency_ms=0,
                error_rate=0,
                period_days=days,
            )
        
        try:
            start_time = datetime.now() - timedelta(days=days)
            
            # Filter runs by agent tag
            runs = list(self._client.list_runs(
                project_name=self._config.project_name,
                start_time=start_time,
                filter=[f"agent:{agent_name}"],
                limit=500,
            ))
            
            if not runs:
                return AgentPerformance(
                    agent_name=agent_name,
                    total_runs=0,
                    avg_latency_ms=0,
                    error_rate=0,
                    period_days=days,
                )
            
            # Calculate metrics
            total_runs = len(runs)
            latencies = [r.latency_ms for r in runs if r.latency_ms]
            errors = [r for r in runs if r.error]
            
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            error_rate = (len(errors) / total_runs) * 100 if total_runs > 0 else 0
            
            # Get average feedback score
            run_ids = [str(r.id) for r in runs]
            feedbacks = list(self._client.list_feedback(run_ids=run_ids)) if run_ids else []
            scores = [fb.score for fb in feedbacks if fb.score is not None]
            avg_score = sum(scores) / len(scores) if scores else None
            
            return AgentPerformance(
                agent_name=agent_name,
                total_runs=total_runs,
                avg_latency_ms=avg_latency,
                avg_score=avg_score,
                error_rate=error_rate,
                period_days=days,
            )
        except Exception as e:
            logger.error(f"Failed to get agent performance: {e}")
            return AgentPerformance(
                agent_name=agent_name,
                total_runs=0,
                avg_latency_ms=0,
                error_rate=0,
                period_days=days,
            )
    
    def get_project_stats(self) -> Dict[str, Any]:
        """
        Get overall project statistics.
        
        Returns:
            Project statistics including costs, tokens, and run counts
        """
        if not self._ensure_client():
            return {"error": "Client not configured"}
        
        try:
            # Get stats for last 30 days
            stats_7d = self.get_feedback_summary(days=7)
            stats_30d = self.get_feedback_summary(days=30)
            
            return {
                "project_name": self._config.project_name,
                "last_7_days": {
                    "total_runs": stats_7d.total_runs,
                    "rated_runs": stats_7d.rated_runs,
                    "avg_score": stats_7d.avg_score,
                },
                "last_30_days": {
                    "total_runs": stats_30d.total_runs,
                    "rated_runs": stats_30d.rated_runs,
                    "avg_score": stats_30d.avg_score,
                },
            }
        except Exception as e:
            logger.error(f"Failed to get project stats: {e}")
            return {"error": str(e)}
