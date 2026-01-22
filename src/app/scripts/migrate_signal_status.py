#!/usr/bin/env python3
"""Migrate signal_status from SQLite to Supabase with ID mapping."""

import sqlite3
import json

# SQLite meeting_id -> meeting_name mapping
SQLITE_MEETING_MAP = {
    5: "Data Eng & Infra Sprint Planning",
    7: "DMP Touchbase",
    8: "Quote-LinQ | Rx Sprint Planning",
    9: "Rx Product Overview",
    10: "Data Eng Backlog Grooming",
    11: "RN:RB 1-1",
    12: "Team Retrospective",
    13: "Rx Backlog Grooming",
    14: "Sync w John on Dev-8109 setup",
    15: "Rx Backlog Grooming",
    16: "Rx Product Overview Con't",
    17: "DMP<>CEO",
    18: "Rx Backlog Grooming",
    19: "[Document] Slack w Johnathan",
}

# Supabase meeting_name -> UUID mapping
SUPABASE_MEETING_MAP = {
    "Data Eng Sprint Planning": "2b454f96-acd6-42a9-af07-2f0b4d086c78",
    "DMP Touchbase": "21f66c92-a495-4279-9a32-164b496f4c9d",
    "RX Sprint Planning": "ba20f051-9118-43f3-9709-cf5b2fa8f2d9",
    "Rx Product Overview": "96f15f44-8525-4e2d-b4d4-4ff08d8dd2ac",
    "Data Eng Backlog Grooming": "0c94cee8-d613-4243-96a9-328ebc1a93b0",
    "Data Eng & Infra Sprint Planning": "5ced06d1-fff3-43be-8db3-0e1be16d3983",
    "Quote-LinQ | Rx Sprint Planning": "ba461d27-6e03-450b-be7e-bf9794d932ec",
    "RN:RB 1-1": "28e20b79-96ee-4e6d-89c2-6eef6ae7e769",
    "Team Retrospective": "19070245-13c3-44e5-8bca-c90afd140f54",
    "Rx Backlog Grooming": "25cb7b95-2970-494d-969a-392a0b2473f0",  # First one
    "Sync w John on Dev-8109 setup": "b6b3fdcc-defa-4382-9957-22367c1070ad",
    # "Rx Backlog Grooming": "dc1c973f-17d0-45c0-ade8-8cc13ae65a45",  # Second one
    "Rx Product Overview Con't": "4d7009ed-e0ec-4748-a60a-946c688a24b5",
    "DMP<>CEO": "405d0a1c-bdd8-4ab0-83a4-9d485484f900",
    # "Rx Backlog Grooming": "70cba815-2cbc-4b9e-890a-31a8c337f7d9",  # Third one
    "[Document] Slack w Johnathan": "72fb3085-c6fc-4b0f-8f9b-13dfaad4375a",
}


def get_supabase_meeting_id(sqlite_meeting_id: int) -> str | None:
    """Map SQLite meeting ID to Supabase UUID."""
    meeting_name = SQLITE_MEETING_MAP.get(sqlite_meeting_id)
    if not meeting_name:
        return None
    return SUPABASE_MEETING_MAP.get(meeting_name)


def generate_sql():
    """Generate SQL INSERT statements for signal_status migration."""
    conn = sqlite3.connect("agent.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT meeting_id, signal_type, signal_text, status, converted_to, converted_ref_id 
        FROM signal_status
    """)
    
    rows = cursor.fetchall()
    print(f"-- Found {len(rows)} signal_status records to migrate")
    
    for row in rows:
        supabase_meeting_id = get_supabase_meeting_id(row['meeting_id'])
        if not supabase_meeting_id:
            print(f"-- SKIP: No mapping for SQLite meeting_id {row['meeting_id']}")
            continue
            
        signal_text = row['signal_text'].replace("'", "''") if row['signal_text'] else ''
        signal_type = row['signal_type'] or 'unknown'
        status = row['status'] or 'pending'
        converted_to = f"'{row['converted_to']}'" if row['converted_to'] else 'NULL'
        converted_ref_id = f"'{row['converted_ref_id']}'" if row['converted_ref_id'] else 'NULL'
        
        print(f"""INSERT INTO signal_status (meeting_id, signal_type, signal_text, status, converted_to, converted_ref_id)
VALUES ('{supabase_meeting_id}', '{signal_type}', '{signal_text}', '{status}', {converted_to}, {converted_ref_id});""")
    
    conn.close()


if __name__ == "__main__":
    generate_sql()
