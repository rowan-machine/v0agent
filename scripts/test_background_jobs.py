#!/usr/bin/env python3
"""Test background job execution."""

import sys
sys.path.insert(0, '/Users/rowan/v0agent')

from src.app.services.background_jobs import run_job, JOB_CONFIGS

print("=" * 60)
print("Background Job System Test")
print("=" * 60)

print("\nAvailable jobs:")
for name, config in JOB_CONFIGS.items():
    status = "✅" if config.enabled else "❌"
    print(f"  {status} {name}: {config.description}")
    print(f"     Schedule: {config.schedule}")

print("\n" + "=" * 60)
print("Running 'stale_ticket_alert' job...")
print("=" * 60)

try:
    result = run_job("stale_ticket_alert")
    print(f"\nResult: {result}")
    
    if result.get('notifications_created'):
        print(f"\n✅ Created {result['notifications_created']} notification(s)")
    else:
        print("\nℹ️ No notifications created (no stale tickets found)")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Running 'sprint_mode_detect' job...")
print("=" * 60)

try:
    result = run_job("sprint_mode_detect")
    print(f"\nResult: {result}")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("All tests complete!")
print("=" * 60)
