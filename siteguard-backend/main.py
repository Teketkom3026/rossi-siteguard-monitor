"""
SiteGuard Monitor — Main Orchestrator
Coordinates all monitoring checkers, processes results, and sends notifications.
"""
import asyncio
import yaml
import logging
from datetime import datetime, time
from typing import Dict, List, Optional
from pathlib import Path

from checkers.availability import AvailabilityChecker
from checkers.ssl_checker import SSLChecker
from checkers.ui_tester import UITester
from checkers.sitemap_crawler import SitemapCrawler
from checkers.security_scanner import SecurityScanner
from checkers.malware_detector import MalwareDetector
from notifications import NotificationManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DashboardData:
    """In-memory storage for dashboard data"""
    def __init__(self):
        self.sites_status: Dict[str, dict] = {}
        self.last_updated: Optional[datetime] = None
        self.check_history: Dict[str, list] = {}

    def update_site(self, domain: str, status: dict):
        self.sites_status[domain] = status
        self.last_updated = datetime.now()
        if domain not in self.check_history:
            self.check_history[domain] = []
        self.check_history[domain].append({
            'timestamp': datetime.now().isoformat(),
            'status': status.get('overall_severity', 'unknown')
        })
        # Keep last 100 checks per site
        if len(self.check_history[domain]) > 100:
            self.check_history[domain] = self.check_history[domain][-100:]


dashboard_data = DashboardData()


