#!/usr/bin/env python
"""Fix career_profile fields that have JSON array notation stored as strings."""
import sqlite3
import json
import re

def fix_list_fields():
    conn = sqlite3.connect('/Users/rowan/v0agent/agent.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fields that may have list-like strings
    list_fields = ['certifications', 'technical_specializations', 'work_achievements', 
                   'languages', 'soft_skills', 'strengths', 'short_term_goals', 'long_term_goals']

    profile = cursor.execute('SELECT * FROM career_profile LIMIT 1').fetchone()
    if not profile:
        print("No career profile found")
        return
    
    updates = []
    values = []
    
    for field in list_fields:
        val = profile[field]
        if val and (str(val).startswith('[') or "', '" in str(val)):
            # Parse Python list representation
            try:
                # Try JSON first (handles proper JSON arrays)
                items = json.loads(str(val).replace("'", '"'))
            except:
                # Parse Python list notation like ['a', 'b', 'c']
                items = re.findall(r"'([^']+)'", str(val))
            
            if items:
                clean_val = ', '.join(items)
                updates.append(f"{field} = ?")
                values.append(clean_val)
                print(f"FIXED {field}:")
                print(f"  OLD: {str(val)[:80]}...")
                print(f"  NEW: {clean_val[:80]}...")
    
    if updates:
        values.append(profile['id'])
        query = f"UPDATE career_profile SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        print(f"\n✅ Updated {len(updates)} fields!")
    else:
        print("No list-style strings found to fix")

    conn.close()

if __name__ == "__main__":
    fix_list_fields()
