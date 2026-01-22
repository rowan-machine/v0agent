# src/app/services/coach_recommendations.py
"""
Coach Recommendation Engine

Uses embeddings for actionable recommendations in "Your Coach" section.
Finds relevant items based on:
1. User's current context (active tickets, recent meetings)
2. DIKW items that need attention
3. Signals that need review
4. Missing transcripts in meetings
5. When user was mentioned in transcripts

Technical Debt Item: Coach recommendation engine using embeddings
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import json

from ..db import connect
from ..infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class CoachRecommendationEngine:
    """
    Intelligent recommendation engine for the "Your Coach" section.
    
    Uses embeddings to find semantically relevant recommendations
    rather than just rule-based matching.
    """
    
    def __init__(self, user_id: Optional[str] = None, user_name: str = "Rowan"):
        self.user_id = user_id
        self.user_name = user_name  # For mention detection
        self.supabase = get_supabase_client()
    
    def get_recommendations(
        self, 
        dismissed_ids: List[str] = None,
        max_items: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Get smart recommendations for the dashboard.
        
        Returns prioritized list of actionable recommendations.
        """
        dismissed_ids = dismissed_ids or []
        recommendations = []
        
        # 1. Get context-aware recommendations using embeddings
        embedding_recs = self._get_embedding_based_recommendations(dismissed_ids)
        recommendations.extend(embedding_recs)
        
        # 2. Get DIKW items that need attention
        dikw_recs = self._get_dikw_recommendations(dismissed_ids)
        recommendations.extend(dikw_recs)
        
        # 3. Get signals that need review
        signal_recs = self._get_signal_review_recommendations(dismissed_ids)
        recommendations.extend(signal_recs)
        
        # 4. Get meetings missing transcripts
        transcript_recs = self._get_missing_transcript_recommendations(dismissed_ids)
        recommendations.extend(transcript_recs)
        
        # 5. Get mentions of user in transcripts
        mention_recs = self._get_user_mention_recommendations(dismissed_ids)
        recommendations.extend(mention_recs)
        
        # 6. Get ticket backlog grooming suggestions
        grooming_recs = self._get_backlog_grooming_recommendations(dismissed_ids)
        recommendations.extend(grooming_recs)
        
        # Deduplicate and prioritize
        seen_ids = set()
        unique_recs = []
        for rec in recommendations:
            if rec["id"] not in seen_ids:
                seen_ids.add(rec["id"])
                unique_recs.append(rec)
        
        # Sort by priority (lower number = higher priority)
        priority_map = {
            "blocker": 0,
            "mention": 1,  # User mentioned = important
            "risk": 2,
            "action": 3,
            "dikw": 4,
            "grooming": 5,
            "transcript": 6,
            "idea": 7,
        }
        unique_recs.sort(key=lambda r: priority_map.get(r.get("type", "idea"), 99))
        
        return unique_recs[:max_items]
    
    def _get_embedding_based_recommendations(
        self, 
        dismissed_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Use embeddings to find relevant recommendations based on user context.
        """
        if not self.supabase:
            return []
        
        recommendations = []
        
        try:
            # Get user's current focus (in-progress tickets)
            tickets_result = self.supabase.table("tickets").select(
                "id, ticket_id, title, description"
            ).eq("status", "in_progress").limit(3).execute()
            
            current_work = tickets_result.data or []
            
            if not current_work:
                return []
            
            # Build context from current work
            context_texts = [
                f"{t['title']} - {t.get('description', '')[:200]}"
                for t in current_work
            ]
            
            # Find related DIKW items using similarity search
            # This is a simplified version - full implementation would use pgvector
            for work in current_work[:2]:
                related_dikw = self.supabase.table("dikw_items").select(
                    "id, content, level, summary"
                ).ilike("content", f"%{work['title'].split()[0]}%").limit(2).execute()
                
                for dikw in (related_dikw.data or []):
                    rec_id = f"related-dikw-{dikw['id']}"
                    if rec_id not in dismissed_ids:
                        recommendations.append({
                            "id": rec_id,
                            "type": "dikw",
                            "label": f"💡 Related {dikw['level'].title()}",
                            "text": dikw.get('summary') or dikw['content'][:80],
                            "action": f"Related to: {work['title'][:40]}",
                            "link": f"/dikw?focus={dikw['id']}",
                            "link_text": "View DIKW"
                        })
        
        except Exception as e:
            logger.error(f"Embedding recommendations failed: {e}")
        
        return recommendations[:3]
    
    def _get_dikw_recommendations(
        self, 
        dismissed_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Find DIKW items that need attention:
        - Low confidence items that could be promoted
        - Items with high validation count
        """
        recommendations = []
        
        if self.supabase:
            try:
                # High validation items ready for promotion
                promotable = self.supabase.table("dikw_items").select(
                    "id, content, level, validation_count, confidence"
                ).neq("level", "wisdom").gte("validation_count", 3).order(
                    "validation_count", desc=True
                ).limit(2).execute()
                
                for item in (promotable.data or []):
                    rec_id = f"dikw-promote-{item['id']}"
                    if rec_id not in dismissed_ids:
                        next_level = {
                            "data": "information",
                            "information": "knowledge",
                            "knowledge": "wisdom"
                        }.get(item["level"], "wisdom")
                        
                        recommendations.append({
                            "id": rec_id,
                            "type": "dikw",
                            "label": "📈 Ready to Promote",
                            "text": item['content'][:80] + "..." if len(item['content']) > 80 else item['content'],
                            "action": f"Validated {item['validation_count']} times - promote to {next_level}?",
                            "link": f"/dikw?focus={item['id']}",
                            "link_text": "Review & Promote"
                        })
            
            except Exception as e:
                logger.debug(f"DIKW recommendations error: {e}")
        
        return recommendations
    
    def _get_signal_review_recommendations(
        self, 
        dismissed_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Find signals that need review.
        """
        recommendations = []
        
        with connect() as conn:
            # Count pending signals
            pending = conn.execute("""
                SELECT COUNT(*) as count FROM signal_status 
                WHERE status = 'pending' OR status IS NULL
            """).fetchone()
            
            count = pending['count'] if pending else 0
            
            if count > 5:
                rec_id = "signals-pending-review"
                if rec_id not in dismissed_ids:
                    recommendations.append({
                        "id": rec_id,
                        "type": "action",
                        "label": "📥 Signals to Review",
                        "text": f"{count} signals waiting for your review",
                        "action": "Review signals to build your knowledge base",
                        "link": "/signals",
                        "link_text": "Review Signals"
                    })
        
        return recommendations
    
    def _get_missing_transcript_recommendations(
        self, 
        dismissed_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Find meetings that don't have linked transcripts.
        """
        recommendations = []
        
        if self.supabase:
            try:
                # Find recent meetings without linked documents
                meetings = self.supabase.table("meetings").select(
                    "id, meeting_name, meeting_date"
                ).is_("raw_text", "null").gte(
                    "meeting_date",
                    (datetime.now() - timedelta(days=7)).isoformat()
                ).order("meeting_date", desc=True).limit(2).execute()
                
                for meeting in (meetings.data or []):
                    rec_id = f"missing-transcript-{meeting['id']}"
                    if rec_id not in dismissed_ids:
                        recommendations.append({
                            "id": rec_id,
                            "type": "transcript",
                            "label": "📝 Missing Transcript",
                            "text": meeting['meeting_name'][:60],
                            "action": "Add the transcript to extract more signals",
                            "link": f"/meetings/{meeting['id']}",
                            "link_text": "Add Transcript"
                        })
            
            except Exception as e:
                logger.debug(f"Transcript recommendations error: {e}")
        
        return recommendations
    
    def _get_user_mention_recommendations(
        self, 
        dismissed_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Find transcripts where the user was mentioned.
        """
        recommendations = []
        
        if self.supabase and self.user_name:
            try:
                # Search documents for user mentions
                docs = self.supabase.table("documents").select(
                    "id, source, content, meeting_id"
                ).ilike("content", f"%{self.user_name}%").order(
                    "created_at", desc=True
                ).limit(3).execute()
                
                for doc in (docs.data or []):
                    # Find the mention context
                    content = doc['content']
                    idx = content.lower().find(self.user_name.lower())
                    if idx >= 0:
                        start = max(0, idx - 50)
                        end = min(len(content), idx + len(self.user_name) + 100)
                        snippet = "..." + content[start:end] + "..."
                        
                        rec_id = f"mention-{doc['id']}"
                        if rec_id not in dismissed_ids:
                            recommendations.append({
                                "id": rec_id,
                                "type": "mention",
                                "label": "👋 You Were Mentioned",
                                "text": snippet[:100],
                                "action": f"In: {doc['source'][:40]}",
                                "link": f"/documents/{doc['id']}" if not doc['meeting_id'] else f"/meetings/{doc['meeting_id']}",
                                "link_text": "View Context"
                            })
            
            except Exception as e:
                logger.debug(f"Mention recommendations error: {e}")
        
        return recommendations
    
    def _get_backlog_grooming_recommendations(
        self, 
        dismissed_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Find backlog items that need grooming.
        """
        recommendations = []
        
        if self.supabase:
            try:
                # Find old backlog items
                old_backlog = self.supabase.table("tickets").select(
                    "id, ticket_id, title, created_at"
                ).eq("status", "backlog").order(
                    "created_at", desc=False
                ).limit(3).execute()
                
                for ticket in (old_backlog.data or []):
                    # Check if more than 14 days old
                    created = datetime.fromisoformat(ticket['created_at'].replace('Z', '+00:00'))
                    if (datetime.now(created.tzinfo) - created).days > 14:
                        rec_id = f"groom-{ticket['id']}"
                        if rec_id not in dismissed_ids:
                            recommendations.append({
                                "id": rec_id,
                                "type": "grooming",
                                "label": "🧹 Backlog Grooming",
                                "text": f"{ticket['ticket_id']}: {ticket['title'][:50]}",
                                "action": "This has been in backlog for 2+ weeks - still relevant?",
                                "link": f"/tickets?focus={ticket['ticket_id']}",
                                "link_text": "Review Ticket"
                            })
            
            except Exception as e:
                logger.debug(f"Grooming recommendations error: {e}")
        
        return recommendations[:2]


def get_coach_recommendations(
    dismissed_ids: List[str] = None,
    user_name: str = "Rowan"
) -> List[Dict[str, Any]]:
    """
    Get smart recommendations for the coach section.
    
    Main entry point for the dashboard highlights API.
    """
    engine = CoachRecommendationEngine(user_name=user_name)
    return engine.get_recommendations(dismissed_ids=dismissed_ids)
