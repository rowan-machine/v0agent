# src/app/services/signal_learning.py
"""
Signal Learning Service - Feedback-driven AI improvement

This service implements the Signal feedback → AI learning loop (PC-1):
1. Analyzes patterns in user feedback (approve/reject/archive) on signals
2. Generates learning context for MeetingAnalyzerAgent prompts
3. Stores learnings in ai_memory for long-term retention
4. Provides signal quality hints based on historical patterns

The feedback loop helps the AI:
- Learn which signal types are most valuable to the user
- Identify patterns in rejected signals to avoid similar extractions
- Understand user preferences for signal phrasing and detail level
- Track signal categories that need more attention
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import logging

from ..infrastructure.supabase_client import get_supabase_client as get_supabase

logger = logging.getLogger(__name__)


# =============================================================================
# SIGNAL FEEDBACK PATTERNS
# =============================================================================

class SignalLearningService:
    """
    Service for analyzing signal feedback and generating learning context.
    
    The service maintains a feedback-driven learning loop:
    1. Collect feedback from user actions (approve, reject, archive)
    2. Analyze patterns in feedback data
    3. Generate learning hints for signal extraction
    4. Store learnings in ai_memory for context retrieval
    """
    
    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id
        self._feedback_cache: Dict[str, Any] = {}
        self._cache_expiry: Optional[datetime] = None
    
    def get_feedback_summary(self, days: int = 90) -> Dict[str, Any]:
        """
        Get a summary of signal feedback patterns.
        
        Returns:
            Dict with feedback statistics by signal type and overall patterns
        """
        supabase = get_supabase()
        if not supabase:
            logger.warning("Supabase not available for feedback summary")
            return self._empty_summary()
        
        return self._get_feedback_summary_supabase(supabase, days)
    
    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary when no data available."""
        return {
            "by_type": {},
            "total_feedback": 0,
            "approval_rate": 0.0,
            "rejection_rate": 0.0,
            "rejected_patterns": [],
            "approved_patterns": []
        }
    
    def _get_feedback_summary_supabase(self, supabase, days: int) -> Dict[str, Any]:
        """Supabase implementation for feedback summary."""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Build filter for user if specified
        filters = {"created_at": {"gte": cutoff_date}}
        if self.user_id:
            filters["user_id"] = self.user_id
        
        try:
            # Get all feedback in date range
            query = supabase.table("signal_feedback").select(
                "signal_type, signal_text, feedback, created_at"
            ).gte("created_at", cutoff_date)
            
            if self.user_id:
                query = query.eq("user_id", self.user_id)
            
            result = query.execute()
            rows = result.data or []
            
            # Aggregate manually
            type_feedback_counts = {}
            rejected = []
            approved = []
            
            for row in rows:
                key = f"{row['signal_type']}:{row['feedback']}"
                type_feedback_counts[key] = type_feedback_counts.get(key, 0) + 1
                
                if row['feedback'] == 'down':
                    rejected.append(row)
                elif row['feedback'] == 'up':
                    approved.append(row)
            
            # Convert to list format
            type_counts = [
                {"signal_type": k.split(":")[0], "feedback": k.split(":")[1], "count": v}
                for k, v in type_feedback_counts.items()
            ]
            
            return self._build_summary(type_counts, rejected[:50], approved[:50])
        
        except Exception as e:
            logger.error(f"Failed to get feedback summary from Supabase: {e}")
            return self._empty_summary()
    
    def _build_summary(
        self, 
        type_counts: List[Dict], 
        rejected: List[Dict], 
        approved: List[Dict]
    ) -> Dict[str, Any]:
        """Build a structured summary from raw feedback data."""
        
        # Calculate acceptance rates by signal type
        by_type = {}
        for row in type_counts:
            signal_type = row.get("signal_type") or row.get(0, "unknown")
            feedback = row.get("feedback") or row.get(1, "unknown")
            count = row.get("count") or row.get(2, 0)
            
            if signal_type not in by_type:
                by_type[signal_type] = {"approved": 0, "rejected": 0, "archived": 0, "completed": 0}
            
            if feedback == "up":
                by_type[signal_type]["approved"] += count
            elif feedback == "down":
                by_type[signal_type]["rejected"] += count
            elif feedback == "archived":
                by_type[signal_type]["archived"] += count
            elif feedback == "completed":
                by_type[signal_type]["completed"] += count
        
        # Calculate acceptance rates
        acceptance_rates = {}
        for signal_type, counts in by_type.items():
            total = counts["approved"] + counts["rejected"]
            if total > 0:
                acceptance_rates[signal_type] = round(counts["approved"] / total * 100, 1)
            else:
                acceptance_rates[signal_type] = None  # No data
        
        # Extract rejection patterns
        rejection_patterns = self._analyze_rejection_patterns([
            {"signal_type": r.get("signal_type") or r.get(0), 
             "signal_text": r.get("signal_text") or r.get(1)}
            for r in rejected
        ])
        
        # Extract approval patterns (what makes a good signal)
        approval_patterns = self._analyze_approval_patterns([
            {"signal_type": a.get("signal_type") or a.get(0), 
             "signal_text": a.get("signal_text") or a.get(1)}
            for a in approved
        ])
        
        return {
            "by_type": by_type,
            "acceptance_rates": acceptance_rates,
            "rejection_patterns": rejection_patterns,
            "approval_patterns": approval_patterns,
            "total_feedback": sum(sum(c.values()) for c in by_type.values()),
        }
    
    def _analyze_rejection_patterns(self, rejected_signals: List[Dict]) -> List[str]:
        """Analyze rejected signals to identify patterns to avoid."""
        patterns = []
        
        if not rejected_signals:
            return patterns
        
        # Check for common characteristics in rejected signals
        short_signals = sum(1 for s in rejected_signals if len(s.get("signal_text", "")) < 20)
        vague_words = ["something", "stuff", "things", "etc", "various"]
        vague_signals = sum(1 for s in rejected_signals 
                          if any(w in (s.get("signal_text", "").lower()) for w in vague_words))
        
        total = len(rejected_signals)
        
        if short_signals > total * 0.3:
            patterns.append("Avoid extracting very short signals (less than 20 characters)")
        
        if vague_signals > total * 0.2:
            patterns.append("Avoid vague language like 'something', 'stuff', 'various', 'etc.'")
        
        # Identify frequently rejected signal types
        type_rejections = {}
        for s in rejected_signals:
            st = s.get("signal_type", "unknown")
            type_rejections[st] = type_rejections.get(st, 0) + 1
        
        for signal_type, count in type_rejections.items():
            if count > 5:
                patterns.append(f"Be more selective when extracting '{signal_type}' signals")
        
        return patterns
    
    def _analyze_approval_patterns(self, approved_signals: List[Dict]) -> List[str]:
        """Analyze approved signals to identify patterns to emulate."""
        patterns = []
        
        if not approved_signals:
            return patterns
        
        # Check for common characteristics in approved signals
        lengths = [len(s.get("signal_text", "")) for s in approved_signals]
        if lengths:
            avg_length = sum(lengths) / len(lengths)
            if avg_length > 50:
                patterns.append(f"User prefers detailed signals (average approved length: {int(avg_length)} chars)")
        
        # Check for specific/actionable language
        action_words = ["will", "should", "need to", "must", "by", "owner:"]
        actionable = sum(1 for s in approved_signals
                        if any(w in (s.get("signal_text", "").lower()) for w in action_words))
        
        if actionable > len(approved_signals) * 0.5:
            patterns.append("User values actionable signals with clear ownership or deadlines")
        
        # Identify highly approved signal types
        type_approvals = {}
        for s in approved_signals:
            st = s.get("signal_type", "unknown")
            type_approvals[st] = type_approvals.get(st, 0) + 1
        
        top_types = sorted(type_approvals.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_types:
            patterns.append(f"Most valued signal types: {', '.join(t[0] for t in top_types)}")
        
        return patterns
    
    def generate_learning_context(self) -> str:
        """
        Generate context text for injection into signal extraction prompts.
        
        This context helps the AI understand user preferences based on feedback.
        """
        summary = self.get_feedback_summary()
        
        if summary.get("total_feedback", 0) < 5:
            return ""  # Not enough feedback to generate meaningful context
        
        context_parts = []
        
        # Add acceptance rate context
        rates = summary.get("acceptance_rates", {})
        if rates:
            high_acceptance = [t for t, r in rates.items() if r and r > 70]
            low_acceptance = [t for t, r in rates.items() if r and r < 50]
            
            if high_acceptance:
                context_parts.append(
                    f"User highly values these signal types: {', '.join(high_acceptance)}"
                )
            if low_acceptance:
                context_parts.append(
                    f"Be selective when extracting: {', '.join(low_acceptance)} (often rejected)"
                )
        
        # Add pattern-based guidance
        for pattern in summary.get("rejection_patterns", [])[:3]:
            context_parts.append(f"- {pattern}")
        
        for pattern in summary.get("approval_patterns", [])[:3]:
            context_parts.append(f"+ {pattern}")
        
        if not context_parts:
            return ""
        
        return "\n".join([
            "## Signal Quality Guidelines (learned from user feedback)",
            "",
            *context_parts,
            ""
        ])
    
    def store_learning_in_memory(self) -> Optional[str]:
        """
        Store signal learning context in ai_memory for long-term retention.
        
        Returns:
            Memory ID if successfully stored, None otherwise
        """
        learning_context = self.generate_learning_context()
        
        if not learning_context:
            return None
        
        supabase = get_supabase()
        if not supabase:
            return self._store_learning_sqlite(learning_context)
        
        try:
            # Check if we already have a signal learning memory
            result = supabase.table("ai_memory").select("id").eq(
                "source_type", "signal_learning"
            ).limit(1).execute()
            
            if result.data:
                # Update existing
                memory_id = result.data[0]["id"]
                supabase.table("ai_memory").update({
                    "content": learning_context,
                    "updated_at": datetime.now().isoformat(),
                }).eq("id", memory_id).execute()
                logger.info(f"Updated signal learning memory: {memory_id}")
                return str(memory_id)
            else:
                # Create new
                insert_result = supabase.table("ai_memory").insert({
                    "source_type": "signal_learning",
                    "source_query": "Signal feedback patterns",
                    "content": learning_context,
                    "status": "approved",
                    "importance": 8,  # High importance for context retrieval
                    "tags": ["signal", "learning", "feedback"],
                }).execute()
                
                if insert_result.data:
                    memory_id = insert_result.data[0]["id"]
                    logger.info(f"Created signal learning memory: {memory_id}")
                    return str(memory_id)
        
        except Exception as e:
            logger.error(f"Failed to store signal learning: {e}")
        
        return None
    
    def _store_learning_sqlite(self, learning_context: str) -> Optional[str]:
        """Supabase storage for learning (renamed from SQLite for compatibility)."""
        try:
            supabase = get_supabase()
            if not supabase:
                logger.warning("Supabase not available for storing learning")
                return None
            
            # Check for existing
            existing_result = supabase.table("ai_memory").select("id").eq("source_type", "signal_learning").execute()
            
            if existing_result.data:
                existing_id = existing_result.data[0]["id"]
                supabase.table("ai_memory").update({
                    "content": learning_context,
                    "updated_at": "now()"
                }).eq("id", existing_id).execute()
                return str(existing_id)
            else:
                insert_result = supabase.table("ai_memory").insert({
                    "source_type": "signal_learning",
                    "source_query": "Signal feedback patterns",
                    "content": learning_context,
                    "status": "approved",
                    "importance": 8,
                    "tags": "signal,learning,feedback"
                }).execute()
                if insert_result.data:
                    return str(insert_result.data[0]["id"])
                return None
        
        except Exception as e:
            logger.error(f"Failed to store signal learning in Supabase: {e}")
            return None
    
    def get_signal_quality_hints(self, signal_type: str) -> Dict[str, Any]:
        """
        Get specific quality hints for a signal type based on feedback.
        
        Returns:
            Dict with acceptance_rate, example_good_signals, patterns_to_avoid
        """
        summary = self.get_feedback_summary()
        
        acceptance_rate = summary.get("acceptance_rates", {}).get(signal_type)
        
        # Find relevant patterns
        patterns_to_avoid = [
            p for p in summary.get("rejection_patterns", [])
            if signal_type.lower() in p.lower()
        ]
        
        patterns_to_follow = [
            p for p in summary.get("approval_patterns", [])
            if signal_type.lower() in p.lower()
        ]
        
        return {
            "signal_type": signal_type,
            "acceptance_rate": acceptance_rate,
            "patterns_to_avoid": patterns_to_avoid,
            "patterns_to_follow": patterns_to_follow,
            "has_feedback": acceptance_rate is not None,
        }


# =============================================================================
# API FUNCTIONS
# =============================================================================

def get_signal_learning_service(user_id: Optional[str] = None) -> SignalLearningService:
    """Get a SignalLearningService instance."""
    return SignalLearningService(user_id=user_id)


def get_learning_context_for_extraction() -> str:
    """
    Get learning context for signal extraction prompts.
    
    This is the main integration point for MeetingAnalyzerAgent.
    """
    service = get_signal_learning_service()
    return service.generate_learning_context()


def refresh_signal_learnings() -> bool:
    """
    Refresh signal learnings and store in ai_memory.
    
    Call this periodically (e.g., daily) or after significant feedback.
    """
    service = get_signal_learning_service()
    memory_id = service.store_learning_in_memory()
    return memory_id is not None
