#!/usr/bin/env python3
"""Test script to introspect Pocket API structure."""
import os
import sys
import json

# Load .env
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v.strip('"').strip("'")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.app.integrations.pocket import PocketClient

def main():
    client = PocketClient()
    
    # List recordings
    print("Fetching recordings...")
    recordings = client.list_recordings(limit=50)
    print(f"Response type: {type(recordings)}")
    
    # Try different structures based on API response
    if isinstance(recordings, dict):
        print(f"Response keys: {list(recordings.keys())}")
        if 'data' in recordings:
            data = recordings['data']
            if isinstance(data, dict):
                recs = data.get('recordings', [])
            elif isinstance(data, list):
                recs = data
            else:
                recs = []
        elif 'recordings' in recordings:
            recs = recordings['recordings']
        else:
            recs = []
    elif isinstance(recordings, list):
        recs = recordings
    else:
        recs = []
    
    print(f"Found {len(recs)} recordings")
    
    # Check all recordings for mind map types
    print("\n=== Checking all recordings ===")
    for rec in recs:
        rec_id = rec.get('id')
        title = rec.get('title', 'Untitled')[:40]
        details = client.get_recording(rec_id, include_transcript=False, include_summarizations=True)
        summ = details.get('data', {}).get('summarizations', {})
        
        mind_map_types = []
        for k, v in summ.items():
            if 'mind_map' in k.lower() and isinstance(v, dict):
                mm_type = v.get('type', 'unknown')
                mind_map_types.append(f"{k}:{mm_type}")
        
        summary_versions = []
        for k, v in summ.items():
            if 'summary' in k.lower() and isinstance(v, dict):
                ver = v.get('version', '?')
                summary_versions.append(f"{k}:v{ver}")
        
        print(f"  {title}: mindmaps={mind_map_types}, summaries={summary_versions}")
    
    # Find Therapy Insights recording
    therapy_rec = None
    for rec in recs:
        title = rec.get('title') or ''
        if 'Therapy' in title:
            therapy_rec = rec
    
    if therapy_rec:
        print(f"\n=== Analyzing: {therapy_rec.get('title')} ===")
        print(f"ID: {therapy_rec.get('id')}")
        
        details = client.get_recording(therapy_rec['id'], include_transcript=True, include_summarizations=True)
        summ = details.get('data', {}).get('summarizations', {})
        
        print(f"\nSummarization keys: {list(summ.keys())}")
        
        for k, v in summ.items():
            if isinstance(v, dict):
                v_type = v.get('type', 'N/A')
                v_keys = list(v.keys())
                print(f"\n  {k}:")
                print(f"    type: {v_type}")
                print(f"    keys: {v_keys}")
                
                # Check for version info
                if 'version' in v:
                    print(f"    version: {v.get('version')}")
                
                # Check for markdown/text content
                if 'markdown' in v:
                    md = v.get('markdown', '')
                    print(f"    markdown length: {len(md) if md else 0}")
                if 'text' in v:
                    txt = v.get('text', '')
                    print(f"    text length: {len(txt) if txt else 0}")
                    
                # For mind maps, check nodes structure
                if 'nodes' in v:
                    nodes = v.get('nodes', [])
                    print(f"    nodes count: {len(nodes)}")
                    if nodes and isinstance(nodes[0], dict):
                        print(f"    node keys: {list(nodes[0].keys())}")
            else:
                print(f"\n  {k}: {type(v).__name__}")
    else:
        print("\nNo 'Therapy' recording found. Available recordings:")
        for rec in recs[:10]:
            print(f"  - {rec.get('title')}")

if __name__ == '__main__':
    main()