class MonitoringOrchestrator:
    """Main monitoring orchestrator"""

    def __init__(self, config_path: str = "config/sites.yaml"):
        self.config_path = config_path
        self.sites_config = []
        self.load_config()

        # Initialize checkers
        self.availability_checker = AvailabilityChecker(timeout=30, retries=3)
        self.ssl_checker = SSLChecker(warning_days=30, critical_days=7)
        self.ui_tester = UITester()
        self.sitemap_crawler = SitemapCrawler()
        self.security_scanner = SecurityScanner()
        self.malware_detector = MalwareDetector()

        # Initialize notification manager
        self.notification_manager = NotificationManager()

        # Track previous states for recovery detection
        self.previous_states: Dict[str, str] = {}

    def load_config(self):
        """Load sites configuration from YAML"""
        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.sites_config = config.get('sites', [])
                logger.info(f"Loaded {len(self.sites_config)} sites from config")
        else:
            logger.warning(f"Config file not found: {self.config_path}")
            self.sites_config = []

    async def check_site(self, site_config: dict) -> dict:
        """Run all enabled checks for a single site"""
        domain = site_config['domain']
        checks = site_config.get('checks', {})
        critical_pages = site_config.get('critical_pages', [{'url': '/', 'name': 'Main'}])
        ui_elements = site_config.get('ui_elements', [])

        logger.info(f"Starting checks for {domain}")
        results = {
            'domain': domain,
            'name': site_config.get('name', domain),
            'timestamp': datetime.now().isoformat(),
            'priority': site_config.get('priority', 'medium'),
        }

        tasks = {}

        # Availability check (always enabled)
        if checks.get('availability', True):
            tasks['availability'] = self.availability_checker.full_check(
                domain, critical_pages
            )

        # SSL check
        if checks.get('ssl', True):
            tasks['ssl'] = self.ssl_checker.check_ssl(domain)

        # UI tests
        if checks.get('ui_tests', False) and ui_elements:
            tasks['ui'] = self.ui_tester.test_elements(
                f"https://{domain}", ui_elements
            )

        # Security scan
        if checks.get('security_scan', False):
            tasks['security'] = self.security_scanner.full_scan(domain)

        # Malware scan
        if checks.get('malware_scan', False):
            tasks['malware'] = self.malware_detector.full_scan(domain)

        # Run all checks in parallel
        if tasks:
            task_results = await asyncio.gather(
                *tasks.values(),
                return_exceptions=True
            )

            for key, result in zip(tasks.keys(), task_results):
                if isinstance(result, Exception):
                    logger.error(f"Check {key} failed for {domain}: {result}")
                    results[key] = {'error': str(result)}
                else:
                    if hasattr(result, '__dict__'):
                        results[key] = result.__dict__
                    elif isinstance(result, dict):
                        results[key] = result
                    else:
                        results[key] = {'data': str(result)}

        # Sitemap crawling (run separately, can be slow)
        try:
            sitemap_result = await self.sitemap_crawler.crawl(domain)
            if hasattr(sitemap_result, '__dict__'):
                results['sitemap'] = sitemap_result.__dict__
            elif isinstance(sitemap_result, dict):
                results['sitemap'] = sitemap_result
        except Exception as e:
            logger.error(f"Sitemap crawl failed for {domain}: {e}")

        return results

    def process_results(self, domain: str, results: dict) -> dict:
        """Process check results and determine overall severity"""
        issues = []
        overall_severity = 'ok'

        # Process availability
        avail = results.get('availability', {})
        if isinstance(avail, dict):
            results['is_available'] = avail.get('is_available', False)
            results['response_time_ms'] = avail.get('response_time_ms')
            results['https_status'] = avail.get('https_status')
            results['http_status'] = avail.get('http_status')

            if not avail.get('is_available', False):
                issues.append({
                    'type': 'availability',
                    'severity': 'critical',
                    'description': f"Site {domain} is down",
                    'details': avail.get('error_message', 'Unknown error')
                })
                overall_severity = 'critical'
            elif avail.get('response_time_ms', 0) > 5000:
                issues.append({
                    'type': 'availability',
                    'severity': 'medium',
                    'description': f"Slow response: {avail.get('response_time_ms')}ms"
                })
                if overall_severity not in ('critical', 'high'):
                    overall_severity = 'medium'

        # Process SSL
        ssl = results.get('ssl', {})
        if isinstance(ssl, dict):
            results['ssl_days_left'] = ssl.get('days_until_expiry')
            if ssl.get('is_expired'):
                issues.append({
                    'type': 'ssl',
                    'severity': 'critical',
                    'description': f"SSL certificate expired for {domain}"
                })
                overall_severity = 'critical'
            elif ssl.get('is_expiring_soon'):
                days = ssl.get('days_until_expiry', 0)
                severity = 'high' if days <= 7 else 'medium'
                issues.append({
                    'type': 'ssl',
                    'severity': severity,
                    'description': f"SSL expires in {days} days"
                })
                if severity == 'high' and overall_severity not in ('critical',):
                    overall_severity = 'high'
                elif severity == 'medium' and overall_severity == 'ok':
                    overall_severity = 'medium'
            elif not ssl.get('has_ssl') and 'error' not in ssl:
                issues.append({
                    'type': 'ssl',
                    'severity': 'high',
                    'description': f"No SSL certificate for {domain}"
                })
                if overall_severity not in ('critical',):
                    overall_severity = 'high'

        # Process security
        security = results.get('security', {})
        if isinstance(security, dict):
            score = security.get('security_score', security.get('score', 0))
            results['security_score'] = score
            if score < 40:
                issues.append({
                    'type': 'security',
                    'severity': 'high',
                    'description': f"Low security score: {score}/100"
                })
                if overall_severity not in ('critical',):
                    overall_severity = 'high'
            elif score < 70:
                issues.append({
                    'type': 'security',
                    'severity': 'medium',
                    'description': f"Security score: {score}/100"
                })
                if overall_severity == 'ok':
                    overall_severity = 'medium'

        # Process malware
        malware = results.get('malware', {})
        if isinstance(malware, dict):
            threats = malware.get('threats', [])
            results['malware_detected'] = len(threats) > 0
            if threats:
                issues.append({
                    'type': 'malware',
                    'severity': 'critical',
                    'description': f"Malware detected: {len(threats)} threat(s)",
                    'details': ', '.join(t.get('name', 'Unknown') for t in threats[:5])
                })
                overall_severity = 'critical'

        # Process UI test results
        ui = results.get('ui', {})
        if isinstance(ui, dict):
            total = ui.get('total_elements', 0)
            ok = ui.get('passed_elements', 0)
            results['ui_total_count'] = total
            results['ui_ok_count'] = ok
            failed = ui.get('failed_elements', [])
            if failed:
                critical_failed = [
                    e for e in failed
                    if e.get('critical', False)
                ]
                if critical_failed:
                    issues.append({
                        'type': 'ui',
                        'severity': 'high',
                        'description': f"{len(critical_failed)} critical UI element(s) failed",
                        'details': ', '.join(e.get('name', 'Unknown') for e in critical_failed)
                    })
                    if overall_severity not in ('critical',):
                        overall_severity = 'high'

        results['issues'] = issues
        results['overall_severity'] = overall_severity

        return results

    def determine_severity(self, results: dict) -> str:
        """Determine the overall severity from processed results"""
        return results.get('overall_severity', 'unknown')

    async def send_alerts(self, domain: str, results: dict):
        """Send alerts based on severity changes"""
        current_severity = results.get('overall_severity', 'ok')
        previous_severity = self.previous_states.get(domain, 'ok')

        # Send recovery notification
        if previous_severity in ('critical', 'high') and current_severity == 'ok':
            await self.notification_manager.send_recovery(
                domain=domain,
                previous_severity=previous_severity
            )

        # Send alert for new issues
        for issue in results.get('issues', []):
            await self.notification_manager.send_alert(
                domain=domain,
                alert_type=issue['type'],
                severity=issue['severity'],
                description=issue['description'],
                details=issue.get('details', '')
            )

        self.previous_states[domain] = current_severity

    async def send_daily_report(self):
        """Generate and send daily report"""
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
            'security_scores': security_summary
        }

        await self.notification_manager.send_daily_report(report_data)
        logger.info("Daily report sent")

    async def run_checks_cycle(self):
        """Run one full cycle of checks for all sites"""
        logger.info(f"Starting check cycle for {len(self.sites_config)} sites")

        for site_config in self.sites_config:
            domain = site_config['domain']
            try:
                # Run checks
                results = await self.check_site(site_config)

                # Process results
                processed = self.process_results(domain, results)

                # Update dashboard data
                dashboard_data.update_site(domain, processed)

                # Send alerts
                await self.send_alerts(domain, processed)

                severity = processed.get('overall_severity', 'unknown')
                logger.info(f"Check complete for {domain}: {severity}")

            except Exception as e:
                logger.error(f"Error checking {domain}: {e}", exc_info=True)

            # Small delay between sites to avoid overload
            await asyncio.sleep(2)

        logger.info("Check cycle complete")

    async def run(self):
        """Main run loop"""
        logger.info("SiteGuard Monitor Orchestrator starting...")
        logger.info(f"Monitoring {len(self.sites_config)} sites")

        # Schedule daily report at 09:00
        daily_report_sent_today = False

        while True:
            try:
                # Run checks
                await self.run_checks_cycle()

                # Check if it's time for daily report (09:00)
                now = datetime.now()
                if now.hour == 9 and not daily_report_sent_today:
                    await self.send_daily_report()
                    daily_report_sent_today = True
                elif now.hour != 9:
                    daily_report_sent_today = False

                # Wait for next cycle (default: 5 minutes)
                min_interval = min(
                    (s.get('check_interval', 300) for s in self.sites_config),
                    default=300
                )
                logger.info(f"Next check in {min_interval} seconds")
                await asyncio.sleep(min_interval)

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retrying


async def main():
    orchestrator = MonitoringOrchestrator()
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
