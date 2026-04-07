"""
Main monitoring orchestrator - runs all checks, coordinates components,
saves results, and manages notifications.
"""
import asyncio
import yaml
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# Checker modules
from checkers.availability import AvailabilityChecker
from checkers.ssl_checker import SSLChecker
from checkers.ui_tester import UITester
from checkers.sitemap_crawler import SitemapCrawler
from checkers.security_scanner import SecurityScanner

# Notifications
from notifications import NotificationManager

# Dashboard
from dashboard.app import dashboard_data, run_dashboard

# Database
from database.models import Database

# Scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Orchestrator')


class MonitoringOrchestrator:
    """Main orchestration class for the site monitoring system."""

    def __init__(self, config_path: str = 'config/sites.yaml'):
        # Load configuration
        self.config = self._load_config(config_path)
        self.alerts_config = self._load_config('config/alerts.yaml')

        # Initialize checker modules
        self.availability_checker = AvailabilityChecker(
            timeout=30, retries=3
        )
        self.ssl_checker = SSLChecker(
            warning_days=30, critical_days=7
        )
        self.ui_tester = UITester(
            headless=True,
            screenshot_dir='./screenshots'
        )
        self.sitemap_crawler = SitemapCrawler(
            max_concurrent=10, timeout=15
        )
        self.security_scanner = SecurityScanner(
            virustotal_api_key=self.alerts_config.get(
                'virustotal_api_key'
            )
        )

        # Initialize notifications
        self.notifier = NotificationManager(self.alerts_config)

        # Initialize database
        self.db = Database(
            connection_string=self.alerts_config.get(
                'database_url',
                'postgresql://monitor:monitor@localhost:5432/monitoring'
            )
        )

        # Scheduler
        self.scheduler = AsyncIOScheduler()

        # Status cache for tracking changes
        self._previous_status: Dict[str, dict] = {}

        # Running flag
        self._running = False

        # Create required directories
        Path('logs').mkdir(exist_ok=True)
        Path('screenshots').mkdir(exist_ok=True)

    def _load_config(self, path: str) -> dict:
        """Load YAML configuration file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Config file not found: {path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Config parse error {path}: {e}")
            return {}

    async def initialize(self):
        """Initialize all components."""
        logger.info("=" * 60)
        logger.info("Initializing monitoring system...")
        logger.info("=" * 60)

        # Initialize database
        await self.db.initialize()
        logger.info("Database initialized")

        # Initialize headless browser for UI tests
        await self.ui_tester.init_browser()
        logger.info("Headless browser started")

        # Set up scheduler
        self._setup_scheduler()
        logger.info("Scheduler configured")

        sites = self.config.get('sites', [])
        logger.info(f"Loaded {len(sites)} sites for monitoring")
        for site in sites:
            logger.info(
                f"  -> {site['domain']} "
                f"(interval: {site.get('check_interval', 300)}s, "
                f"priority: {site.get('priority', 'medium')})"
            )

    def _setup_scheduler(self):
        """Configure check schedules for all sites."""
        sites = self.config.get('sites', [])

        for site in sites:
            domain = site['domain']
            interval = site.get('check_interval', 300)
            checks = site.get('checks', {})

            # Availability check at the main interval
            if checks.get('availability', True):
                self.scheduler.add_job(
                    self.check_availability,
                    trigger=IntervalTrigger(seconds=interval),
                    args=[site],
                    id=f"avail_{domain}",
                    name=f"Availability: {domain}",
                    max_instances=1,
                    coalesce=True
                )

            # SSL check every hour
            if checks.get('ssl', True):
                self.scheduler.add_job(
                    self.check_ssl,
                    trigger=IntervalTrigger(hours=1),
                    args=[site],
                    id=f"ssl_{domain}",
                    name=f"SSL: {domain}",
                    max_instances=1
                )

            # UI tests every 15 minutes
            if checks.get('ui_tests', True):
                self.scheduler.add_job(
                    self.check_ui,
                    trigger=IntervalTrigger(minutes=15),
                    args=[site],
                    id=f"ui_{domain}",
                    name=f"UI: {domain}",
                    max_instances=1
                )

            # Sitemap crawl every 30 minutes
            self.scheduler.add_job(
                self.check_sitemap,
                trigger=IntervalTrigger(minutes=30),
                args=[site],
                id=f"sitemap_{domain}",
                name=f"Sitemap: {domain}",
                max_instances=1
            )

            # Security scan every 2 hours
            if checks.get('security_scan', True):
                self.scheduler.add_job(
                    self.check_security,
                    trigger=IntervalTrigger(hours=2),
                    args=[site],
                    id=f"security_{domain}",
                    name=f"Security: {domain}",
                    max_instances=1
                )

            # Malware scan every 4 hours
            if checks.get('malware_scan', True):
                self.scheduler.add_job(
                    self.check_malware,
                    trigger=IntervalTrigger(hours=4),
                    args=[site],
                    id=f"malware_{domain}",
                    name=f"Malware: {domain}",
                    max_instances=1
                )

        # Daily report at 09:00
        self.scheduler.add_job(
            self.send_daily_report,
            trigger=CronTrigger(hour=9, minute=0),
            id="daily_report",
            name="Daily Report",
            max_instances=1
        )

        # Data cleanup at 03:00
        self.scheduler.add_job(
            self.cleanup_old_data,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup",
            name="Data Cleanup",
            max_instances=1
        )

    # ===============================
    # MAIN CHECKS
    # ===============================

    async def check_site(self, site_config: dict):
        """
        Run all enabled checks for a single site.
        This is the main entry point for checking a site.
        """
        domain = site_config['domain']
        checks = site_config.get('checks', {})
        results = {}

        logger.info(f"Running full check for: {domain}")

        try:
            tasks = []
            if checks.get('availability', True):
                tasks.append(('availability', self.check_availability(site_config)))
            if checks.get('ssl', True):
                tasks.append(('ssl', self.check_ssl(site_config)))

            # Run availability and SSL in parallel
            for name, task in tasks:
                try:
                    await task
                    results[name] = 'ok'
                except Exception as e:
                    results[name] = f'error: {e}'
                    logger.error(f"Check {name} failed for {domain}: {e}")

            # Run sequential checks
            if checks.get('ui_tests', True):
                try:
                    await self.check_ui(site_config)
                    results['ui'] = 'ok'
                except Exception as e:
                    results['ui'] = f'error: {e}'

            if checks.get('security_scan', True):
                try:
                    await self.check_security(site_config)
                    results['security'] = 'ok'
                except Exception as e:
                    results['security'] = f'error: {e}'

        except Exception as e:
            logger.error(f"Full check failed for {domain}: {e}", exc_info=True)

        return results

    async def check_availability(self, site_config: dict):
        """Check site availability."""
        domain = site_config['domain']
        pages = site_config.get('critical_pages', [])

        try:
            logger.info(f"Checking availability: {domain}")
            result = await self.availability_checker.full_check(
                domain, pages
            )

            # Save to database
            await self.db.save_availability_result(result)

            # Determine severity
            severity = 'ok'
            issues = []

            if not result.is_available:
                severity = 'critical'
                issues.append({
                    'type': 'site_unavailable',
                    'severity': 'critical',
                    'description': (
                        f"Site {domain} is unavailable: "
                        f"{result.error_message}"
                    )
                })
            elif not result.dns_resolved:
                severity = 'critical'
                issues.append({
                    'type': 'dns_failure',
                    'severity': 'critical',
                    'description': f"DNS not resolving: {domain}"
                })
            elif result.response_time_ms and result.response_time_ms > 5000:
                severity = 'high'
                issues.append({
                    'type': 'slow_response',
                    'severity': 'high',
                    'description': (
                        f"Slow response: "
                        f"{result.response_time_ms}ms"
                    )
                })
            elif result.response_time_ms and result.response_time_ms > 3000:
                severity = 'medium'
                issues.append({
                    'type': 'slow_response',
                    'severity': 'medium',
                    'description': (
                        f"Degraded response: "
                        f"{result.response_time_ms}ms"
                    )
                })

            # Check page statuses
            for page_name, page_status in result.pages_status.items():
                if not page_status.get('is_ok'):
                    page_severity = 'high'
                    if severity in ('ok', 'low', 'medium'):
                        severity = page_severity
                    issues.append({
                        'type': 'page_error',
                        'severity': page_severity,
                        'description': (
                            f"Page '{page_name}' "
                            f"returned error: "
                            f"{page_status.get('status', 'N/A')} - "
                            f"{page_status.get('error', '')}"
                        )
                    })

            # Update dashboard
            self._update_dashboard_status(domain, site_config, {
                'is_available': result.is_available,
                'http_status': result.http_status,
                'https_status': result.https_status,
                'response_time_ms': result.response_time_ms,
                'dns_resolved': result.dns_resolved,
                'dns_ip': result.dns_ip,
                'ping_ok': result.ping_ok,
                'overall_severity': severity,
                'issues': issues,
                'pages_status': result.pages_status
            })

            # Send alerts if needed
            await self._process_alerts(domain, severity, issues)

            logger.info(
                f"Availability {domain}: "
                f"available={result.is_available}, "
                f"response={result.response_time_ms}ms, "
                f"severity={severity}"
            )

        except Exception as e:
            logger.error(
                f"Error checking availability {domain}: {e}",
                exc_info=True
            )
            await self.notifier.send_alert(
                domain, 'Monitoring error', 'high',
                f"Availability check error: {str(e)}"
            )

    async def check_ssl(self, site_config: dict):
        """Check SSL certificate."""
        domain = site_config['domain']

        try:
            logger.info(f"Checking SSL: {domain}")
            result = await self.ssl_checker.check_ssl(domain)

            await self.db.save_ssl_result(result)

            ssl_severity = 'ok'
            ssl_issues = []

            if not result.has_ssl:
                ssl_severity = 'critical'
                ssl_issues.append({
                    'type': 'ssl_missing',
                    'severity': 'critical',
                    'description': (
                        f"SSL certificate missing on {domain}"
                    )
                })
            elif result.is_expired:
                ssl_severity = 'critical'
                ssl_issues.append({
                    'type': 'ssl_expired',
                    'severity': 'critical',
                    'description': (
                        f"SSL certificate expired on {domain}"
                    )
                })
            elif result.is_expiring_soon:
                days = result.days_until_expiry
                if days <= 7:
                    ssl_severity = 'high'
                else:
                    ssl_severity = 'medium'
                ssl_issues.append({
                    'type': 'ssl_expiring',
                    'severity': ssl_severity,
                    'description': (
                        f"SSL certificate for {domain} "
                        f"expires in {days} days"
                    )
                })
            elif not result.chain_valid:
                ssl_severity = 'high'
                ssl_issues.append({
                    'type': 'ssl_chain_invalid',
                    'severity': 'high',
                    'description': (
                        f"Invalid SSL certificate chain "
                        f"on {domain}"
                    )
                })

            # Update dashboard
            current = dashboard_data.sites_status.get(domain, {})
            current['ssl'] = {
                'has_ssl': result.has_ssl,
                'is_valid': result.is_valid,
                'issuer': result.issuer,
                'valid_until': (
                    result.valid_until.isoformat()
                    if result.valid_until else None
                ),
                'days_until_expiry': result.days_until_expiry,
                'is_expiring_soon': result.is_expiring_soon,
                'is_expired': result.is_expired,
                'chain_valid': result.chain_valid,
                'protocol_version': result.protocol_version,
                'error_message': result.error_message
            }
            current['ssl_days_left'] = result.days_until_expiry

            # Merge issues
            existing_issues = current.get('issues', [])
            existing_issues = [
                i for i in existing_issues
                if not i['type'].startswith('ssl_')
            ]
            existing_issues.extend(ssl_issues)
            current['issues'] = existing_issues
            current['overall_severity'] = self._calc_overall_severity(
                existing_issues
            )

            dashboard_data.update_site_status(domain, current)

            await self._process_alerts(domain, ssl_severity, ssl_issues)

            logger.info(
                f"SSL {domain}: valid={result.is_valid}, "
                f"expires_in={result.days_until_expiry} days"
            )

        except Exception as e:
            logger.error(
                f"Error checking SSL {domain}: {e}",
                exc_info=True
            )

    async def check_ui(self, site_config: dict):
        """Test UI elements on the site."""
        domain = site_config['domain']
        elements = site_config.get('ui_elements', [])
        pages = site_config.get('critical_pages', [])

        if not elements and not pages:
            return

        try:
            logger.info(f"UI tests: {domain}")
            ui_issues = []

            # Test elements on main page
            result = None
            if elements:
                result = await self.ui_tester.test_page(
                    domain, '/', elements
                )
                await self.db.save_ui_result(result)

                for elem in result.elements:
                    if not elem.action_success:
                        ui_issues.append({
                            'type': 'ui_element_broken',
                            'severity': 'high',
                            'description': (
                                f"UI element '{elem.name}' "
                                f"is broken: "
                                f"{elem.error_message or 'action failed'}"
                            )
                        })

                if result.console_errors:
                    ui_issues.append({
                        'type': 'js_console_errors',
                        'severity': 'medium',
                        'description': (
                            f"JavaScript console errors: "
                            f"{len(result.console_errors)} found"
                        )
                    })

            # Test catalog flow
            catalog_result = await self.ui_tester.test_catalog_flow(
                domain
            )
            if catalog_result.has_critical_issues:
                for elem in catalog_result.elements:
                    if not elem.action_success:
                        ui_issues.append({
                            'type': 'catalog_flow_broken',
                            'severity': 'critical',
                            'description': (
                                f"Purchase flow broken: "
                                f"'{elem.name}' - "
                                f"{elem.error_message or 'not working'}"
                            )
                        })

            # Update dashboard
            current = dashboard_data.sites_status.get(domain, {})
            all_elements = []
            if elements and result:
                all_elements.extend([
                    {
                        'name': e.name,
                        'action': e.action,
                        'action_success': e.action_success,
                        'error_message': e.error_message
                    } for e in result.elements
                ])
            all_elements.extend([
                {
                    'name': e.name,
                    'action': e.action,
                    'action_success': e.action_success,
                    'error_message': e.error_message
                } for e in catalog_result.elements
            ])
            current['ui_elements'] = all_elements

            # Merge issues
            existing_issues = current.get('issues', [])
            existing_issues = [
                i for i in existing_issues
                if not i['type'].startswith('ui_') and
                   not i['type'].startswith('catalog_') and
                   not i['type'].startswith('js_')
            ]
            existing_issues.extend(ui_issues)
            current['issues'] = existing_issues
            current['overall_severity'] = self._calc_overall_severity(
                existing_issues
            )

            dashboard_data.update_site_status(domain, current)

            ui_severity = self._calc_overall_severity(ui_issues)
            await self._process_alerts(domain, ui_severity, ui_issues)

            ok_count = sum(
                1 for e in all_elements if e['action_success']
            )
            total_count = len(all_elements)
            logger.info(
                f"UI {domain}: "
                f"{ok_count}/{total_count} elements OK"
            )

        except Exception as e:
            logger.error(
                f"Error in UI tests {domain}: {e}",
                exc_info=True
            )

    async def check_sitemap(self, site_config: dict):
        """Crawl site via sitemap."""
        domain = site_config['domain']

        try:
            logger.info(f"Sitemap crawl: {domain}")
            result = await self.sitemap_crawler.crawl(domain)

            await self.db.save_sitemap_result(result)

            # Update sitemap tree on dashboard
            dashboard_data.update_sitemap_tree(
                domain, result.tree_structure
            )

            # Issues for pages with errors
            sitemap_issues = []
            for path, page in result.pages.items():
                if not page.is_ok:
                    sitemap_issues.append({
                        'type': 'page_error',
                        'severity': 'medium',
                        'description': (
                            f"Page {path} unavailable: "
                            f"status {page.status_code} - "
                            f"{page.error_message or ''}"
                        )
                    })

            if sitemap_issues:
                current = dashboard_data.sites_status.get(domain, {})
                existing = current.get('issues', [])
                existing = [
                    i for i in existing
                    if i['type'] != 'page_error'
                ]
                existing.extend(sitemap_issues[:20])
                current['issues'] = existing
                current['overall_severity'] = self._calc_overall_severity(
                    existing
                )
                dashboard_data.update_site_status(domain, current)

            logger.info(
                f"Sitemap {domain}: "
                f"{result.pages_ok}/{result.total_pages} pages OK"
            )

        except Exception as e:
            logger.error(
                f"Error crawling sitemap {domain}: {e}",
                exc_info=True
            )

    async def check_security(self, site_config: dict):
        """Run security scan."""
        domain = site_config['domain']
        pages = [
            p.get('url', '/') for p in
            site_config.get('critical_pages', [{'url': '/'}])
        ]

        try:
            logger.info(f"Security scan: {domain}")
            result = await self.security_scanner.full_scan(
                domain, pages
            )

            await self.db.save_security_result(result)

            # Update dashboard
            current = dashboard_data.sites_status.get(domain, {})
            current['security_score'] = result.overall_score
            current['has_waf'] = result.has_waf
            current['waf_name'] = result.waf_name
            current['security_headers'] = result.security_headers
            current['threats'] = [
                {
                    'threat_type': t.threat_type,
                    'severity': t.severity,
                    'description': t.description,
                    'location': t.location,
                    'details': t.details,
                    'recommendation': t.recommendation
                } for t in result.threats
            ]

            sec_issues = [
                {
                    'type': f"security_{t.threat_type}",
                    'severity': t.severity,
                    'description': t.description
                }
                for t in result.threats
                if t.severity in ('critical', 'high')
            ]

            existing = current.get('issues', [])
            existing = [
                i for i in existing
                if not i['type'].startswith('security_')
            ]
            existing.extend(sec_issues)
            current['issues'] = existing
            current['overall_severity'] = self._calc_overall_severity(
                existing
            )

            dashboard_data.update_site_status(domain, current)

            # Notifications for critical/high threats
            for threat in result.threats:
                if threat.severity in ('critical', 'high'):
                    await self.notifier.send_alert(
                        domain=domain,
                        alert_type=f"Security: {threat.threat_type}",
                        severity=threat.severity,
                        description=threat.description,
                        details=threat.details,
                        recommendation=threat.recommendation
                    )
                    dashboard_data.add_alert({
                        'domain': domain,
                        'severity': threat.severity,
                        'description': threat.description
                    })

            logger.info(
                f"Security {domain}: "
                f"score={result.overall_score}/100, "
                f"threats={len(result.threats)}, "
                f"malware={'YES' if result.malware_detected else 'no'}"
            )

        except Exception as e:
            logger.error(
                f"Error in security scan {domain}: {e}",
                exc_info=True
            )

    async def check_malware(self, site_config: dict):
        """Extended malware scan."""
        domain = site_config['domain']

        try:
            logger.info(f"Malware scan: {domain}")

            # Get all pages from sitemap for deep scanning
            sitemap_result = await self.sitemap_crawler.crawl(domain)
            all_pages = list(sitemap_result.pages.keys())[:50]
            if not all_pages:
                all_pages = ['/']

            result = await self.security_scanner.full_scan(
                domain, all_pages
            )

            if result.malware_detected:
                logger.critical(
                    f"MALWARE DETECTED on {domain}!"
                )
                await self.notifier.send_alert(
                    domain=domain,
                    alert_type='Malware detected',
                    severity='critical',
                    description=(
                        f"Malware detected on {domain}!"
                    ),
                    details='\n'.join([
                        f"- [{t.severity}] {t.description}"
                        for t in result.threats
                        if t.threat_type in (
                            'malware_code', 'malware_script',
                            'hidden_iframe', 'cryptominer',
                            'webshell', 'malicious_redirect'
                        )
                    ]),
                    recommendation=(
                        "URGENT: Perform full site audit, "
                        "verify file integrity, "
                        "change all passwords"
                    )
                )

            logger.info(
                f"Malware scan {domain}: "
                f"pages_scanned={len(all_pages)}, "
                f"malware={'DETECTED' if result.malware_detected else 'clean'}"
            )

        except Exception as e:
            logger.error(
                f"Error in malware scan {domain}: {e}",
                exc_info=True
            )

    # ===============================
    # HELPER METHODS
    # ===============================

    def _calc_overall_severity(self, issues: List[dict]) -> str:
        """Calculate the overall severity from a list of issues."""
        if not issues:
            return 'ok'
        severity_order = {
            'critical': 0, 'high': 1, 'medium': 2, 'low': 3
        }
        min_order = 4
        for issue in issues:
            order = severity_order.get(issue.get('severity', 'low'), 3)
            if order < min_order:
                min_order = order
        reverse_map = {v: k for k, v in severity_order.items()}
        return reverse_map.get(min_order, 'ok')

    def _update_dashboard_status(
        self, domain: str, site_config: dict, data: dict
    ):
        """Update site status on the dashboard."""
        current = dashboard_data.sites_status.get(domain, {})
        current.update(data)
        current['name'] = site_config.get('name', domain)
        current['priority'] = site_config.get('priority', 'medium')

        issues = current.get('issues', [])
        if issues:
            critical = [
                i for i in issues
                if i['severity'] == 'critical'
            ]
            if critical:
                current['error_summary'] = critical[0]['description']
            else:
                current['error_summary'] = issues[0]['description']
        else:
            current['error_summary'] = None

        dashboard_data.update_site_status(domain, current)

    async def _process_alerts(
        self, domain: str, severity: str, issues: List[dict]
    ):
        """Process alerts - send notifications and record them."""
        if severity == 'ok':
            # Check if there were previous problems - send recovery
            prev = self._previous_status.get(domain, {})
            if prev.get('severity') in (
                'critical', 'high', 'medium'
            ):
                await self.notifier.send_recovery(
                    domain,
                    f"Site {domain} has recovered"
                )
                dashboard_data.add_alert({
                    'domain': domain,
                    'severity': 'info',
                    'description': 'Site has recovered and is operational'
                })
            self._previous_status[domain] = {'severity': 'ok'}
            return

        self._previous_status[domain] = {'severity': severity}

        for issue in issues:
            await self.notifier.send_alert(
                domain=domain,
                alert_type=issue['type'],
                severity=issue['severity'],
                description=issue['description']
            )
            dashboard_data.add_alert({
                'domain': domain,
                'severity': issue['severity'],
                'description': issue['description']
            })

    def process_results(self, domain: str, results: dict):
        """
        Process check results for a domain and update dashboard.

        Args:
            domain: The domain that was checked
            results: Dict of check_type -> result data
        """
        issues = []
        for check_type, result_data in results.items():
            if isinstance(result_data, str) and result_data.startswith('error'):
                issues.append({
                    'type': f'{check_type}_error',
                    'severity': 'high',
                    'description': f"{check_type} check failed: {result_data}"
                })

        severity = self._calc_overall_severity(issues)
        current = dashboard_data.sites_status.get(domain, {})
        current['issues'] = issues
        current['overall_severity'] = severity
        dashboard_data.update_site_status(domain, current)
        return severity

    def determine_severity(self, results: dict) -> str:
        """
        Determine overall severity from check results.

        Args:
            results: Dict of check_type -> result/status

        Returns:
            Severity string: 'critical', 'high', 'medium', 'low', or 'ok'
        """
        issues = []
        for check_type, result_data in results.items():
            if isinstance(result_data, str) and result_data.startswith('error'):
                issues.append({'severity': 'high'})
            elif isinstance(result_data, dict):
                if result_data.get('severity'):
                    issues.append({'severity': result_data['severity']})
        return self._calc_overall_severity(issues)

    async def send_daily_report(self):
        """Generate and send the daily report."""
        logger.info("Generating daily report...")

        sites = dashboard_data.sites_status
        total = len(sites)
        ok = sum(
            1 for s in sites.values()
            if s.get('overall_severity', 'ok') == 'ok'
        )
        with_issues = total - ok
        critical_count = sum(
            1 for s in sites.values()
            if s.get('overall_severity') == 'critical'
        )

        sites_status_report = {}
        for domain, status in sites.items():
            sites_status_report[domain] = {
                'is_ok': status.get('overall_severity', 'ok') == 'ok',
                'issues_count': len(status.get('issues', []))
            }

        expiring_ssl = []
        for domain, status in sites.items():
            ssl_days = status.get('ssl_days_left')
            if ssl_days is not None and ssl_days <= 30:
                expiring_ssl.append({
                    'domain': domain,
                    'days_left': ssl_days
                })

        security_summary = {}
        for domain, status in sites.items():
            score = status.get('security_score', 0)
            security_summary[domain] = score

        report_data = {
            'total_sites': total,
            'sites_ok': ok,
            'sites_with_issues': with_issues,
            'critical_issues': critical_count,
            'sites_status': sites_status_report,
            'expiring_ssl': sorted(
                expiring_ssl, key=lambda x: x['days_left']
            ),
            'security_summary': security_summary
        }

        await self.notifier.send_daily_report(report_data)

        logger.info(
            f"Daily report sent: "
            f"{ok}/{total} OK, "
            f"{with_issues} with issues"
        )

    async def cleanup_old_data(self):
        """Clean up old monitoring data."""
        try:
            days_to_keep = self.alerts_config.get(
                'data_retention_days', 90
            )
            cutoff = datetime.now() - timedelta(days=days_to_keep)
            deleted = await self.db.cleanup_old_records(cutoff)
            logger.info(
                f"Data cleanup: deleted {deleted} records "
                f"older than {days_to_keep} days"
            )
        except Exception as e:
            logger.error(f"Error cleaning up data: {e}")

    # ===============================
    # INITIAL CHECK RUN
    # ===============================

    async def run_initial_checks(self):
        """Run all checks on startup."""
        logger.info("Running initial checks...")
        sites = self.config.get('sites', [])

        for site in sites:
            domain = site['domain']
            logger.info(f"--- Initial check: {domain} ---")

            try:
                tasks = [
                    self.check_availability(site),
                    self.check_ssl(site),
                    self.check_sitemap(site),
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

                # UI tests after availability
                await self.check_ui(site)
                # Security after sitemap
                await self.check_security(site)

                logger.info(f"Initial check completed for {domain}")
            except Exception as e:
                logger.error(
                    f"Error in initial check {domain}: {e}",
                    exc_info=True
                )

            # Brief pause between sites
            await asyncio.sleep(2)

        logger.info("All initial checks completed")

    # ===============================
    # START AND STOP
    # ===============================

    async def start(self):
        """Start the monitoring system."""
        self._running = True

        # Initialize
        await self.initialize()

        # Initial checks
        await self.run_initial_checks()

        # Start scheduler
        self.scheduler.start()
        logger.info("Scheduler started")
        logger.info("=" * 60)
        logger.info("MONITORING SYSTEM RUNNING")
        logger.info("=" * 60)

        # Wait for shutdown
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def stop(self):
        """Stop the monitoring system."""
        logger.info("Stopping monitoring system...")
        self._running = False

        self.scheduler.shutdown(wait=False)
        await self.ui_tester.close_browser()
        await self.notifier.close()
        await self.db.close()

        logger.info("Monitoring system stopped")


# ===============================
# ENTRY POINT
# ===============================

async def main():
    """Main entry point."""
    orchestrator = MonitoringOrchestrator(
        config_path='config/sites.yaml'
    )

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Shutdown signal received...")
        asyncio.ensure_future(orchestrator.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Start dashboard in a separate thread
    import threading
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        kwargs={'host': '0.0.0.0', 'port': 5000, 'debug': False},
        daemon=True
    )
    dashboard_thread.start()
    logger.info("Dashboard running at http://0.0.0.0:5000")

    # Start monitoring
    await orchestrator.start()


if __name__ == '__main__':
    asyncio.run(main())
