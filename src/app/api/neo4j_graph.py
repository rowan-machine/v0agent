# src/app/api/neo4j_graph.py
"""
Neo4j Knowledge Graph API - Builds and queries a knowledge graph from app data.

Graph Schema:
- Nodes: Meeting, Document, Signal, Ticket, DIKWItem, Person, Topic, Tag
- Relationships: HAS_SIGNAL, MENTIONS, RELATED_TO, ASSIGNED_TO, BLOCKS, PROMOTES_TO, etc.
"""

import os
import json
from typing import List, Dict
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from ..db import connect

router = APIRouter()

# Neo4j connection - lazy loaded
_driver = None

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")


def get_driver():
    """Get or create Neo4j driver connection."""
    global _driver
    if _driver is None:
        try:
            from neo4j import GraphDatabase
            _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            # Verify connectivity
            _driver.verify_connectivity()
        except ImportError:
            raise RuntimeError("neo4j package not installed. Run: pip install neo4j")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Neo4j: {e}")
    return _driver


def close_driver():
    """Close the Neo4j driver."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def run_query(query: str, params: dict = None) -> List[Dict]:
    """Run a Cypher query and return results."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, params or {})
        return [dict(record) for record in result]


def run_write(query: str, params: dict = None):
    """Run a write Cypher query."""
    driver = get_driver()
    with driver.session() as session:
        session.run(query, params or {})


