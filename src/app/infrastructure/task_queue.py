# src/app/infrastructure/task_queue.py
"""
Background Task Queue - Phase 4.2

Provides async background task processing using Redis Queue (RQ).
Falls back to synchronous execution when Redis is not available.

Features:
- Job scheduling with priorities
- Retry logic with exponential backoff
- Job status tracking
- Graceful degradation (no Redis = sync execution)

Usage:
    from .task_queue import get_task_queue
    
    queue = get_task_queue()
    
    # Enqueue a task
    job_id = queue.enqueue(
        "process_meeting",
        meeting_id=123,
        priority="high"
    )
    
    # Check status
    status = queue.get_status(job_id)
"""

import asyncio
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobPriority(Enum):
    """Job priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Job:
    """Represents a background job."""
    id: str
    name: str
    kwargs: Dict[str, Any]
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3


class TaskQueue:
    """
    Background task queue with Redis support and fallback.
    
    When Redis is available, uses RQ for distributed task processing.
    When Redis is unavailable, executes tasks synchronously or in thread pool.
    """
    
    _instance: Optional['TaskQueue'] = None
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize task queue.
        
        Args:
            redis_url: Redis connection URL. If None, uses fallback mode.
        """
        self._redis_url = redis_url
        self._redis_client = None
        self._rq_queue = None
        self._fallback_mode = True
        self._jobs: Dict[str, Job] = {}
        self._handlers: Dict[str, Callable] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Try to connect to Redis
        self._connect_redis()
        
    def _connect_redis(self) -> bool:
        """Attempt to connect to Redis."""
        if not self._redis_url:
            logger.info("📦 Task queue running in fallback mode (no Redis)")
            return False
            
        try:
            import redis
            from rq import Queue
            
            self._redis_client = redis.from_url(self._redis_url)
            self._redis_client.ping()
            self._rq_queue = Queue(connection=self._redis_client)
            self._fallback_mode = False
            logger.info("✅ Task queue connected to Redis")
            return True
        except ImportError:
            logger.warning("⚠️ rq not installed, using fallback mode")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}, using fallback mode")
        
        return False
    
    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is connected."""
        return not self._fallback_mode
    
    def register_handler(self, name: str, handler: Callable) -> None:
        """
        Register a task handler function.
        
        Args:
            name: Task name
            handler: Function to execute for this task
        """
        self._handlers[name] = handler
        logger.debug(f"Registered task handler: {name}")
    
    def enqueue(
        self,
        task_name: str,
        priority: str = "normal",
        max_retries: int = 3,
        **kwargs
    ) -> str:
        """
        Enqueue a task for background processing.
        
        Args:
            task_name: Name of registered task handler
            priority: Job priority (low, normal, high, critical)
            max_retries: Maximum retry attempts on failure
            **kwargs: Arguments to pass to task handler
            
        Returns:
            Job ID for tracking
        """
        job = Job(
            id=str(uuid.uuid4()),
            name=task_name,
            kwargs=kwargs,
            priority=JobPriority(priority),
            max_retries=max_retries,
        )
        self._jobs[job.id] = job
        
        if self._fallback_mode:
            # Execute in thread pool
            self._executor.submit(self._execute_job, job)
        else:
            # Enqueue to Redis
            self._rq_queue.enqueue(
                self._execute_job_wrapper,
                job.id,
                job_timeout='5m',
            )
        
        logger.info(f"📥 Enqueued job {job.id}: {task_name}")
        return job.id
    
    def _execute_job(self, job: Job) -> None:
        """Execute a job synchronously."""
        handler = self._handlers.get(job.name)
        if not handler:
            job.status = JobStatus.FAILED
            job.error = f"No handler registered for task: {job.name}"
            logger.error(job.error)
            return
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        
        try:
            result = handler(**job.kwargs)
            job.result = result
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            logger.info(f"✅ Job {job.id} completed: {job.name}")
        except Exception as e:
            job.error = str(e)
            job.retries += 1
            
            if job.retries < job.max_retries:
                job.status = JobStatus.RETRYING
                logger.warning(f"⚠️ Job {job.id} failed, retrying ({job.retries}/{job.max_retries}): {e}")
                # Exponential backoff
                time.sleep(2 ** job.retries)
                self._execute_job(job)
            else:
                job.status = JobStatus.FAILED
                logger.error(f"❌ Job {job.id} failed after {job.retries} retries: {e}")
    
    def _execute_job_wrapper(self, job_id: str) -> Any:
        """Wrapper for RQ execution."""
        job = self._jobs.get(job_id)
        if job:
            self._execute_job(job)
            return job.result
        return None
    
    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status.
        
        Args:
            job_id: Job ID from enqueue()
            
        Returns:
            Job status dict or None if not found
        """
        job = self._jobs.get(job_id)
        if not job:
            return None
        
        return {
            "id": job.id,
            "name": job.name,
            "status": job.status.value,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result": job.result,
            "error": job.error,
            "retries": job.retries,
        }
    
    def get_pending_jobs(self) -> List[Dict[str, Any]]:
        """Get all pending jobs."""
        return [
            self.get_status(job.id)
            for job in self._jobs.values()
            if job.status == JobStatus.PENDING
        ]
    
    async def wait_for_job(self, job_id: str, timeout: float = 60.0) -> Optional[Dict[str, Any]]:
        """
        Wait for a job to complete.
        
        Args:
            job_id: Job ID to wait for
            timeout: Maximum wait time in seconds
            
        Returns:
            Final job status or None on timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(job_id)
            if status and status["status"] in ("completed", "failed"):
                return status
            await asyncio.sleep(0.1)
        return None
    
    def shutdown(self) -> None:
        """Shutdown the task queue."""
        self._executor.shutdown(wait=True)
        if self._redis_client:
            self._redis_client.close()


# Singleton instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue(redis_url: Optional[str] = None) -> TaskQueue:
    """
    Get the task queue singleton.
    
    Args:
        redis_url: Redis URL (only used on first call)
        
    Returns:
        TaskQueue instance
    """
    global _task_queue
    if _task_queue is None:
        # Try to get Redis URL from environment
        import os
        url = redis_url or os.environ.get("REDIS_URL")
        _task_queue = TaskQueue(redis_url=url)
    return _task_queue


# Task decorator for easy registration
def task(name: Optional[str] = None, priority: str = "normal"):
    """
    Decorator to register a function as a background task.
    
    Usage:
        @task("process_meeting")
        def process_meeting(meeting_id: int):
            ...
            
        # Enqueue
        get_task_queue().enqueue("process_meeting", meeting_id=123)
    """
    def decorator(func: Callable) -> Callable:
        task_name = name or func.__name__
        get_task_queue().register_handler(task_name, func)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Add enqueue method to function
        wrapper.enqueue = lambda **kw: get_task_queue().enqueue(task_name, priority=priority, **kw)
        return wrapper
    
    return decorator
