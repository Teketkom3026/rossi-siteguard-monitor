"""
Redis-based task queue using aioredis for async check dispatching.
Provides reliable task queuing, deduplication, and result storage
for site monitoring checks.
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable

try:
    import redis.asyncio as aioredis
except ImportError:
    import aioredis

logger = logging.getLogger(__name__)


class TaskPriority:
    """Task priority levels for queue ordering."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class TaskStatus:
    """Task lifecycle states."""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    RETRYING = 'retrying'


class Task:
    """Represents a single queued task."""

    def __init__(
        self,
        task_type: str,
        domain: str,
        payload: Optional[dict] = None,
        priority: int = TaskPriority.MEDIUM,
        max_retries: int = 3,
        task_id: Optional[str] = None,
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.task_type = task_type
        self.domain = domain
        self.payload = payload or {}
        self.priority = priority
        self.max_retries = max_retries
        self.retries = 0
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Optional[dict] = None
        self.error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize task to dictionary."""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'domain': self.domain,
            'payload': self.payload,
            'priority': self.priority,
            'max_retries': self.max_retries,
            'retries': self.retries,
            'status': self.status,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'result': self.result,
            'error': self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """Deserialize task from dictionary."""
        task = cls(
            task_type=data['task_type'],
            domain=data['domain'],
            payload=data.get('payload', {}),
            priority=data.get('priority', TaskPriority.MEDIUM),
            max_retries=data.get('max_retries', 3),
            task_id=data.get('task_id'),
        )
        task.retries = data.get('retries', 0)
        task.status = data.get('status', TaskStatus.PENDING)
        task.created_at = data.get('created_at', task.created_at)
        task.started_at = data.get('started_at')
        task.completed_at = data.get('completed_at')
        task.result = data.get('result')
        task.error = data.get('error')
        return task


class TaskQueue:
    """
    Redis-based async task queue for dispatching site monitoring checks.

    Features:
    - Priority-based task ordering
    - Task deduplication (prevents duplicate checks for same domain/type)
    - Automatic retry with configurable limits
    - Task result storage with TTL
    - Worker pool management
    - Dead letter queue for permanently failed tasks
    """

    QUEUE_KEY = 'siteguard:tasks:queue'
    PROCESSING_KEY = 'siteguard:tasks:processing'
    RESULTS_KEY = 'siteguard:tasks:results'
    DEDUP_KEY = 'siteguard:tasks:dedup'
    DLQ_KEY = 'siteguard:tasks:dlq'
    STATS_KEY = 'siteguard:tasks:stats'

    def __init__(
        self,
        redis_url: str = 'redis://localhost:6379/0',
        result_ttl: int = 3600,
        dedup_ttl: int = 60,
        max_workers: int = 10,
    ):
        self.redis_url = redis_url
        self.result_ttl = result_ttl
        self.dedup_ttl = dedup_ttl
        self.max_workers = max_workers
        self.redis: Optional[aioredis.Redis] = None
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._workers: List[asyncio.Task] = []

    async def connect(self):
        """Establish connection to Redis."""
        self.redis = aioredis.from_url(
            self.redis_url,
            encoding='utf-8',
            decode_responses=True,
        )
        await self.redis.ping()
        logger.info(f"TaskQueue connected to Redis at {self.redis_url}")

    async def disconnect(self):
        """Close Redis connection."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        if self.redis:
            await self.redis.close()
            logger.info("TaskQueue disconnected from Redis")

    def register_handler(self, task_type: str, handler: Callable):
        """
        Register an async handler function for a task type.

        Args:
            task_type: The type of task (e.g., 'availability', 'ssl')
            handler: Async callable that processes the task
        """
        self._handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")

    async def enqueue(self, task: Task) -> str:
        """
        Add a task to the queue with deduplication.

        Args:
            task: Task instance to enqueue

        Returns:
            task_id of the enqueued task, or existing task_id if duplicate
        """
        dedup_key = f"{self.DEDUP_KEY}:{task.task_type}:{task.domain}"

        # Check for duplicate
        existing = await self.redis.get(dedup_key)
        if existing:
            logger.debug(
                f"Duplicate task skipped: {task.task_type} for {task.domain}"
            )
            return existing

        # Serialize and add to sorted set (priority as score)
        task_data = json.dumps(task.to_dict())
        score = task.priority * 1_000_000_000 + time.time()

        await self.redis.zadd(self.QUEUE_KEY, {task_data: score})

        # Set dedup key with TTL
        await self.redis.setex(dedup_key, self.dedup_ttl, task.task_id)

        # Update stats
        await self.redis.hincrby(self.STATS_KEY, 'enqueued', 1)

        logger.debug(
            f"Enqueued task {task.task_id}: "
            f"{task.task_type} for {task.domain} "
            f"(priority={task.priority})"
        )
        return task.task_id

    async def enqueue_check(
        self,
        check_type: str,
        domain: str,
        site_config: dict,
        priority: int = TaskPriority.MEDIUM,
    ) -> str:
        """
        Convenience method to enqueue a site check.

        Args:
            check_type: Type of check (availability, ssl, ui, etc.)
            domain: Domain to check
            site_config: Full site configuration dict
            priority: Task priority level

        Returns:
            task_id
        """
        task = Task(
            task_type=check_type,
            domain=domain,
            payload={'site_config': site_config},
            priority=priority,
        )
        return await self.enqueue(task)

    async def dequeue(self) -> Optional[Task]:
        """
        Remove and return the highest-priority task from the queue.

        Returns:
            Task instance, or None if queue is empty
        """
        # Get the lowest-score (highest-priority) item
        items = await self.redis.zpopmin(self.QUEUE_KEY, count=1)
        if not items:
            return None

        task_data_str, score = items[0]
        task_data = json.loads(task_data_str)
        task = Task.from_dict(task_data)
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.now().isoformat()

        # Track in processing set
        await self.redis.hset(
            self.PROCESSING_KEY,
            task.task_id,
            json.dumps(task.to_dict())
        )

        return task

    async def complete_task(self, task: Task, result: Optional[dict] = None):
        """Mark a task as completed and store its result."""
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now().isoformat()
        task.result = result

        # Remove from processing
        await self.redis.hdel(self.PROCESSING_KEY, task.task_id)

        # Store result with TTL
        result_key = f"{self.RESULTS_KEY}:{task.task_id}"
        await self.redis.setex(
            result_key,
            self.result_ttl,
            json.dumps(task.to_dict())
        )

        # Update stats
        await self.redis.hincrby(self.STATS_KEY, 'completed', 1)

        logger.debug(f"Task {task.task_id} completed: {task.task_type} for {task.domain}")

    async def fail_task(self, task: Task, error: str):
        """
        Mark a task as failed. Re-enqueue if retries remain,
        otherwise move to dead letter queue.
        """
        task.retries += 1
        task.error = error

        # Remove from processing
        await self.redis.hdel(self.PROCESSING_KEY, task.task_id)

        if task.retries < task.max_retries:
            # Re-enqueue with lower priority
            task.status = TaskStatus.RETRYING
            task.priority = min(task.priority + 1, TaskPriority.LOW)
            task_data = json.dumps(task.to_dict())
            score = task.priority * 1_000_000_000 + time.time()
            await self.redis.zadd(self.QUEUE_KEY, {task_data: score})
            await self.redis.hincrby(self.STATS_KEY, 'retried', 1)
            logger.warning(
                f"Task {task.task_id} retry {task.retries}/{task.max_retries}: "
                f"{error}"
            )
        else:
            # Move to dead letter queue
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now().isoformat()
            await self.redis.lpush(
                self.DLQ_KEY, json.dumps(task.to_dict())
            )
            await self.redis.hincrby(self.STATS_KEY, 'failed', 1)
            logger.error(
                f"Task {task.task_id} permanently failed after "
                f"{task.max_retries} retries: {error}"
            )

    async def get_task_result(self, task_id: str) -> Optional[dict]:
        """Retrieve the result of a completed task."""
        result_key = f"{self.RESULTS_KEY}:{task_id}"
        data = await self.redis.get(result_key)
        if data:
            return json.loads(data)
        return None

    async def get_queue_stats(self) -> dict:
        """Get queue statistics."""
        queue_size = await self.redis.zcard(self.QUEUE_KEY)
        processing_size = await self.redis.hlen(self.PROCESSING_KEY)
        dlq_size = await self.redis.llen(self.DLQ_KEY)
        stats = await self.redis.hgetall(self.STATS_KEY)

        return {
            'queue_size': queue_size,
            'processing': processing_size,
            'dead_letter_queue': dlq_size,
            'total_enqueued': int(stats.get('enqueued', 0)),
            'total_completed': int(stats.get('completed', 0)),
            'total_failed': int(stats.get('failed', 0)),
            'total_retried': int(stats.get('retried', 0)),
        }

    async def _worker(self, worker_id: int):
        """
        Worker coroutine that continuously processes tasks from the queue.
        """
        logger.info(f"Worker-{worker_id} started")
        while self._running:
            try:
                task = await self.dequeue()
                if task is None:
                    await asyncio.sleep(0.5)
                    continue

                handler = self._handlers.get(task.task_type)
                if handler is None:
                    await self.fail_task(
                        task,
                        f"No handler registered for task type: {task.task_type}"
                    )
                    continue

                try:
                    result = await handler(task.payload.get('site_config', {}))
                    await self.complete_task(task, result)
                except Exception as e:
                    await self.fail_task(task, str(e))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker-{worker_id} error: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info(f"Worker-{worker_id} stopped")

    async def start_workers(self, num_workers: Optional[int] = None):
        """
        Start worker coroutines to process tasks.

        Args:
            num_workers: Number of workers (defaults to max_workers)
        """
        num = num_workers or self.max_workers
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(num)
        ]
        logger.info(f"Started {num} task queue workers")

    async def stop_workers(self):
        """Stop all worker coroutines gracefully."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        logger.info("All task queue workers stopped")

    async def flush_queue(self):
        """Clear all pending tasks from the queue (use with caution)."""
        await self.redis.delete(self.QUEUE_KEY)
        logger.warning("Task queue flushed")

    async def flush_dlq(self):
        """Clear the dead letter queue."""
        await self.redis.delete(self.DLQ_KEY)
        logger.info("Dead letter queue flushed")

    async def requeue_dlq(self, limit: int = 100):
        """
        Move tasks from the dead letter queue back to the main queue
        for reprocessing.
        """
        count = 0
        while count < limit:
            data = await self.redis.rpop(self.DLQ_KEY)
            if not data:
                break
            task_data = json.loads(data)
            task = Task.from_dict(task_data)
            task.status = TaskStatus.PENDING
            task.retries = 0
            task.error = None
            await self.enqueue(task)
            count += 1

        logger.info(f"Re-queued {count} tasks from dead letter queue")
        return count