def is_neo4j_available() -> bool:
    """Check if Neo4j is available without raising exceptions."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        driver.close()
        return True
    except:
        return False


def safe_run_write(query: str, params: dict = None) -> bool:
    """Run a write query safely, returning True on success, False on failure."""
    try:
        run_write(query, params)
        return True
    except:
        return False


# ============================================
# Background Sync Functions (safe to call from other modules)
# ============================================

def sync_single_meeting(meeting_id: int, meeting_name: str, notes: str, meeting_date: str, signals_json: str = None):
    """
    Sync a single meeting to Neo4j. Safe to call - silently fails if Neo4j unavailable.
    Call this after creating/updating a meeting.
    """
    try:
        # Create Meeting node
        run_write("""
            MERGE (m:Meeting {sqlite_id: $id})
            SET m.name = $name,
                m.notes = $notes,
                m.meeting_date = $meeting_date,
                m.updated_at = datetime()
        """, {
            "id": meeting_id,
            "name": meeting_name,
            "notes": notes[:2000] if notes else None,
            "meeting_date": meeting_date
        })
        
        # Extract and create signals
        if signals_json:
            try:
                signals = json.loads(signals_json) if isinstance(signals_json, str) else signals_json
                for signal_type, items in signals.items():
                    if isinstance(items, list):
                        for idx, item in enumerate(items):
                            text = item if isinstance(item, str) else item.get("text", str(item))
                            signal_id = f"{meeting_id}_{signal_type}_{idx}"
                            
                            run_write("""
                                MERGE (s:Signal {id: $signal_id})
                                SET s.signal_type = $signal_type,
                                    s.text = $text
                                WITH s
                                MATCH (m:Meeting {sqlite_id: $meeting_id})
                                MERGE (m)-[:HAS_SIGNAL]->(s)
                            """, {
                                "signal_id": signal_id,
                                "signal_type": signal_type,
                                "text": text[:1000] if text else None,
                                "meeting_id": meeting_id
                            })
                            
                            # Extract people from signal
                            people = extract_people_from_text(text)
                            for person in people:
                                safe_run_write("""
                                    MERGE (p:Person {name: $name})
                                    WITH p
                                    MATCH (s:Signal {id: $signal_id})
                                    MERGE (s)-[:MENTIONS]->(p)
                                """, {"name": person, "signal_id": signal_id})
            except json.JSONDecodeError:
                pass
        
        # Extract people from meeting notes
        people = extract_people_from_text(notes)
        for person in people:
            safe_run_write("""
                MERGE (p:Person {name: $name})
                WITH p
                MATCH (m:Meeting {sqlite_id: $meeting_id})
                MERGE (m)-[:MENTIONS]->(p)
            """, {"name": person, "meeting_id": meeting_id})
        
        return True
    except Exception as e:
        # Silently fail - Neo4j is optional
        print(f"Neo4j sync failed for meeting {meeting_id}: {e}")
        return False


def sync_single_document(doc_id: int, source: str, content: str, document_date: str):
    """
    Sync a single document to Neo4j. Safe to call - silently fails if Neo4j unavailable.
    Call this after creating/updating a document.
    """
    try:
        run_write("""
            MERGE (d:Document {sqlite_id: $id})
            SET d.source = $source,
                d.content = $content,
                d.document_date = $document_date,
                d.updated_at = datetime()
        """, {
            "id": doc_id,
            "source": source,
            "content": content[:2000] if content else None,
            "document_date": document_date
        })
        
        # Extract people and topics
        people = extract_people_from_text(content)
        for person in people:
            safe_run_write("""
                MERGE (p:Person {name: $name})
                WITH p
                MATCH (d:Document {sqlite_id: $doc_id})
                MERGE (d)-[:MENTIONS]->(p)
            """, {"name": person, "doc_id": doc_id})
        
        topics = extract_topics_from_text(content)
        for topic in topics:
            safe_run_write("""
                MERGE (t:Topic {name: $name})
                WITH t
                MATCH (d:Document {sqlite_id: $doc_id})
                MERGE (d)-[:ABOUT]->(t)
            """, {"name": topic, "doc_id": doc_id})
        
        return True
    except Exception as e:
        print(f"Neo4j sync failed for document {doc_id}: {e}")
        return False


def sync_single_ticket(ticket_id: str, title: str, description: str = None, status: str = None, 
                       priority: str = None, assignee: str = None, labels: list = None):
    """
    Sync a single ticket to Neo4j. Safe to call - silently fails if Neo4j unavailable.
    """
    try:
        run_write("""
            MERGE (t:Ticket {ticket_id: $ticket_id})
            SET t.title = $title,
                t.description = $description,
                t.status = $status,
                t.priority = $priority,
                t.updated_at = datetime()
        """, {
            "ticket_id": ticket_id,
            "title": title,
            "description": description[:1000] if description else None,
            "status": status,
            "priority": priority
        })
        
        # Link to assignee
        if assignee:
            safe_run_write("""
                MERGE (p:Person {name: $name})
                WITH p
                MATCH (t:Ticket {ticket_id: $ticket_id})
                MERGE (t)-[:ASSIGNED_TO]->(p)
            """, {"name": assignee, "ticket_id": ticket_id})
        
        # Add labels as tags
        if labels:
            for label in labels:
                safe_run_write("""
                    MERGE (tag:Tag {name: $name})
                    WITH tag
                    MATCH (t:Ticket {ticket_id: $ticket_id})
                    MERGE (t)-[:HAS_TAG]->(tag)
                """, {"name": label, "ticket_id": ticket_id})
        
        return True
    except Exception as e:
        print(f"Neo4j sync failed for ticket {ticket_id}: {e}")
        return False


# ============================================
# Schema Creation
# ============================================

SCHEMA_QUERIES = [
    # Constraints for uniqueness
    "CREATE CONSTRAINT meeting_id IF NOT EXISTS FOR (m:Meeting) REQUIRE m.sqlite_id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.sqlite_id IS UNIQUE",
    "CREATE CONSTRAINT ticket_id IF NOT EXISTS FOR (t:Ticket) REQUIRE t.ticket_id IS UNIQUE",
    "CREATE CONSTRAINT dikw_id IF NOT EXISTS FOR (dk:DIKWItem) REQUIRE dk.sqlite_id IS UNIQUE",
    "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (tp:Topic) REQUIRE tp.name IS UNIQUE",
    "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (tg:Tag) REQUIRE tg.name IS UNIQUE",
    
    # Indexes for faster lookups
    "CREATE INDEX meeting_date IF NOT EXISTS FOR (m:Meeting) ON (m.meeting_date)",
    "CREATE INDEX ticket_status IF NOT EXISTS FOR (t:Ticket) ON (t.status)",
    "CREATE INDEX dikw_level IF NOT EXISTS FOR (dk:DIKWItem) ON (dk.level)",
    "CREATE INDEX signal_type IF NOT EXISTS FOR (s:Signal) ON (s.signal_type)",
]


@router.post("/api/neo4j/init-schema")
async def init_neo4j_schema():
    """Initialize Neo4j schema with constraints and indexes."""
    try:
        errors = []
        for query in SCHEMA_QUERIES:
            try:
                run_write(query)
            except Exception as e:
                errors.append(f"{query[:50]}...: {str(e)}")
        
        if errors:
            return JSONResponse({
                "status": "partial",
                "message": "Schema created with some warnings",
                "warnings": errors
            })
        
        return JSONResponse({"status": "ok", "message": "Schema initialized successfully"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================
# Data Sync Functions
# ============================================

def extract_people_from_text(text: str) -> List[str]:
    """Extract person names from text using simple heuristics."""
    # Common patterns: @mentions, "assigned to X", names with capital letters
    import re
    
    people = set()
    
    # @mentions
    mentions = re.findall(r'@(\w+)', text or '')
    people.update(mentions)
    
    # "assigned to [Name]" pattern
    assigned = re.findall(r'assigned to (\w+(?:\s+\w+)?)', text or '', re.I)
    people.update(assigned)
    
    # Names in brackets [Name]
    brackets = re.findall(r'\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\]', text or '')
    people.update(brackets)
    
    return list(people)


def extract_topics_from_text(text: str) -> List[str]:
    """Extract topics/keywords from text."""
    # Simple keyword extraction - could be enhanced with NLP
    import re
    
    # Look for technical terms, capitalized phrases
    topics = set()
    
    # Hashtags
    hashtags = re.findall(r'#(\w+)', text or '')
    topics.update(hashtags)
    
    # Technical terms (simple pattern)
    tech_terms = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text or '')  # CamelCase
    topics.update(tech_terms)
    
    return list(topics)[:10]  # Limit to 10 topics


@router.post("/api/neo4j/sync-meetings")
async def sync_meetings_to_neo4j():
    """Sync all meetings to Neo4j."""
    try:
        with connect() as conn:
            meetings = conn.execute(
                "SELECT * FROM meeting_summaries ORDER BY id"
            ).fetchall()
        
        count = 0
        for meeting in meetings:
            # Create Meeting node
            run_write("""
                MERGE (m:Meeting {sqlite_id: $id})
                SET m.name = $name,
                    m.notes = $notes,
                    m.meeting_date = $meeting_date,
                    m.created_at = $created_at
            """, {
                "id": meeting["id"],
                "name": meeting["meeting_name"],
                "notes": meeting["synthesized_notes"][:2000] if meeting["synthesized_notes"] else None,
                "meeting_date": meeting["meeting_date"],
                "created_at": meeting["created_at"]
            })
            
            # Extract and create signals
            if meeting["signals_json"]:
                try:
                    signals = json.loads(meeting["signals_json"])
                    for signal_type, items in signals.items():
                        if isinstance(items, list):
                            for idx, item in enumerate(items):
                                text = item if isinstance(item, str) else item.get("text", str(item))
                                signal_id = f"{meeting['id']}_{signal_type}_{idx}"
                                
                                run_write("""
                                    MERGE (s:Signal {id: $signal_id})
                                    SET s.signal_type = $signal_type,
                                        s.text = $text
                                    WITH s
                                    MATCH (m:Meeting {sqlite_id: $meeting_id})
                                    MERGE (m)-[:HAS_SIGNAL]->(s)
                                """, {
                                    "signal_id": signal_id,
                                    "signal_type": signal_type,
                                    "text": text[:1000] if text else None,
                                    "meeting_id": meeting["id"]
                                })
                                
                                # Extract people from signal
                                people = extract_people_from_text(text)
                                for person in people:
                                    run_write("""
                                        MERGE (p:Person {name: $name})
                                        WITH p
                                        MATCH (s:Signal {id: $signal_id})
                                        MERGE (s)-[:MENTIONS]->(p)
                                    """, {"name": person, "signal_id": signal_id})
                except json.JSONDecodeError:
                    pass
            
            # Extract people from meeting
            people = extract_people_from_text(meeting["synthesized_notes"])
            for person in people:
                run_write("""
                    MERGE (p:Person {name: $name})
                    WITH p
                    MATCH (m:Meeting {sqlite_id: $meeting_id})
                    MERGE (m)-[:MENTIONS]->(p)
                """, {"name": person, "meeting_id": meeting["id"]})
            
            count += 1
        
        return JSONResponse({"status": "ok", "synced": count})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/neo4j/sync-documents")
async def sync_documents_to_neo4j():
    """Sync all documents to Neo4j."""
    try:
        with connect() as conn:
            docs = conn.execute("SELECT * FROM docs ORDER BY id").fetchall()
        
        count = 0
        for doc in docs:
            run_write("""
                MERGE (d:Document {sqlite_id: $id})
                SET d.source = $source,
                    d.content = $content,
                    d.document_date = $document_date,
                    d.created_at = $created_at
            """, {
                "id": doc["id"],
                "source": doc["source"],
                "content": doc["content"][:2000] if doc["content"] else None,
                "document_date": doc["document_date"],
                "created_at": doc["created_at"]
            })
            
            # Extract topics
            topics = extract_topics_from_text(doc["content"])
            for topic in topics:
                run_write("""
                    MERGE (tp:Topic {name: $name})
                    WITH tp
                    MATCH (d:Document {sqlite_id: $doc_id})
                    MERGE (d)-[:ABOUT]->(tp)
                """, {"name": topic, "doc_id": doc["id"]})
            
            count += 1
        
        return JSONResponse({"status": "ok", "synced": count})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/neo4j/sync-tickets")
async def sync_tickets_to_neo4j():
    """Sync all tickets to Neo4j."""
    try:
        with connect() as conn:
            tickets = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        
        count = 0
        for ticket in tickets:
            run_write("""
                MERGE (t:Ticket {ticket_id: $ticket_id})
                SET t.sqlite_id = $id,
                    t.title = $title,
                    t.description = $description,
                    t.status = $status,
                    t.priority = $priority,
                    t.ai_summary = $ai_summary,
                    t.created_at = $created_at
            """, {
                "id": ticket["id"],
                "ticket_id": ticket["ticket_id"],
                "title": ticket["title"],
                "description": ticket["description"][:1000] if ticket["description"] else None,
                "status": ticket["status"],
                "priority": ticket["priority"],
                "ai_summary": ticket["ai_summary"],
                "created_at": ticket["created_at"]
            })
            
            # Create tags
            if ticket["tags"]:
                for tag in ticket["tags"].split(","):
                    tag = tag.strip()
                    if tag:
                        run_write("""
                            MERGE (tg:Tag {name: $name})
                            WITH tg
                            MATCH (t:Ticket {ticket_id: $ticket_id})
                            MERGE (t)-[:TAGGED]->(tg)
                        """, {"name": tag, "ticket_id": ticket["ticket_id"]})
            
            count += 1
        
        return JSONResponse({"status": "ok", "synced": count})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/neo4j/sync-dikw")
async def sync_dikw_to_neo4j():
    """Sync DIKW items to Neo4j."""
    try:
        with connect() as conn:
            items = conn.execute(
                "SELECT * FROM dikw_items WHERE status = 'active' ORDER BY id"
            ).fetchall()
        
        count = 0
        for item in items:
            run_write("""
                MERGE (dk:DIKWItem {sqlite_id: $id})
                SET dk.level = $level,
                    dk.content = $content,
                    dk.summary = $summary,
                    dk.source_type = $source_type,
                    dk.original_signal_type = $original_signal_type,
                    dk.confidence = $confidence,
                    dk.created_at = $created_at
            """, {
                "id": item["id"],
                "level": item["level"],
                "content": item["content"][:1000] if item["content"] else None,
                "summary": item["summary"],
                "source_type": item["source_type"],
                "original_signal_type": item["original_signal_type"],
                "confidence": item["confidence"],
                "created_at": item["created_at"]
            })
            
            # Link to source meeting
            if item["meeting_id"]:
                run_write("""
                    MATCH (dk:DIKWItem {sqlite_id: $dikw_id})
                    MATCH (m:Meeting {sqlite_id: $meeting_id})
                    MERGE (dk)-[:DERIVED_FROM]->(m)
                """, {"dikw_id": item["id"], "meeting_id": item["meeting_id"]})
            
            # Link promoted items
            if item["promoted_to"]:
                run_write("""
                    MATCH (dk1:DIKWItem {sqlite_id: $from_id})
                    MATCH (dk2:DIKWItem {sqlite_id: $to_id})
                    MERGE (dk1)-[:PROMOTES_TO]->(dk2)
                """, {"from_id": item["id"], "to_id": item["promoted_to"]})
            
            # Tags
            if item["tags"]:
                for tag in item["tags"].split(","):
                    tag = tag.strip()
                    if tag:
                        run_write("""
                            MERGE (tg:Tag {name: $name})
                            WITH tg
                            MATCH (dk:DIKWItem {sqlite_id: $dikw_id})
                            MERGE (dk)-[:TAGGED]->(tg)
                        """, {"name": tag, "dikw_id": item["id"]})
            
            count += 1
        
        return JSONResponse({"status": "ok", "synced": count})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/neo4j/sync-all")
async def sync_all_to_neo4j():
    """Sync all data to Neo4j knowledge graph."""
    try:
        # Initialize schema first
        await init_neo4j_schema()
        
        # Sync each entity type
        meetings_result = await sync_meetings_to_neo4j()
        docs_result = await sync_documents_to_neo4j()
        tickets_result = await sync_tickets_to_neo4j()
        dikw_result = await sync_dikw_to_neo4j()
        
        # Create cross-entity relationships using AI
        await create_semantic_relationships()
        
        return JSONResponse({
            "status": "ok",
            "meetings": meetings_result.body if hasattr(meetings_result, 'body') else "synced",
            "documents": docs_result.body if hasattr(docs_result, 'body') else "synced",
            "tickets": tickets_result.body if hasattr(tickets_result, 'body') else "synced",
            "dikw": dikw_result.body if hasattr(dikw_result, 'body') else "synced"
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/neo4j/create-relationships")
async def create_semantic_relationships():
    """Create semantic relationships between entities using text similarity."""
    try:
        # Link tickets to meetings that mention them
        run_write("""
            MATCH (t:Ticket)
            MATCH (m:Meeting)
            WHERE m.notes CONTAINS t.ticket_id OR m.notes CONTAINS t.title
            MERGE (m)-[:REFERENCES]->(t)
        """)
        
        # Link documents to meetings by date proximity
        run_write("""
            MATCH (d:Document)
            MATCH (m:Meeting)
            WHERE d.document_date IS NOT NULL 
              AND m.meeting_date IS NOT NULL
              AND d.document_date = m.meeting_date
            MERGE (d)-[:SAME_DAY]->(m)
        """)
        
        # Link signals that mention the same person
        run_write("""
            MATCH (s1:Signal)-[:MENTIONS]->(p:Person)<-[:MENTIONS]-(s2:Signal)
            WHERE id(s1) < id(s2)
            MERGE (s1)-[:RELATED_PERSON]->(s2)
        """)
        
        # Link DIKW items to tickets with similar content
        run_write("""
            MATCH (dk:DIKWItem)
            MATCH (t:Ticket)
            WHERE dk.content CONTAINS t.title OR t.description CONTAINS dk.summary
            MERGE (dk)-[:RELATES_TO]->(t)
        """)
        
        return JSONResponse({"status": "ok", "message": "Relationships created"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================
# Query Endpoints
# ============================================

@router.get("/api/neo4j/stats")
async def get_graph_stats():
    """Get statistics about the knowledge graph."""
    try:
        stats = {}
        
        # Node counts
        node_counts = run_query("""
            MATCH (n)
            RETURN labels(n)[0] as label, count(*) as count
            ORDER BY count DESC
        """)
        stats["nodes"] = {r["label"]: r["count"] for r in node_counts}
        
        # Relationship counts
        rel_counts = run_query("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(*) as count
            ORDER BY count DESC
        """)
        stats["relationships"] = {r["type"]: r["count"] for r in rel_counts}
        
        # Total counts
        totals = run_query("""
            MATCH (n) 
            WITH count(n) as nodes
            MATCH ()-[r]->()
            RETURN nodes, count(r) as relationships
        """)
        if totals:
            stats["total_nodes"] = totals[0]["nodes"]
            stats["total_relationships"] = totals[0]["relationships"]
        
        return JSONResponse(stats)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/neo4j/search")
