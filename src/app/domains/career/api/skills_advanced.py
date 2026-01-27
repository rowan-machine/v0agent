# src/app/domains/career/api/skills_advanced.py
"""
Advanced Skills API Routes

AI-powered endpoints for skill extraction and assessment.
These routes use LLM analysis and codebase scanning.
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Default skill categories for initialization
SKILL_CATEGORIES = {
    "python": ["Python", "typing", "Hexagonal Architecture"],
    "backend": ["REST APIs", "FastAPI", "Backend Development", "Microservices"],
    "data": ["ETL", "Data Pipelines", "Data Quality", "Data Lineage"],
    "analytics": ["Data Analysis", "SQL/Databases", "Data Visualization"],
    "aws": ["AWS", "Cloud Platforms", "Lambda", "S3"],
    "Agentic AI": [
        "LLM Integration", "RAG", "Embeddings", "Prompt Engineering",
        "MCP Servers", "Tool Calling", "Agent Orchestration",
        "ReAct Patterns", "Function Calling", "Multi-Agent Systems"
    ],
    "ddd": ["Domain Driven Design", "Bounded Contexts", "Aggregates", "Event Sourcing"],
    "knowledge": ["Knowledge Graphs", "DIKW", "Semantic"],
}


@router.post("/skills/initialize")
async def initialize_skills(request: Request):
    """Initialize skill tracker with pre-defined categories or custom skills."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    try:
        body = await request.json()
        skills_with_categories = body.get("skills_with_categories", [])
        custom_skills = body.get("skills", [])  # Legacy format
    except Exception:
        skills_with_categories = []
        custom_skills = []
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    added = 0
    
    if skills_with_categories:
        # New format: skills with their categories
        for item in skills_with_categories:
            skill_name = item.get("name") if isinstance(item, dict) else item
            category = item.get("category", "Custom") if isinstance(item, dict) else "Custom"
            try:
                existing = supabase.table("skill_tracker").select("id").eq(
                    "skill_name", skill_name
                ).execute()
                if not existing.data:
                    supabase.table("skill_tracker").insert({
                        "skill_name": skill_name,
                        "category": category,
                        "proficiency_level": 0
                    }).execute()
                    added += 1
            except Exception:
                pass
    elif custom_skills:
        # Legacy format: just skill names
        for skill in custom_skills:
            try:
                existing = supabase.table("skill_tracker").select("id").eq(
                    "skill_name", skill
                ).execute()
                if not existing.data:
                    supabase.table("skill_tracker").insert({
                        "skill_name": skill,
                        "category": "Custom",
                        "proficiency_level": 0
                    }).execute()
                    added += 1
            except Exception:
                pass
    else:
        # Add default skill categories
        for category, skills in SKILL_CATEGORIES.items():
            for skill in skills:
                try:
                    existing = supabase.table("skill_tracker").select("id").eq(
                        "skill_name", skill
                    ).execute()
                    if not existing.data:
                        supabase.table("skill_tracker").insert({
                            "skill_name": skill,
                            "category": category,
                            "proficiency_level": 0
                        }).execute()
                        added += 1
                except Exception:
                    pass
    
    return JSONResponse({"status": "ok", "initialized": added})


@router.post("/skills/reset")
async def reset_skills():
    """Reset all skill data (delete all skills)."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    supabase.table("skill_tracker").delete().gte("id", 0).execute()
    return JSONResponse({"status": "ok", "message": "All skills reset"})


@router.post("/skills/remove-by-categories")
async def remove_skills_by_categories(request: Request):
    """Remove skills belonging to specified categories."""
    from ....infrastructure.supabase_client import get_supabase_client
    
    data = await request.json()
    categories_to_remove = data.get("categories", [])
    
    if not categories_to_remove:
        return JSONResponse({"status": "ok", "removed": 0})
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    removed = 0
    for category in categories_to_remove:
        result = supabase.table("skill_tracker").delete().eq("category", category).execute()
        removed += len(result.data) if result.data else 0
    
    return JSONResponse({
        "status": "ok",
        "removed": removed,
        "categories": categories_to_remove
    })


@router.post("/skills/from-resume")
async def extract_skills_from_resume(request: Request):
    """Extract skills from uploaded resume text using AI."""
    from ....infrastructure.supabase_client import get_supabase_client
    import re
    
    data = await request.json()
    resume_text = data.get("resume_text", "")
    update_profile = data.get("update_profile", False)
    
    if not resume_text.strip():
        return JSONResponse({"error": "No resume text provided"}, status_code=400)
    
    prompt = f"""Analyze this resume and extract technical skills with estimated proficiency levels.

