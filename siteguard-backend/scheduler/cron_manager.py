"""
APScheduler-based cron manager for scheduling site checks at configured intervals.
Manages periodic jobs for availability, SSL, UI, sitemap, and security checks.
"""
import logging
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import (
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
)

logger = logging.getLogger(__name__)


class CronManager:
    """
    Manages scheduled monitoring jobs using APScheduler.
    Supports dynamic addition/removal of jobs and provides
    execution statistics.
    """

    def __init__(self, timezone: str = 'Europe/Moscow'):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.job_stats: Dict[str, dict] = {}
        self._setup_event_listeners()

    def _setup_event_listeners(self):
        """Set up listeners for job execution events."""
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )
        self.scheduler.add_listener(
            self._on_job_missed,
            EVENT_JOB_MISSED
        )

    def _on_job_executed(self, event):
        """Handle successful job execution."""
        job_id = event.job_id
        if job_id not in self.job_stats:
            self.job_stats[job_id] = {
                'executions': 0, 'errors': 0, 'missed': 0
            }
        self.job_stats[job_id]['executions'] += 1
        self.job_stats[job_id]['last_run'] = datetime.now().isoformat()
        self.job_stats[job_id]['last_status'] = 'success'
        logger.debug(f"Job {job_id} executed successfully")

    def _on_job_error(self, event):
        """Handle job execution error."""
        job_id = event.job_id
        if job_id not in self.job_stats:
            self.job_stats[job_id] = {
                'executions': 0, 'errors': 0, 'missed': 0
            }
        self.job_stats[job_id]['errors'] += 1
        self.job_stats[job_id]['last_run'] = datetime.now().isoformat()
        self.job_stats[job_id]['last_status'] = 'error'
        self.job_stats[job_id]['last_error'] = str(event.exception)
        logger.error(
            f"Job {job_id} failed: {event.exception}",
            exc_info=event.traceback
        )

    def _on_job_missed(self, event):
        """Handle missed job execution."""
        job_id = event.job_id
        if job_id not in self.job_stats:
            self.job_stats[job_id] = {
                'executions': 0, 'errors': 0, 'missed': 0
            }
        self.job_stats[job_id]['missed'] += 1
        logger.warning(f"Job {job_id} missed its scheduled run")

    def schedule_site_checks(
        self,
        site_config: dict,
        check_handlers: Dict[str, Callable]
    ):
        """
        Schedule all configured checks for a single site.

        Args:
            site_config: Site configuration dict with domain, checks, intervals
            check_handlers: Dict mapping check type to async handler function
        """
        domain = site_config['domain']
        interval = site_config.get('check_interval', 300)
        checks = site_config.get('checks', {})

        # Availability check at the configured interval
        if checks.get('availability', True) and 'availability' in check_handlers:
            self.add_interval_job(
                job_id=f"avail_{domain}",
                func=check_handlers['availability'],
                args=[site_config],
                seconds=interval,
                name=f"Availability: {domain}",
            )

        # SSL check every hour
        if checks.get('ssl', True) and 'ssl' in check_handlers:
            self.add_interval_job(
                job_id=f"ssl_{domain}",
                func=check_handlers['ssl'],
                args=[site_config],
                hours=1,
                name=f"SSL: {domain}",
            )

        # UI tests every 15 minutes
        if checks.get('ui_tests', True) and 'ui' in check_handlers:
            self.add_interval_job(
                job_id=f"ui_{domain}",
                func=check_handlers['ui'],
                args=[site_config],
                minutes=15,
                name=f"UI: {domain}",
            )

        # Sitemap crawl every 30 minutes
        if 'sitemap' in check_handlers:
            self.add_interval_job(
                job_id=f"sitemap_{domain}",
                func=check_handlers['sitemap'],
                args=[site_config],
                minutes=30,
                name=f"Sitemap: {domain}",
            )

        # Security scan every 2 hours
        if checks.get('security_scan', True) and 'security' in check_handlers:
            self.add_interval_job(
                job_id=f"security_{domain}",
                func=check_handlers['security'],
                args=[site_config],
                hours=2,
                name=f"Security: {domain}",
            )

        # Malware scan every 4 hours
        if checks.get('malware_scan', True) and 'malware' in check_handlers:
            self.add_interval_job(
                job_id=f"malware_{domain}",
                func=check_handlers['malware'],
                args=[site_config],
                hours=4,
                name=f"Malware: {domain}",
            )

        logger.info(
            f"Scheduled checks for {domain} "
            f"(interval={interval}s, checks={list(checks.keys())})"
        )

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        args: Optional[List] = None,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        name: Optional[str] = None,
        max_instances: int = 1,
        coalesce: bool = True,
    ):
        """Add an interval-triggered job."""
        trigger_kwargs = {}
        if seconds:
            trigger_kwargs['seconds'] = seconds
        if minutes:
            trigger_kwargs['minutes'] = minutes
        if hours:
            trigger_kwargs['hours'] = hours

        self.scheduler.add_job(
            func,
            trigger=IntervalTrigger(**trigger_kwargs),
            args=args or [],
            id=job_id,
            name=name or job_id,
            max_instances=max_instances,
            coalesce=coalesce,
            replace_existing=True,
        )

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        hour: int,
        minute: int = 0,
        args: Optional[List] = None,
        name: Optional[str] = None,
        max_instances: int = 1,
    ):
        """Add a cron-triggered job (runs daily at specified time)."""
        self.scheduler.add_job(
            func,
            trigger=CronTrigger(hour=hour, minute=minute),
            args=args or [],
            id=job_id,
            name=name or job_id,
            max_instances=max_instances,
            replace_existing=True,
        )

    def remove_site_jobs(self, domain: str):
        """Remove all scheduled jobs for a given domain."""
        prefixes = ['avail_', 'ssl_', 'ui_', 'sitemap_', 'security_', 'malware_']
        for prefix in prefixes:
            job_id = f"{prefix}{domain}"
            try:
                self.scheduler.remove_job(job_id)
                logger.info(f"Removed job: {job_id}")
            except Exception:
                pass

    def get_all_jobs(self) -> List[dict]:
        """Get information about all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            stats = self.job_stats.get(job.id, {})
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': (
                    job.next_run_time.isoformat()
                    if job.next_run_time else None
                ),
                'trigger': str(job.trigger),
                'executions': stats.get('executions', 0),
                'errors': stats.get('errors', 0),
                'missed': stats.get('missed', 0),
                'last_run': stats.get('last_run'),
                'last_status': stats.get('last_status'),
            })
        return jobs

    def get_job_stats(self) -> Dict[str, dict]:
        """Get execution statistics for all jobs."""
        return dict(self.job_stats)

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("CronManager scheduler started")

    def shutdown(self, wait: bool = False):
        """Shut down the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("CronManager scheduler shut down")

    def pause(self):
        """Pause all scheduled jobs."""
        self.scheduler.pause()
        logger.info("CronManager paused")

    def resume(self):
        """Resume all paused jobs."""
        self.scheduler.resume()
        logger.info("CronManager resumed")