async def search_graph(q: str = Query(..., description="Search query")):
    """Search the knowledge graph for matching nodes."""
    try:
        results = run_query("""
            CALL db.index.fulltext.queryNodes('search_index', $query) YIELD node, score
            RETURN labels(node)[0] as type, 
                   node.name as name,
                   node.title as title,
                   node.content as content,
                   score
            LIMIT 20
        """, {"query": q})
        
        # Fallback to CONTAINS search if fulltext not available
        if not results:
            results = run_query("""
                MATCH (n)
                WHERE n.name CONTAINS $query 
                   OR n.title CONTAINS $query 
                   OR n.content CONTAINS $query
                   OR n.text CONTAINS $query
                RETURN labels(n)[0] as type,
                       coalesce(n.name, n.title, n.ticket_id) as name,
                       n.content as content
                LIMIT 20
            """, {"query": q})
        
        return JSONResponse({"results": results})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/neo4j/person/{name}")
async def get_person_context(name: str):
    """Get all context related to a person."""
    try:
        # Get meetings mentioning person
        meetings = run_query("""
            MATCH (p:Person {name: $name})<-[:MENTIONS]-(m:Meeting)
            RETURN m.name as meeting, m.meeting_date as date, m.sqlite_id as id
            ORDER BY m.meeting_date DESC
            LIMIT 10
        """, {"name": name})
        
        # Get signals mentioning person
        signals = run_query("""
            MATCH (p:Person {name: $name})<-[:MENTIONS]-(s:Signal)
            RETURN s.signal_type as type, s.text as text
            LIMIT 20
        """, {"name": name})
        
        # Get connected people (co-mentioned)
        connected = run_query("""
            MATCH (p:Person {name: $name})<-[:MENTIONS]-(m:Meeting)-[:MENTIONS]->(p2:Person)
            WHERE p2.name <> $name
            RETURN p2.name as person, count(*) as meetings
            ORDER BY meetings DESC
            LIMIT 10
        """, {"name": name})
        
        return JSONResponse({
            "person": name,
            "meetings": meetings,
            "signals": signals,
            "connected_people": connected
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/neo4j/meeting/{meeting_id}/graph")
async def get_meeting_subgraph(meeting_id: int):
    """Get the subgraph around a meeting for visualization."""
    try:
        # Get meeting and connected nodes
        nodes = run_query("""
            MATCH (m:Meeting {sqlite_id: $id})
            OPTIONAL MATCH (m)-[:HAS_SIGNAL]->(s:Signal)
            OPTIONAL MATCH (m)-[:MENTIONS]->(p:Person)
            OPTIONAL MATCH (m)-[:REFERENCES]->(t:Ticket)
            RETURN 
                collect(DISTINCT {id: 'm_' + toString(m.sqlite_id), label: m.name, type: 'Meeting'}) +
                collect(DISTINCT {id: 's_' + s.id, label: left(s.text, 50), type: 'Signal', signal_type: s.signal_type}) +
                collect(DISTINCT {id: 'p_' + p.name, label: p.name, type: 'Person'}) +
                collect(DISTINCT {id: 't_' + t.ticket_id, label: t.title, type: 'Ticket'})
                as nodes
        """, {"id": meeting_id})
        
        # Get relationships
        edges = run_query("""
            MATCH (m:Meeting {sqlite_id: $id})-[r]->(n)
            RETURN 
                'm_' + toString(m.sqlite_id) as source,
                CASE 
                    WHEN n:Signal THEN 's_' + n.id
                    WHEN n:Person THEN 'p_' + n.name
                    WHEN n:Ticket THEN 't_' + n.ticket_id
                END as target,
                type(r) as type
        """, {"id": meeting_id})
        
        return JSONResponse({
            "nodes": nodes[0]["nodes"] if nodes else [],
            "edges": edges
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/neo4j/dikw-chain/{item_id}")
async def get_dikw_chain(item_id: int):
    """Get the promotion chain for a DIKW item."""
    try:
        chain = run_query("""
            MATCH path = (start:DIKWItem {sqlite_id: $id})-[:PROMOTES_TO*0..]->(end:DIKWItem)
            RETURN [n in nodes(path) | {
                id: n.sqlite_id,
                level: n.level,
                content: n.content,
                summary: n.summary,
                confidence: n.confidence
            }] as chain
            ORDER BY length(path) DESC
            LIMIT 1
        """, {"id": item_id})
        
        # Also get the source chain going backwards
        source_chain = run_query("""
            MATCH path = (start:DIKWItem)-[:PROMOTES_TO*0..]->(end:DIKWItem {sqlite_id: $id})
            RETURN [n in nodes(path) | {
                id: n.sqlite_id,
                level: n.level,
                content: n.content,
                summary: n.summary,
                confidence: n.confidence
            }] as chain
            ORDER BY length(path) DESC
            LIMIT 1
        """, {"id": item_id})
        
        return JSONResponse({
            "forward_chain": chain[0]["chain"] if chain else [],
            "source_chain": source_chain[0]["chain"] if source_chain else []
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/neo4j/query")
async def run_cypher_query(request: Request):
    """Run a custom Cypher query (read-only for safety)."""
    try:
        data = await request.json()
        query = data.get("query", "")
        params = data.get("params", {})
        
        # Safety check - only allow read queries
        query_lower = query.lower().strip()
        if any(word in query_lower for word in ['create', 'merge', 'delete', 'set', 'remove', 'drop']):
            return JSONResponse(
                {"error": "Only read queries allowed. Use MATCH/RETURN."},
                status_code=400
            )
        
        results = run_query(query, params)
        return JSONResponse({"results": results})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/neo4j/clear")
async def clear_graph():
    """Clear all data from the Neo4j graph (use with caution!)."""
    try:
        run_write("MATCH (n) DETACH DELETE n")
        return JSONResponse({"status": "ok", "message": "Graph cleared"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