Resume:
{resume_text[:8000]}

Return a JSON object with this structure:
{{
    "skills": [
        {{"name": "Skill Name", "category": "category_name", "proficiency": 50, "evidence": "Brief reason from resume"}}
    ]
}}

Categories should be one of: python, backend, data, analytics, aws, Agentic AI, ddd, knowledge, Custom
Proficiency should be 1-100 based on the level of experience shown.

Return ONLY the JSON object, no other text."""

    profile_updated = False
    try:
        from ....llm import ask as ask_llm
        response = ask_llm(prompt, model="gpt-4o-mini")
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            skills_data = json.loads(json_match.group())
            
            skills_added = 0
            supabase = get_supabase_client()
            if supabase:
                for skill in skills_data.get("skills", []):
                    skill_name = skill.get("name")
                    category = skill.get("category", "Custom")
                    proficiency = skill.get("proficiency", 30)
                    evidence = json.dumps([skill.get("evidence", "Extracted from resume")])
                    
                    existing = supabase.table("skill_tracker").select("id,proficiency_level").eq(
                        "skill_name", skill_name
                    ).execute()
                    
                    if existing.data:
                        current_prof = existing.data[0].get("proficiency_level", 0)
                        if proficiency > current_prof:
                            supabase.table("skill_tracker").update({
                                "proficiency_level": proficiency,
                                "evidence": evidence
                            }).eq("skill_name", skill_name).execute()
                    else:
                        supabase.table("skill_tracker").insert({
                            "skill_name": skill_name,
                            "category": category,
                            "proficiency_level": proficiency,
                            "evidence": evidence
                        }).execute()
                    skills_added += 1
            
            # Optionally update profile from resume
            if update_profile:
                profile_updated = await _update_profile_from_resume(resume_text, supabase)
            
            return JSONResponse({
                "status": "ok",
                "skills_added": skills_added,
                "skills": skills_data.get("skills", []),
                "profile_updated": profile_updated
            })
        else:
            return JSONResponse({"error": "Could not parse AI response"}, status_code=500)
    except Exception as e:
        logger.exception("Error extracting skills from resume")
        return JSONResponse({"error": str(e)}, status_code=500)


async def _update_profile_from_resume(resume_text: str, supabase) -> bool:
    """Helper to extract and update profile from resume."""
    import re
    
    profile_prompt = f"""Analyze this resume and extract profile information.

Resume:
{resume_text[:8000]}

Return a JSON object with these fields (include only what you can find):
{{
    "current_role": "current or most recent job title",
    "target_role": "next career goal if mentioned",
    "years_experience": number or null,
    "education": "degrees, schools",
    "certifications": "certifications mentioned",
    "technical_specializations": "main technical focus areas",
    "strengths": "key strengths shown",
    "short_term_goals": "any short-term goals mentioned",
    "long_term_goals": "any long-term career aspirations",
    "soft_skills": "leadership, communication skills etc",
    "languages": "programming or spoken languages",
    "work_achievements": "notable achievements"
}}

Return ONLY valid JSON, no other text. Use null for fields you can't determine."""

    try:
        from ....llm import ask as ask_llm
        profile_response = ask_llm(profile_prompt, model="gpt-4o-mini")
        profile_match = re.search(r'\{[\s\S]*\}', profile_response)
        
        if profile_match and supabase:
            profile_data = json.loads(profile_match.group())
            
            update_data = {}
            for field in ['current_role', 'target_role', 'years_experience', 'education',
                         'certifications', 'technical_specializations', 'strengths',
                         'short_term_goals', 'long_term_goals', 'soft_skills',
                         'languages', 'work_achievements']:
                if field in profile_data and profile_data[field]:
                    val = profile_data[field]
                    if isinstance(val, list):
                        val = ', '.join(str(item) for item in val)
                    update_data[field] = str(val)
            
            if update_data:
                existing = supabase.table("career_profile").select("id").limit(1).execute()
                if existing.data:
                    supabase.table("career_profile").update(update_data).eq(
                        "id", existing.data[0].get("id")
                    ).execute()
                else:
                    supabase.table("career_profile").insert(update_data).execute()
                return True
    except Exception as e:
        logger.error(f"Profile update error: {e}")
    
    return False


