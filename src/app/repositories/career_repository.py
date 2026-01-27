# src/app/repositories/career_repository.py
"""
Career Repository - Ports and Adapters

Port: CareerRepository (abstract interface)
Adapters: SupabaseCareerRepository

Covers career-related tables:
- career_profile (11 calls)
- career_memories (25 calls)
- career_suggestions (8 calls)
- skill_tracker (26 calls)
- standup_updates (8 calls)
- code_locker (16 calls)
- career_tweaks, career_chat_updates, skill_import_tracking
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CareerProfile:
    """Career profile domain entity."""
    id: int = 1
    current_role: Optional[str] = None
    target_role: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    interests: Optional[str] = None
    goals: Optional[str] = None
    certifications: Optional[str] = None
    education: Optional[str] = None
    years_experience: Optional[int] = None
    preferred_work_style: Optional[str] = None
    industry_focus: Optional[str] = None
    leadership_experience: Optional[str] = None
    notable_projects: Optional[str] = None
    learning_priorities: Optional[str] = None
    career_timeline: Optional[str] = None
    technical_specializations: Optional[str] = None
    soft_skills: Optional[str] = None
    work_achievements: Optional[str] = None
    career_values: Optional[str] = None
    short_term_goals: Optional[str] = None
    long_term_goals: Optional[str] = None
    mentorship: Optional[str] = None
    networking: Optional[str] = None
    languages: Optional[str] = None
    last_insights: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CareerProfile":
        """Create from dictionary."""
        return cls(
            id=data.get("id", 1),
            current_role=data.get("current_role"),
            target_role=data.get("target_role"),
            strengths=data.get("strengths"),
            weaknesses=data.get("weaknesses"),
            interests=data.get("interests"),
            goals=data.get("goals"),
            certifications=data.get("certifications"),
            education=data.get("education"),
            years_experience=data.get("years_experience"),
            preferred_work_style=data.get("preferred_work_style"),
            industry_focus=data.get("industry_focus"),
            leadership_experience=data.get("leadership_experience"),
            notable_projects=data.get("notable_projects"),
            learning_priorities=data.get("learning_priorities"),
            career_timeline=data.get("career_timeline"),
            technical_specializations=data.get("technical_specializations"),
            soft_skills=data.get("soft_skills"),
            work_achievements=data.get("work_achievements"),
            career_values=data.get("career_values"),
            short_term_goals=data.get("short_term_goals"),
            long_term_goals=data.get("long_term_goals"),
            mentorship=data.get("mentorship"),
            networking=data.get("networking"),
            languages=data.get("languages"),
            last_insights=data.get("last_insights"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "current_role": self.current_role,
            "target_role": self.target_role,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "interests": self.interests,
            "goals": self.goals,
            "certifications": self.certifications,
            "education": self.education,
            "years_experience": self.years_experience,
            "preferred_work_style": self.preferred_work_style,
            "industry_focus": self.industry_focus,
            "leadership_experience": self.leadership_experience,
            "notable_projects": self.notable_projects,
            "learning_priorities": self.learning_priorities,
            "career_timeline": self.career_timeline,
            "technical_specializations": self.technical_specializations,
            "soft_skills": self.soft_skills,
            "work_achievements": self.work_achievements,
            "career_values": self.career_values,
            "short_term_goals": self.short_term_goals,
            "long_term_goals": self.long_term_goals,
            "mentorship": self.mentorship,
            "networking": self.networking,
            "languages": self.languages,
            "last_insights": self.last_insights,
        }


@dataclass
class CareerMemory:
    """Career memory domain entity."""
    id: Optional[int] = None
    memory_text: Optional[str] = None
    category: Optional[str] = None
    importance: Optional[int] = None
    created_at: Optional[str] = None
    embedding: Optional[List[float]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CareerMemory":
        return cls(
            id=data.get("id"),
            memory_text=data.get("memory_text"),
            category=data.get("category"),
            importance=data.get("importance", 50),
            created_at=data.get("created_at"),
            embedding=data.get("embedding"),
        )


@dataclass
class CareerSuggestion:
    """Career suggestion domain entity."""
    id: Optional[int] = None
    suggestion_type: Optional[str] = None
    content: Optional[str] = None
    status: str = "pending"
    priority: Optional[int] = None
    created_at: Optional[str] = None
    dismissed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CareerSuggestion":
        return cls(
            id=data.get("id"),
            suggestion_type=data.get("suggestion_type"),
            content=data.get("content"),
            status=data.get("status", "pending"),
            priority=data.get("priority"),
            created_at=data.get("created_at"),
            dismissed_at=data.get("dismissed_at"),
        )


@dataclass
class SkillEntry:
    """Skill tracker domain entity."""
    id: Optional[int] = None
    skill_name: Optional[str] = None
    category: Optional[str] = None
    proficiency: Optional[int] = None
    last_used: Optional[str] = None
    context: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillEntry":
        return cls(
            id=data.get("id"),
            skill_name=data.get("skill_name"),
            category=data.get("category"),
            proficiency=data.get("proficiency", 0),
            last_used=data.get("last_used"),
            context=data.get("context"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class StandupUpdate:
    """Standup update domain entity."""
    id: Optional[int] = None
    yesterday: Optional[str] = None
    today: Optional[str] = None
    blockers: Optional[str] = None
    mood: Optional[str] = None
    notes: Optional[str] = None
    ai_analysis: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandupUpdate":
        return cls(
            id=data.get("id"),
            yesterday=data.get("yesterday"),
            today=data.get("today"),
            blockers=data.get("blockers"),
            mood=data.get("mood"),
            notes=data.get("notes"),
            ai_analysis=data.get("ai_analysis"),
            created_at=data.get("created_at"),
        )


@dataclass
class CodeLockerEntry:
    """Code locker domain entity."""
    id: Optional[int] = None
    filename: Optional[str] = None
    content: Optional[str] = None
    ticket_id: Optional[int] = None
    version: int = 1
    description: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeLockerEntry":
        return cls(
            id=data.get("id"),
            filename=data.get("filename"),
            content=data.get("content"),
            ticket_id=data.get("ticket_id"),
            version=data.get("version", 1),
            description=data.get("description"),
            created_at=data.get("created_at"),
        )


# =============================================================================
# PORT (Abstract Interface)
# =============================================================================

class CareerRepository(ABC):
    """
    Career Repository Port - defines the interface for career data access.
    """

    # Profile operations
    @abstractmethod
    def get_profile(self) -> Optional[CareerProfile]:
        """Get the career profile."""
        pass

    @abstractmethod
    def update_profile(self, data: Dict[str, Any]) -> bool:
        """Update the career profile."""
        pass

    @abstractmethod
    def get_profile_insights(self) -> Optional[Dict[str, Any]]:
        """Get profile insights (last_insights, updated_at)."""
        pass

    # Memory operations
    @abstractmethod
    def get_memories(
        self,
        category: Optional[str] = None,
        limit: int = 50,
        order_desc: bool = True
    ) -> List[CareerMemory]:
        """Get career memories with optional filtering."""
        pass

    @abstractmethod
    def search_memories(
        self,
        query_embedding: List[float],
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[CareerMemory]:
        """Search memories by embedding similarity."""
        pass

    @abstractmethod
    def add_memory(self, data: Dict[str, Any]) -> Optional[CareerMemory]:
        """Add a career memory."""
        pass

    @abstractmethod
    def delete_memory(self, memory_id: int) -> bool:
        """Delete a career memory."""
        pass

    # Suggestion operations
    @abstractmethod
    def get_suggestions(
        self,
        statuses: Optional[List[str]] = None,
        suggestion_type: Optional[str] = None,
        limit: int = 50
    ) -> List[CareerSuggestion]:
        """Get career suggestions."""
        pass

    @abstractmethod
    def add_suggestion(self, data: Dict[str, Any]) -> Optional[CareerSuggestion]:
        """Add a career suggestion."""
        pass

    @abstractmethod
    def update_suggestion(self, suggestion_id: int, data: Dict[str, Any]) -> bool:
        """Update a suggestion status."""
        pass

    @abstractmethod
    def dismiss_suggestions(self, suggestion_ids: List[int]) -> int:
        """Dismiss multiple suggestions."""
        pass

    # Skill operations
    @abstractmethod
    def get_skills(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        order_by: str = "proficiency"
    ) -> List[SkillEntry]:
        """Get skills with optional filtering."""
        pass

    @abstractmethod
    def get_skill_by_name(self, skill_name: str) -> Optional[SkillEntry]:
        """Get a skill by name."""
        pass

    @abstractmethod
    def upsert_skill(self, data: Dict[str, Any]) -> Optional[SkillEntry]:
        """Create or update a skill."""
        pass

    @abstractmethod
    def delete_skill(self, skill_id: int) -> bool:
        """Delete a skill."""
        pass

    @abstractmethod
    def get_skill_categories(self) -> List[str]:
        """Get distinct skill categories."""
        pass

    # Standup operations
    @abstractmethod
    def get_standups(
        self,
        limit: int = 10,
        days_back: Optional[int] = None
    ) -> List[StandupUpdate]:
        """Get standup updates."""
        pass

    @abstractmethod
    def get_standup_by_date(self, date: str) -> Optional[StandupUpdate]:
        """Get standup for a specific date."""
        pass

    @abstractmethod
    def add_standup(self, data: Dict[str, Any]) -> Optional[StandupUpdate]:
        """Add a standup update."""
        pass

    @abstractmethod
    def delete_standup(self, standup_id: int) -> bool:
        """Delete a standup update."""
        pass

    # Code locker operations
    @abstractmethod
    def get_code_entries(
        self,
        ticket_id: Optional[int] = None,
        filename: Optional[str] = None,
        limit: int = 50
    ) -> List[CodeLockerEntry]:
        """Get code locker entries."""
        pass

    @abstractmethod
    def get_latest_code(self, ticket_id: int, filename: str) -> Optional[CodeLockerEntry]:
        """Get the latest code version for a file/ticket."""
        pass

    @abstractmethod
    def add_code_entry(self, data: Dict[str, Any]) -> Optional[CodeLockerEntry]:
        """Add a code locker entry."""
        pass

    @abstractmethod
    def get_next_version(self, ticket_id: int, filename: str) -> int:
        """Get the next version number for a file."""
        pass

    # Career tweaks operations
    @abstractmethod
    def get_tweaks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get career tweaks."""
        pass

    @abstractmethod
    def add_tweak(self, content: str) -> Optional[Dict[str, Any]]:
        """Add a career tweak."""
        pass

    @abstractmethod
    def delete_tweak(self, tweak_id: int) -> bool:
        """Delete a career tweak."""
        pass

    # Chat updates operations
    @abstractmethod
    def get_chat_updates(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get career chat updates."""
        pass

    @abstractmethod
    def add_chat_update(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a chat update."""
        pass

    @abstractmethod
    def get_latest_summary(self) -> Optional[str]:
        """Get the latest career summary."""
        pass


# =============================================================================
# SUPABASE ADAPTER
# =============================================================================

class SupabaseCareerRepository(CareerRepository):
    """Supabase adapter for career repository."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from ..infrastructure.supabase_client import get_supabase_client
            self._client = get_supabase_client()
        return self._client

    # -------------------------------------------------------------------------
    # Profile operations
    # -------------------------------------------------------------------------

    def get_profile(self) -> Optional[CareerProfile]:
        """Get the career profile."""
        if not self.client:
            logger.warning("Supabase not available")
            return None

        try:
            result = self.client.table("career_profile").select("*").eq("id", 1).execute()
            if result.data:
                return CareerProfile.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get career profile: {e}")
            return None

    def update_profile(self, data: Dict[str, Any]) -> bool:
        """Update the career profile."""
        if not self.client:
            return False

        try:
            data["id"] = 1  # Ensure we're updating the single profile
            self.client.table("career_profile").upsert(data, on_conflict="id").execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update career profile: {e}")
            return False

    def get_profile_insights(self) -> Optional[Dict[str, Any]]:
        """Get profile insights."""
        if not self.client:
            return None

        try:
            result = self.client.table("career_profile").select(
                "last_insights, updated_at"
            ).eq("id", 1).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get profile insights: {e}")
            return None

    # -------------------------------------------------------------------------
    # Memory operations
    # -------------------------------------------------------------------------

    def get_memories(
        self,
        category: Optional[str] = None,
        limit: int = 50,
        order_desc: bool = True
    ) -> List[CareerMemory]:
        """Get career memories."""
        if not self.client:
            return []

        try:
            query = self.client.table("career_memories").select("*")
            if category:
                query = query.eq("category", category)
            query = query.order("created_at", desc=order_desc).limit(limit)
            result = query.execute()
            return [CareerMemory.from_dict(m) for m in (result.data or [])]
        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return []

    def search_memories(
        self,
        query_embedding: List[float],
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[CareerMemory]:
        """Search memories by embedding similarity."""
        if not self.client:
            return []

        try:
            # Use Supabase RPC for vector similarity search
            result = self.client.rpc(
                "search_career_memories",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": limit,
                }
            ).execute()
            return [CareerMemory.from_dict(m) for m in (result.data or [])]
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []

    def add_memory(self, data: Dict[str, Any]) -> Optional[CareerMemory]:
        """Add a career memory."""
        if not self.client:
            return None

        try:
            result = self.client.table("career_memories").insert(data).execute()
            if result.data:
                return CareerMemory.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return None

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a career memory."""
        if not self.client:
            return False

        try:
            self.client.table("career_memories").delete().eq("id", memory_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    # -------------------------------------------------------------------------
    # Suggestion operations
    # -------------------------------------------------------------------------

    def get_suggestions(
        self,
        statuses: Optional[List[str]] = None,
        suggestion_type: Optional[str] = None,
        limit: int = 50
    ) -> List[CareerSuggestion]:
        """Get career suggestions."""
        if not self.client:
            return []

        try:
            query = self.client.table("career_suggestions").select("*")
            if statuses:
                query = query.in_("status", statuses)
            if suggestion_type:
                query = query.eq("suggestion_type", suggestion_type)
            query = query.order("created_at", desc=True).limit(limit)
            result = query.execute()
            return [CareerSuggestion.from_dict(s) for s in (result.data or [])]
        except Exception as e:
            logger.error(f"Failed to get suggestions: {e}")
            return []

    def add_suggestion(self, data: Dict[str, Any]) -> Optional[CareerSuggestion]:
        """Add a career suggestion."""
        if not self.client:
            return None

        try:
            result = self.client.table("career_suggestions").insert(data).execute()
            if result.data:
                return CareerSuggestion.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to add suggestion: {e}")
            return None

    def update_suggestion(self, suggestion_id: int, data: Dict[str, Any]) -> bool:
        """Update a suggestion."""
        if not self.client:
            return False

        try:
            self.client.table("career_suggestions").update(data).eq("id", suggestion_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update suggestion: {e}")
            return False

    def dismiss_suggestions(self, suggestion_ids: List[int]) -> int:
        """Dismiss multiple suggestions."""
        if not self.client or not suggestion_ids:
            return 0

        dismissed = 0
        try:
            for sid in suggestion_ids:
                self.client.table("career_suggestions").update(
                    {"status": "dismissed"}
                ).eq("id", sid).execute()
                dismissed += 1
            return dismissed
        except Exception as e:
            logger.error(f"Failed to dismiss suggestions: {e}")
            return dismissed

    # -------------------------------------------------------------------------
    # Skill operations
    # -------------------------------------------------------------------------

    def get_skills(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        order_by: str = "proficiency"
    ) -> List[SkillEntry]:
        """Get skills."""
        if not self.client:
            return []

        try:
            query = self.client.table("skill_tracker").select("*")
            if category:
                query = query.eq("category", category)
            query = query.order(order_by, desc=True).limit(limit)
            result = query.execute()
            return [SkillEntry.from_dict(s) for s in (result.data or [])]
        except Exception as e:
            logger.error(f"Failed to get skills: {e}")
            return []

    def get_skill_by_name(self, skill_name: str) -> Optional[SkillEntry]:
        """Get a skill by name."""
        if not self.client:
            return None

        try:
            result = self.client.table("skill_tracker").select("*").eq(
                "skill_name", skill_name
            ).execute()
            if result.data:
                return SkillEntry.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get skill: {e}")
            return None

    def upsert_skill(self, data: Dict[str, Any]) -> Optional[SkillEntry]:
        """Create or update a skill."""
        if not self.client:
            return None

        try:
            # Use skill_name as conflict key
            result = self.client.table("skill_tracker").upsert(
                data, on_conflict="skill_name"
            ).execute()
            if result.data:
                return SkillEntry.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to upsert skill: {e}")
            return None

    def delete_skill(self, skill_id: int) -> bool:
        """Delete a skill."""
        if not self.client:
            return False

        try:
            self.client.table("skill_tracker").delete().eq("id", skill_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete skill: {e}")
            return False

    def get_skill_categories(self) -> List[str]:
        """Get distinct skill categories."""
        if not self.client:
            return []

        try:
            result = self.client.table("skill_tracker").select("category").execute()
            categories = set(r.get("category") for r in (result.data or []) if r.get("category"))
            return sorted(categories)
        except Exception as e:
            logger.error(f"Failed to get skill categories: {e}")
            return []

    # -------------------------------------------------------------------------
    # Standup operations
    # -------------------------------------------------------------------------

    def get_standups(
        self,
        limit: int = 10,
        days_back: Optional[int] = None
    ) -> List[StandupUpdate]:
        """Get standup updates."""
        if not self.client:
            return []

        try:
            query = self.client.table("standup_updates").select("*")
            if days_back:
                cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
                query = query.gte("created_at", cutoff)
            # Try standup_date first, fall back to created_at
            try:
                query = query.order("standup_date", desc=True).limit(limit)
                result = query.execute()
            except Exception:
                query = self.client.table("standup_updates").select("*")
                if days_back:
                    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
                    query = query.gte("created_at", cutoff)
                query = query.order("created_at", desc=True).limit(limit)
                result = query.execute()
            return [StandupUpdate.from_dict(s) for s in (result.data or [])]
        except Exception as e:
            logger.error(f"Failed to get standups: {e}")
            return []

    def get_standup_by_date(self, date: str) -> Optional[StandupUpdate]:
        """Get standup for a specific date."""
        if not self.client:
            return None

        try:
            # Try standup_date column first
            try:
                result = self.client.table("standup_updates").select("*").eq(
                    "standup_date", date
                ).execute()
                if result.data:
                    return StandupUpdate.from_dict(result.data[0])
            except Exception:
                pass
            
            # Fall back to checking created_at date portion
            result = self.client.table("standup_updates").select("*").gte(
                "created_at", f"{date}T00:00:00"
            ).lt("created_at", f"{date}T23:59:59").limit(1).execute()
            if result.data:
                return StandupUpdate.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get standup by date: {e}")
            return None

    def add_standup(self, data: Dict[str, Any]) -> Optional[StandupUpdate]:
        """Add a standup update."""
        if not self.client:
            return None

        try:
            result = self.client.table("standup_updates").insert(data).execute()
            if result.data:
                return StandupUpdate.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to add standup: {e}")
            return None

    def delete_standup(self, standup_id: int) -> bool:
        """Delete a standup update."""
        if not self.client:
            return False

        try:
            self.client.table("standup_updates").delete().eq("id", standup_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete standup: {e}")
            return False

    # -------------------------------------------------------------------------
    # Code locker operations
    # -------------------------------------------------------------------------

    def get_code_entries(
        self,
        ticket_id: Optional[int] = None,
        filename: Optional[str] = None,
        limit: int = 50
    ) -> List[CodeLockerEntry]:
        """Get code locker entries."""
        if not self.client:
            return []

        try:
            query = self.client.table("code_locker").select("*")
            if ticket_id:
                query = query.eq("ticket_id", ticket_id)
            if filename:
                query = query.eq("filename", filename)
            query = query.order("created_at", desc=True).limit(limit)
            result = query.execute()
            return [CodeLockerEntry.from_dict(c) for c in (result.data or [])]
        except Exception as e:
            logger.error(f"Failed to get code entries: {e}")
            return []

    def get_latest_code(self, ticket_id: int, filename: str) -> Optional[CodeLockerEntry]:
        """Get the latest code version for a file/ticket."""
        if not self.client:
            return None

        try:
            result = self.client.table("code_locker").select("*").eq(
                "filename", filename
            ).eq("ticket_id", ticket_id).order("version", desc=True).limit(1).execute()
            if result.data:
                return CodeLockerEntry.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get latest code: {e}")
            return None

    def add_code_entry(self, data: Dict[str, Any]) -> Optional[CodeLockerEntry]:
        """Add a code locker entry."""
        if not self.client:
            return None

        try:
            result = self.client.table("code_locker").insert(data).execute()
            if result.data:
                return CodeLockerEntry.from_dict(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to add code entry: {e}")
            return None

    def get_next_version(self, ticket_id: int, filename: str) -> int:
        """Get the next version number for a file."""
        if not self.client:
            return 1

        try:
            result = self.client.table("code_locker").select("version").eq(
                "ticket_id", ticket_id
            ).eq("filename", filename).order("version", desc=True).limit(1).execute()
            if result.data:
                return result.data[0].get("version", 0) + 1
            return 1
        except Exception as e:
            logger.error(f"Failed to get next version: {e}")
            return 1

    # -------------------------------------------------------------------------
    # Career tweaks operations
    # -------------------------------------------------------------------------

    def get_tweaks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get career tweaks."""
        if not self.client:
            return []

        try:
            result = self.client.table("career_tweaks").select("*").order(
                "created_at", desc=True
            ).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get tweaks: {e}")
            return []

    def add_tweak(self, content: str) -> Optional[Dict[str, Any]]:
        """Add a career tweak."""
        if not self.client:
            return None

        try:
            result = self.client.table("career_tweaks").insert(
                {"content": content}
            ).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to add tweak: {e}")
            return None

    def delete_tweak(self, tweak_id: int) -> bool:
        """Delete a career tweak."""
        if not self.client:
            return False

        try:
            self.client.table("career_tweaks").delete().eq("id", tweak_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete tweak: {e}")
            return False

    # -------------------------------------------------------------------------
    # Chat updates operations
    # -------------------------------------------------------------------------

    def get_chat_updates(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get career chat updates."""
        if not self.client:
            return []

        try:
            result = self.client.table("career_chat_updates").select("*").order(
                "created_at", desc=True
            ).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get chat updates: {e}")
            return []

    def add_chat_update(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a chat update."""
        if not self.client:
            return None

        try:
            result = self.client.table("career_chat_updates").insert(data).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to add chat update: {e}")
            return None

    def get_latest_summary(self) -> Optional[str]:
        """Get the latest career summary from chat updates."""
        if not self.client:
            return None

        try:
            result = self.client.table("career_chat_updates").select("summary").neq(
                "summary", ""
            ).not_.is_("summary", "null").order("created_at", desc=True).limit(1).execute()
            if result.data:
                return result.data[0].get("summary")
            return None
        except Exception as e:
            logger.error(f"Failed to get latest summary: {e}")
            return None


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_career_repository() -> CareerRepository:
    """Get the career repository (Supabase adapter)."""
    return SupabaseCareerRepository()
