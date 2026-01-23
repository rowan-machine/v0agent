#!/usr/bin/env python3
"""Trigger a test notification for the notification system."""

import sys
sys.path.insert(0, '/Users/rowan/v0agent')

from src.app.services.notification_queue import (
    NotificationQueue, Notification, NotificationType, NotificationPriority
)
from datetime import datetime, timedelta

queue = NotificationQueue()

# Create a test notification
notification = Notification(
    notification_type=NotificationType.COACH_RECOMMENDATION,
    title='Test Notification',
    body='This is a test notification to verify the system works! Click View to see your dashboard.',
    data={
        'test': True,
        'source': 'manual_trigger'
    },
    priority=NotificationPriority.HIGH,
    expires_at=datetime.now() + timedelta(days=1),
)

n_id = queue.create(notification)
print(f'Created notification: {n_id}')

# Check unread count
count = queue.get_unread_count()
print(f'Unread count: {count}')

# List pending
pending = queue.get_pending(limit=5)
print(f'Pending notifications: {len(pending)}')
for n in pending:
    print(f'  - {n.title} ({n.notification_type.value})')