@router.post("/skills/assess-from-codebase")
async def assess_skills_from_codebase(request: Request):
    """Analyze codebase and update skill levels based on code evidence."""
    from ....infrastructure.supabase_client import get_supabase_client
    import os
    import glob
    import random
    
    # Skill patterns to scan for
    skill_patterns = {
        # Domain Driven Design
        "Domain Driven Design": ["domain", "aggregate", "bounded_context", "ubiquitous"],
        "Bounded Contexts": ["bounded_context", "context_map", "anti_corruption"],
        "Aggregates": ["aggregate", "aggregate_root", "entity"],
        "Event Sourcing": ["event_source", "event_store", "cqrs", "event_driven"],
        # Python
        "Python": ["def ", "class ", "import ", "async def", "__init__"],
        "typing": ["typing", "Optional", "List[", "Dict[", "Union[", "Callable"],
        "Hexagonal Architecture": ["hexagonal", "adapter", "port", "driven_adapter"],
        # Analytics
        "Data Analysis": ["pandas", "numpy", "analysis", "dataframe"],
        "SQL/Databases": ["sqlite", "postgresql", "execute(", "SELECT", "INSERT"],
        "Data Visualization": ["matplotlib", "plotly", "chart", "visualization"],
        # Backend
        "REST APIs": ["@app.get", "@app.post", "@router", "endpoint", "api/"],
        "FastAPI": ["fastapi", "FastAPI", "APIRouter", "Depends"],
        "Backend Development": ["middleware", "authentication", "authorization"],
        "Microservices": ["microservice", "service_mesh", "container"],
        # AI/ML - Agentic AI
        "LLM Integration": ["openai", "anthropic", "llm", "chat_completion", "gpt"],
        "RAG": ["rag", "retrieval", "embedding", "vector_store", "chromadb"],
        "Embeddings": ["embedding", "embed_text", "vector", "cosine_similarity"],
        "Prompt Engineering": ["prompt", "system_message", "user_message", "few_shot"],
        "MCP Servers": ["mcp", "model_context_protocol", "mcp_server", "@mcp", "McpServer"],
        "Tool Calling": ["tool_call", "function_call", "@tool", "tools=", "tool_registry"],
        "Agent Orchestration": ["agent", "orchestrat", "workflow", "chain_of_thought"],
        "ReAct Patterns": ["react", "reason", "act", "observation", "thought"],
        "Function Calling": ["function_call", "functions=", "@function", "call_function"],
        "Multi-Agent Systems": ["multi_agent", "agent_team", "collaboration", "delegate"],
        # Data Engineering
        "ETL": ["etl", "extract", "transform", "load", "pipeline"],
        "Data Pipelines": ["pipeline", "dag", "workflow", "orchestration"],
        "Data Quality": ["data_quality", "validation", "schema", "constraint"],
        "Data Lineage": ["lineage", "provenance", "tracking", "metadata"],
        # Cloud/AWS
        "AWS": ["boto3", "aws", "s3_client", "lambda_handler"],
        "Cloud Platforms": ["cloud", "gcp", "azure", "terraform"],
        "Lambda": ["lambda_handler", "serverless", "aws_lambda", "lambda_function"],
        "S3": ["s3", "bucket", "s3_client", "upload_file"],
        # Knowledge
        "Knowledge Graphs": ["knowledge_graph", "neo4j", "graph_db", "triplet"],
        "DIKW": ["dikw", "data_information", "knowledge_wisdom"],
        "Semantic": ["semantic", "ontology", "rdf", "sparql"],
    }
    
    skill_categories = {
        "Domain Driven Design": "ddd", "Bounded Contexts": "ddd", "Aggregates": "ddd", "Event Sourcing": "ddd",
        "Python": "python", "typing": "python", "Hexagonal Architecture": "python",
        "Data Analysis": "analytics", "SQL/Databases": "analytics", "Data Visualization": "analytics",
        "REST APIs": "backend", "FastAPI": "backend", "Backend Development": "backend", "Microservices": "backend",
        "LLM Integration": "Agentic AI", "RAG": "Agentic AI", "Embeddings": "Agentic AI", "Prompt Engineering": "Agentic AI",
        "MCP Servers": "Agentic AI", "Tool Calling": "Agentic AI", "Agent Orchestration": "Agentic AI",
        "ReAct Patterns": "Agentic AI", "Function Calling": "Agentic AI", "Multi-Agent Systems": "Agentic AI",
        "ETL": "data", "Data Pipelines": "data", "Data Quality": "data", "Data Lineage": "data",
        "AWS": "aws", "Cloud Platforms": "aws", "Lambda": "aws", "S3": "aws",
        "Knowledge Graphs": "knowledge", "DIKW": "knowledge", "Semantic": "knowledge",
    }
    
    # Scan codebase
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    ))))
    py_files = glob.glob(os.path.join(workspace_root, "**/*.py"), recursive=True)
    py_files = [f for f in py_files if not any(
        x in f for x in ['__pycache__', '.venv', 'venv', 'node_modules', '.git']
    )]
    
    # Track evidence per skill
    skill_evidence = {skill: {"files": [], "count": 0, "patterns_found": []} for skill in skill_patterns}
    
    for filepath in py_files[:150]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                content_lower = content.lower()
                
            for skill, patterns in skill_patterns.items():
                for pattern in patterns:
                    pattern_lower = pattern.lower()
                    if pattern_lower in content_lower:
                        rel_path = os.path.relpath(filepath, workspace_root)
                        if rel_path not in skill_evidence[skill]["files"]:
                            skill_evidence[skill]["files"].append(rel_path)
                        skill_evidence[skill]["count"] += content_lower.count(pattern_lower)
                        if pattern not in skill_evidence[skill]["patterns_found"]:
                            skill_evidence[skill]["patterns_found"].append(pattern)
        except Exception:
            pass
    
    # Update skill levels
    skills_updated = 0
    supabase = get_supabase_client()
    if supabase:
        for skill, evidence in skill_evidence.items():
            file_count = len(evidence["files"])
            pattern_count = len(evidence["patterns_found"])
            total_count = evidence["count"]
            
            if file_count > 0 or total_count > 0:
                base_score = min(25, pattern_count * 8)
                file_bonus = min(20, file_count * 3)
                usage_bonus = min(25, total_count // 10)
                variance = random.randint(-5, 5)
                
                proficiency = max(5, min(70, base_score + file_bonus + usage_bonus + variance))
                category = skill_categories.get(skill, "Custom")
                evidence_json = json.dumps(evidence["files"][:10])
                
                existing = supabase.table("skill_tracker").select("id,proficiency_level").eq(
                    "skill_name", skill
                ).execute()
                
                if existing.data:
                    current_prof = existing.data[0].get("proficiency_level", 0)
                    if proficiency > current_prof:
                        supabase.table("skill_tracker").update({
                            "proficiency_level": proficiency,
                            "evidence": evidence_json,
                            "last_used_at": "now()"
                        }).eq("skill_name", skill).execute()
                else:
                    supabase.table("skill_tracker").insert({
                        "skill_name": skill,
                        "category": category,
                        "proficiency_level": proficiency,
                        "evidence": evidence_json
                    }).execute()
                skills_updated += 1
    
    evidence_summary = {
        skill: {
            "files": evidence["files"][:5],
            "patterns": evidence["patterns_found"],
            "count": evidence["count"]
        }
        for skill, evidence in skill_evidence.items()
        if evidence["count"] > 0
    }
    
    return JSONResponse({
        "status": "ok",
        "skills_updated": skills_updated,
        "evidence": evidence_summary
    })


@router.post("/skills/populate-from-projects")
async def populate_skills_from_projects():
    """Populate skill tracker from completed projects and memories."""
    from ....infrastructure.supabase_client import get_supabase_client
    from ....services import ticket_service
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    skills_updated = 0
    projects_processed = 0
    skipped_already_processed = 0
    
    # Get already processed IDs
    tracking_result = supabase.table("skill_import_tracking").select("source_type,source_id").execute()
    processed = {(r.get("source_type"), str(r.get("source_id"))) for r in (tracking_result.data or [])}
    
    # Process completed project memories
    project_memories_result = supabase.table("career_memories").select(
        "id,skills,title"
    ).eq("memory_type", "completed_project").not_.is_("skills", "null").neq("skills", "").execute()
    
    for mem in (project_memories_result.data or []):
        mem_id = str(mem.get("id"))
        
        if ("career_memory", mem_id) in processed:
            skipped_already_processed += 1
            continue
        
        projects_processed += 1
        for skill in (mem.get("skills") or "").split(","):
            skill = skill.strip()
            if skill:
                existing = supabase.table("skill_tracker").select("id,proficiency_level,projects_count").eq(
                    "skill_name", skill
                ).execute()
                
                if existing.data:
                    current = existing.data[0]
                    new_prof = min(100, (current.get("proficiency_level") or 0) + 5)
                    new_count = (current.get("projects_count") or 0) + 1
                    supabase.table("skill_tracker").update({
                        "proficiency_level": new_prof,
                        "projects_count": new_count
                    }).eq("id", current.get("id")).execute()
                else:
                    supabase.table("skill_tracker").insert({
                        "skill_name": skill,
                        "category": "projects",
                        "proficiency_level": 20,
                        "projects_count": 1
                    }).execute()
                skills_updated += 1
        
        supabase.table("skill_import_tracking").insert({
            "source_type": "career_memory",
            "source_id": mem_id
        }).execute()
    
    # Process completed tickets
    all_tickets = ticket_service.get_all_tickets()
    completed_tickets = [t for t in all_tickets
                        if t.get("status") in ('done', 'complete', 'completed')
                        and t.get("tags")]
    
    for ticket in completed_tickets:
        ticket_id = str(ticket.get("id", ticket.get("key", "")))
        
        if ("ticket", ticket_id) in processed:
            skipped_already_processed += 1
            continue
        
        for tag in (ticket.get("tags") or "").split(","):
            tag = tag.strip()
            if tag:
                existing = supabase.table("skill_tracker").select("id,proficiency_level,tickets_count").eq(
                    "skill_name", tag
                ).execute()
                
                if existing.data:
                    current = existing.data[0]
                    new_prof = min(100, (current.get("proficiency_level") or 0) + 3)
                    new_count = (current.get("tickets_count") or 0) + 1
                    supabase.table("skill_tracker").update({
                        "proficiency_level": new_prof,
                        "tickets_count": new_count
                    }).eq("id", current.get("id")).execute()
                else:
                    supabase.table("skill_tracker").insert({
                        "skill_name": tag,
                        "category": "tickets",
                        "proficiency_level": 15,
                        "tickets_count": 1
                    }).execute()
                skills_updated += 1
        
        supabase.table("skill_import_tracking").insert({
            "source_type": "ticket",
            "source_id": ticket_id
        }).execute()
    
    return JSONResponse({
        "status": "ok",
        "projects_processed": projects_processed,
        "skills_updated": skills_updated,
        "skipped_already_processed": skipped_already_processed
    })


@router.post("/skills/update-from-tickets")
async def update_skills_from_tickets():
    """Update skill counts based on completed tickets."""
    from ....infrastructure.supabase_client import get_supabase_client
    from ....services import ticket_service
    
    supabase = get_supabase_client()
    if not supabase:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
    
    all_tickets = ticket_service.get_all_tickets()
    completed_tickets = [t for t in all_tickets
                        if t.get("status") in ('done', 'complete', 'completed')
                        and t.get("tags")]
    
    tag_counts = {}
    for t in completed_tickets:
        for tag in (t.get("tags") or "").split(","):
            tag = tag.strip().lower()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    updated = 0
    for tag, count in tag_counts.items():
        result = supabase.table("skill_tracker").select("id,tickets_count").ilike(
            "skill_name", f"%{tag}%"
        ).execute()
        
        for skill in (result.data or []):
            new_count = (skill.get("tickets_count") or 0) + count
            supabase.table("skill_tracker").update({
                "tickets_count": new_count
            }).eq("id", skill.get("id")).execute()
            updated += 1
    
    return JSONResponse({"status": "ok", "tags_processed": len(tag_counts)})


@router.post("/extract-resume-text")
async def extract_resume_text(request: Request):
    """Extract text from uploaded PDF resume file."""
    form = await request.form()
    file = form.get("file")
    
    if not file:
        return JSONResponse({"error": "No file uploaded"}, status_code=400)
    
    filename = file.filename.lower()
    content = await file.read()
    
    if filename.endswith('.pdf'):
        try:
            # Try PyPDF2 first
            try:
                import PyPDF2
                import io
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text() or '')
                text = '\n'.join(text_parts)
                if text.strip():
                    return JSONResponse({"status": "ok", "text": text})
            except ImportError:
                pass
            
            # Fallback: pdfplumber
            try:
                import pdfplumber
                import io
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    text_parts = []
                    for page in pdf.pages:
                        text_parts.append(page.extract_text() or '')
                    text = '\n'.join(text_parts)
                    if text.strip():
                        return JSONResponse({"status": "ok", "text": text})
            except ImportError:
                pass
            
            return JSONResponse({
                "error": "PDF parsing libraries not available. Install PyPDF2 or pdfplumber."
            }, status_code=500)
            
        except Exception as e:
            return JSONResponse({"error": f"Failed to parse PDF: {str(e)}"}, status_code=500)
    
    if filename.endswith('.txt'):
        try:
            text = content.decode('utf-8')
            return JSONResponse({"status": "ok", "text": text})
        except Exception:
            return JSONResponse({"error": "Failed to decode text file"}, status_code=500)
    
    return JSONResponse({"error": "Unsupported file type"}, status_code=400)
