# src/app/sdk/insights.py
"""
Insights Engine for SignalFlow SDK

Provides AI-powered analysis and insights generation for meeting and career data.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WeekSummary:
    """Summary of a week's activity."""
    start_date: str
    end_date: str
    meeting_count: int
    signal_counts: Dict[str, int]
    top_themes: List[str]
    open_actions: int
    completed_actions: int
    key_decisions: List[str]
    blockers: List[str]


@dataclass
class TrendAnalysis:
    """Trend analysis result."""
    metric: str
    period: str
    values: List[float]
    dates: List[str]
    trend_direction: str  # up, down, stable
    change_percent: float
    

class InsightsEngine:
    """
    AI-powered insights engine.
    
    Provides methods for generating summaries, trend analysis, and recommendations.
    
    Example:
        ```python
        insights = client.insights
        
        # Get weekly summary
        summary = insights.summarize_week()
        
        # Analyze trends
        trend = insights.trend_analysis("meeting_count", days=30)
        
        # Get recommendations
        recs = insights.recommendations()
        ```
    """
    
    def __init__(self, client):
        self._client = client
    
    def summarize_week(
        self,
        week_offset: int = 0,
        include_signals: bool = True,
    ) -> WeekSummary:
        """
        Generate a summary for a week.
        
        Args:
            week_offset: 0 = current week, -1 = last week, etc.
            include_signals: Include signal analysis
        
        Returns:
            WeekSummary with meeting and signal statistics
        """
        # Calculate date range
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday() + (week_offset * -7))
        end_of_week = start_of_week + timedelta(days=6)
        
        start_str = start_of_week.strftime("%Y-%m-%d")
        end_str = end_of_week.strftime("%Y-%m-%d")
        
        # Get meetings for the week
        meetings = self._client.meetings.list(
            date_from=start_str,
            date_to=end_str,
            limit=100,
        )
        
        # Get signals if requested
        signal_counts = {}
        key_decisions = []
        blockers = []
        open_actions = 0
        completed_actions = 0
        
        if include_signals:
            signals = self._client.signals.list(limit=500)
            
            for s in signals:
                # Only count signals from this week's meetings
                signal_counts[s.signal_type] = signal_counts.get(s.signal_type, 0) + 1
                
                if s.signal_type == "decision":
                    key_decisions.append(s.content[:100])
                elif s.signal_type == "blocker":
                    blockers.append(s.content[:100])
                elif s.signal_type == "action":
                    if s.status == "completed":
                        completed_actions += 1
                    else:
                        open_actions += 1
        
        # Extract themes from meeting names
        themes = self._extract_themes(meetings)
        
        return WeekSummary(
            start_date=start_str,
            end_date=end_str,
            meeting_count=len(meetings),
            signal_counts=signal_counts,
            top_themes=themes[:5],
            open_actions=open_actions,
            completed_actions=completed_actions,
            key_decisions=key_decisions[:5],
            blockers=blockers[:5],
        )
    
    def trend_analysis(
        self,
        metric: str,
        days: int = 30,
    ) -> TrendAnalysis:
        """
        Analyze trends for a metric over time.
        
        Args:
            metric: One of 'meeting_count', 'signal_count', 'action_completion'
            days: Number of days to analyze
        
        Returns:
            TrendAnalysis with values and direction
        """
        today = datetime.now()
        
        if metric == "meeting_count":
            # Daily meeting counts
            values = []
            dates = []
            
            for i in range(days):
                date = today - timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                dates.append(date_str)
                
                meetings = self._client.meetings.list(
                    date_from=date_str,
                    date_to=date_str,
                    limit=100,
                )
                values.append(len(meetings))
            
            values.reverse()
            dates.reverse()
            
        elif metric == "signal_count":
            # For simplicity, use weekly buckets
            values = []
            dates = []
            
            for i in range(min(days // 7, 4)):
                week_start = today - timedelta(days=7 * (i + 1))
                week_end = today - timedelta(days=7 * i)
                dates.append(week_start.strftime("%Y-%m-%d"))
                
                signals = self._client.signals.list(limit=500)
                values.append(len(signals))
            
            values.reverse()
            dates.reverse()
            
        else:
            values = []
            dates = []
        
        # Calculate trend
        if len(values) >= 2:
            first_half = sum(values[:len(values)//2]) / max(len(values)//2, 1)
            second_half = sum(values[len(values)//2:]) / max(len(values) - len(values)//2, 1)
            
            if second_half > first_half * 1.1:
                direction = "up"
                change = ((second_half - first_half) / first_half) * 100 if first_half else 0
            elif second_half < first_half * 0.9:
                direction = "down"
                change = ((first_half - second_half) / first_half) * 100 if first_half else 0
            else:
                direction = "stable"
                change = 0
        else:
            direction = "stable"
            change = 0
        
        return TrendAnalysis(
            metric=metric,
            period=f"{days} days",
            values=values,
            dates=dates,
            trend_direction=direction,
            change_percent=round(change, 1),
        )
    
    def recommendations(self) -> List[Dict[str, str]]:
        """
        Generate recommendations based on data analysis.
        
        Returns:
            List of recommendations with type, priority, and description
        """
        recs = []
        
        # Get current stats
        stats = self._client.meetings.get_statistics()
        
        # Check transcript coverage
        coverage = stats.get("transcript_coverage", 0)
        if coverage < 0.5:
            recs.append({
                "type": "data_quality",
                "priority": "high",
                "description": f"Only {coverage*100:.0f}% of meetings have transcripts. Consider enabling auto-transcription.",
            })
        
        # Check signal counts
        signal_counts = self._client.signals.get_by_type()
        total_signals = sum(signal_counts.values())
        
        if stats.get("total_meetings", 0) > 10 and total_signals < stats["total_meetings"]:
            recs.append({
                "type": "signal_extraction",
                "priority": "medium",
                "description": "Low signal count relative to meetings. Review signal extraction settings.",
            })
        
        # Check DIKW distribution
        dikw_counts = self._client.dikw.get_by_level()
        if dikw_counts.get("knowledge", 0) == 0 and dikw_counts.get("data", 0) > 10:
            recs.append({
                "type": "knowledge_synthesis",
                "priority": "medium",
                "description": "Data items exist but no knowledge synthesized. Run DIKW promotion.",
            })
        
        # Add general best practices
        if not recs:
            recs.append({
                "type": "general",
                "priority": "low",
                "description": "System health looks good. Continue regular usage patterns.",
            })
        
        return recs
    
    def generate_for_meetings(
        self,
        meeting_ids: List[str],
        insight_type: str = "summary",
    ) -> Dict[str, Any]:
        """
        Generate insights for specific meetings.
        
        Args:
            meeting_ids: List of meeting IDs to analyze
            insight_type: Type of insight ('summary', 'themes', 'actions')
        
        Returns:
            Generated insights
        """
        # This would typically call the AI service
        # For now, return aggregated data
        meetings = []
        for mid in meeting_ids:
            m = self._client.meetings.get(mid)
            if m:
                meetings.append(m)
        
        if insight_type == "summary":
            return {
                "type": "summary",
                "meeting_count": len(meetings),
                "meetings": [m.meeting_name for m in meetings],
                "total_signals": sum(m.signals_count for m in meetings),
            }
        elif insight_type == "themes":
            themes = self._extract_themes(meetings)
            return {
                "type": "themes",
                "themes": themes,
            }
        elif insight_type == "actions":
            # Would aggregate actions from signals
            return {
                "type": "actions",
                "open": 0,
                "completed": 0,
            }
        
        return {"type": insight_type, "data": None}
    
    def _extract_themes(self, meetings: List) -> List[str]:
        """Extract common themes from meeting names."""
        # Simple word frequency for now
        words = {}
        stop_words = {"the", "a", "an", "and", "or", "meeting", "call", "sync", "with"}
        
        for m in meetings:
            name_words = m.meeting_name.lower().split()
            for word in name_words:
                if word not in stop_words and len(word) > 2:
                    words[word] = words.get(word, 0) + 1
        
        # Sort by frequency
        sorted_words = sorted(words.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:10]]
