# src/app/services/documentation_reader.py
"""
Documentation Reader Service

Reads documentation from the repository to provide context for:
- AI implementation memories
- Skill development tracking
- Codebase assessment
- Architecture decisions

This enables the career section to pull real information from the project's
documentation rather than relying solely on user-entered memories.
"""

import os
import re
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Base path for documentation
DOCS_BASE = Path(__file__).parent.parent.parent.parent / "docs"
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class DocumentationReader:
    """Reads and parses documentation from the repository."""
    
    def __init__(self, base_path: Path = DOCS_BASE):
        self.base_path = base_path
        self.project_root = PROJECT_ROOT
    
    def get_all_docs(self, include_content: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of all documentation files.
        
        Args:
            include_content: Whether to include file contents
        
        Returns:
            List of doc metadata dicts
        """
        docs = []
        
        if not self.base_path.exists():
            logger.warning(f"Documentation path not found: {self.base_path}")
            return docs
        
        for md_file in self.base_path.rglob("*.md"):
            try:
                rel_path = md_file.relative_to(self.base_path)
                doc = {
                    "path": str(rel_path),
                    "name": md_file.stem,
                    "category": str(rel_path.parent) if str(rel_path.parent) != "." else "root",
                    "modified": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(),
                    "size": md_file.stat().st_size,
                }
                
                if include_content:
                    doc["content"] = md_file.read_text(encoding="utf-8")
                
                docs.append(doc)
            except Exception as e:
                logger.warning(f"Error reading doc {md_file}: {e}")
        
        return docs
    
    def read_doc(self, path: str) -> Optional[str]:
        """
        Read a specific documentation file.
        
        Args:
            path: Relative path within docs directory
        
        Returns:
            File content or None if not found
        """
        full_path = self.base_path / path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return None
    
    def get_adrs(self) -> List[Dict[str, Any]]:
        """
        Get Architecture Decision Records (ADRs).
        
        Returns:
            List of ADR metadata with parsed frontmatter
        """
        adr_path = self.base_path / "adr"
        adrs = []
        
        if not adr_path.exists():
            return adrs
        
        for adr_file in sorted(adr_path.glob("*.md")):
            if adr_file.name in ("README.md", "template.md"):
                continue
            
            try:
                content = adr_file.read_text(encoding="utf-8")
                adr = self._parse_adr(adr_file.name, content)
                adrs.append(adr)
            except Exception as e:
                logger.warning(f"Error parsing ADR {adr_file}: {e}")
        
        return adrs
    
    def _parse_adr(self, filename: str, content: str) -> Dict[str, Any]:
        """Parse an ADR file into structured data."""
        # Extract number and title from filename (e.g., "001-supabase-migration.md")
        match = re.match(r"(\d+)-(.+)\.md", filename)
        number = match.group(1) if match else "000"
        slug = match.group(2) if match else filename
        
        # Parse title from first H1
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else slug.replace("-", " ").title()
        
        # Extract status if present
        status_match = re.search(r"\*\*Status\*\*:\s*(.+)", content, re.IGNORECASE)
        status = status_match.group(1).strip() if status_match else "Proposed"
        
        # Extract technologies mentioned
        tech_patterns = [
            r"(Supabase|PostgreSQL|SQLite|Redis|FastAPI|Python|TypeScript|React|Docker|Railway)",
            r"(LangChain|OpenAI|Anthropic|Claude|GPT|Embedding|Vector|pgvector)",
            r"(Neo4j|GraphQL|REST|WebSocket|SSE)",
        ]
        technologies = set()
        for pattern in tech_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                technologies.add(match.group(1))
        
        return {
            "number": number,
            "slug": slug,
            "title": title,
            "status": status,
            "technologies": list(technologies),
            "filename": filename,
            "content": content,
        }
    
    def get_architecture_docs(self) -> List[Dict[str, Any]]:
        """
        Get architecture documentation files.
        
        Returns:
            List of architecture doc metadata
        """
        arch_path = self.base_path / "architecture"
        docs = []
        
        if not arch_path.exists():
            return docs
        
        for doc_file in arch_path.glob("*.md"):
            try:
                content = doc_file.read_text(encoding="utf-8")
                docs.append(self._parse_architecture_doc(doc_file.name, content))
            except Exception as e:
                logger.warning(f"Error parsing architecture doc {doc_file}: {e}")
        
        return docs
    
    def _parse_architecture_doc(self, filename: str, content: str) -> Dict[str, Any]:
        """Parse an architecture document."""
        # Extract title
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else filename.replace("_", " ").replace(".md", "")
        
        # Extract sections (H2 headers)
        sections = re.findall(r"^##\s+(.+)$", content, re.MULTILINE)
        
        # Extract technologies mentioned
        technologies = self._extract_technologies(content)
        
        return {
            "filename": filename,
            "title": title,
            "sections": sections,
            "technologies": technologies,
            "content": content,
        }
    
    def _extract_technologies(self, content: str) -> List[str]:
        """Extract technology names from content."""
        tech_patterns = [
            r"(Supabase|PostgreSQL|SQLite|Redis|FastAPI|Python|TypeScript|React|Docker|Railway)",
            r"(LangChain|OpenAI|Anthropic|Claude|GPT|Embedding|Vector|pgvector)",
            r"(Neo4j|GraphQL|REST|WebSocket|SSE|JWT|OAuth)",
            r"(ChromaDB|FAISS|Pinecone|Weaviate)",
            r"(Pydantic|SQLAlchemy|Alembic|pytest)",
        ]
        technologies = set()
        for pattern in tech_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                technologies.add(match.group(1))
        return list(technologies)
    
    def get_ai_implementations(self) -> List[Dict[str, Any]]:
        """
        Extract AI implementation details from documentation.
        
        This looks for AI/ML-related content across all docs.
        
        Returns:
            List of AI implementation records
        """
        implementations = []
        
        # Search in all docs
        all_docs = self.get_all_docs(include_content=True)
        
        ai_keywords = [
            "LLM", "GPT", "Claude", "Anthropic", "OpenAI", "embedding",
            "vector", "RAG", "agent", "prompt", "AI", "ML", "NLP",
            "semantic search", "knowledge graph", "signal extraction",
        ]
        
        for doc in all_docs:
            content = doc.get("content", "")
            
            # Check if doc is AI-related
            ai_mentions = sum(1 for kw in ai_keywords if kw.lower() in content.lower())
            if ai_mentions < 3:
                continue
            
            # Extract AI implementation details
            impl = {
                "source": f"docs/{doc['path']}",
                "title": doc["name"].replace("_", " ").replace("-", " ").title(),
                "category": doc["category"],
                "technologies": self._extract_technologies(content),
                "ai_relevance": ai_mentions,
            }
            
            # Try to extract a summary (first paragraph after title)
            summary_match = re.search(r"^#.+?\n\n(.+?)(?:\n\n|$)", content, re.DOTALL)
            if summary_match:
                impl["summary"] = summary_match.group(1)[:500].strip()
            
            implementations.append(impl)
        
        # Sort by AI relevance
        implementations.sort(key=lambda x: x["ai_relevance"], reverse=True)
        
        return implementations
    
    def get_skill_evidence(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract evidence of skills from documentation.
        
        Returns:
            Dict mapping skill names to evidence from docs
        """
        skills = {}
        
        all_docs = self.get_all_docs(include_content=True)
        
        for doc in all_docs:
            content = doc.get("content", "")
            techs = self._extract_technologies(content)
            
            for tech in techs:
                if tech not in skills:
                    skills[tech] = []
                
                skills[tech].append({
                    "source": f"docs/{doc['path']}",
                    "category": doc["category"],
                    "evidence_type": "documentation",
                })
        
        return skills
    
    def assess_codebase(self) -> Dict[str, Any]:
        """
        Assess the codebase structure and technologies.
        
        Returns:
            Assessment summary with technologies, patterns, and metrics
        """
        assessment = {
            "languages": {},
            "frameworks": [],
            "patterns": [],
            "directories": {},
            "metrics": {},
        }
        
        # Count files by extension
        for ext in [".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".json", ".yaml", ".yml"]:
            count = len(list(self.project_root.rglob(f"*{ext}")))
            if count > 0:
                assessment["languages"][ext] = count
        
        # Check for key framework files
        framework_markers = {
            "FastAPI": ["main.py", "requirements.txt"],
            "React": ["package.json", "tsconfig.json"],
            "Docker": ["Dockerfile", "docker-compose.yaml"],
            "pytest": ["pytest.ini", "conftest.py"],
        }
        
        for framework, markers in framework_markers.items():
            if any((self.project_root / marker).exists() for marker in markers):
                assessment["frameworks"].append(framework)
        
        # Check directory structure
        key_dirs = ["src", "tests", "docs", "config", "scripts", "mobile"]
        for dir_name in key_dirs:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                assessment["directories"][dir_name] = {
                    "exists": True,
                    "file_count": len(list(dir_path.rglob("*.*"))),
                }
        
        # Get total line count for Python files (rough metric)
        total_lines = 0
        for py_file in self.project_root.rglob("*.py"):
            if ".venv" not in str(py_file) and "__pycache__" not in str(py_file):
                try:
                    total_lines += sum(1 for _ in py_file.open())
                except:
                    pass
        assessment["metrics"]["python_lines"] = total_lines
        
        return assessment


# Singleton instance
_reader = None


def get_documentation_reader() -> DocumentationReader:
    """Get the documentation reader singleton."""
    global _reader
    if _reader is None:
        _reader = DocumentationReader()
    return _reader


# Convenience functions

def get_adrs() -> List[Dict[str, Any]]:
    """Get all Architecture Decision Records."""
    return get_documentation_reader().get_adrs()


def get_ai_implementations() -> List[Dict[str, Any]]:
    """Get AI implementation records from documentation."""
    return get_documentation_reader().get_ai_implementations()


def get_skill_evidence() -> Dict[str, List[Dict[str, Any]]]:
    """Get skill evidence from documentation."""
    return get_documentation_reader().get_skill_evidence()


def assess_codebase() -> Dict[str, Any]:
    """Get codebase assessment."""
    return get_documentation_reader().assess_codebase()
