"""
Database models for storing monitoring results.
PostgreSQL + asyncpg / SQLAlchemy async
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
import asyncpg
import json
import logging

logger = logging.getLogger(__name__)


class Database:
    """Async PostgreSQL database manager using asyncpg connection pool."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize connection pool and create tables."""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=2,
            max_size=10
        )
        await self._create_tables()
        logger.info("Database initialized")

    async def _create_tables(self):
        """Create all required tables and indexes."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                -- Availability check results
                CREATE TABLE IF NOT EXISTS availability_checks (
                    id BIGSERIAL PRIMARY KEY,
                    domain VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    is_available BOOLEAN NOT NULL,
                    http_status INTEGER,
                    https_status INTEGER,
                    response_time_ms FLOAT,
                    dns_resolved BOOLEAN,
                    dns_ip VARCHAR(45),
                    dns_resolve_time_ms FLOAT,
                    ping_ok BOOLEAN,
                    ping_time_ms FLOAT,
                    ssl_redirect BOOLEAN,
                    error_message TEXT,
                    pages_status JSONB
                );

                CREATE INDEX IF NOT EXISTS idx_avail_domain_ts
                    ON availability_checks (domain, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_avail_ts
                    ON availability_checks (timestamp DESC);

                -- SSL check results
                CREATE TABLE IF NOT EXISTS ssl_checks (
                    id BIGSERIAL PRIMARY KEY,
                    domain VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    has_ssl BOOLEAN NOT NULL,
                    is_valid BOOLEAN,
                    issuer VARCHAR(500),
                    subject VARCHAR(500),
                    valid_from TIMESTAMPTZ,
                    valid_until TIMESTAMPTZ,
                    days_until_expiry INTEGER,
                    is_expiring_soon BOOLEAN,
                    is_expired BOOLEAN,
                    protocol_version VARCHAR(50),
                    cipher_suite VARCHAR(200),
                    san_domains JSONB,
                    chain_valid BOOLEAN,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_ssl_domain_ts
                    ON ssl_checks (domain, timestamp DESC);

                -- UI test results
                CREATE TABLE IF NOT EXISTS ui_checks (
                    id BIGSERIAL PRIMARY KEY,
                    domain VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    page_url TEXT,
                    page_loaded BOOLEAN,
                    page_load_time_ms FLOAT,
                    elements JSONB,
                    has_critical_issues BOOLEAN,
                    screenshot_path TEXT,
                    console_errors JSONB,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_ui_domain_ts
                    ON ui_checks (domain, timestamp DESC);

                -- Sitemap crawl results
                CREATE TABLE IF NOT EXISTS sitemap_checks (
                    id BIGSERIAL PRIMARY KEY,
                    domain VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    sitemap_found BOOLEAN,
                    sitemap_url TEXT,
                    total_pages INTEGER,
                    pages_ok INTEGER,
                    pages_error INTEGER,
                    pages_detail JSONB,
                    tree_structure JSONB,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_sitemap_domain_ts
                    ON sitemap_checks (domain, timestamp DESC);

                -- Security scan results
                CREATE TABLE IF NOT EXISTS security_checks (
                    id BIGSERIAL PRIMARY KEY,
                    domain VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    overall_score INTEGER,
                    threats JSONB,
                    security_headers JSONB,
                    malware_detected BOOLEAN,
                    suspicious_links JSONB,
                    suspicious_files JSONB,
                    external_scripts JSONB,
                    has_waf BOOLEAN,
                    waf_name VARCHAR(200),
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_security_domain_ts
                    ON security_checks (domain, timestamp DESC);

                -- Alerts
                CREATE TABLE IF NOT EXISTS alerts (
                    id BIGSERIAL PRIMARY KEY,
                    domain VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    alert_type VARCHAR(100) NOT NULL,
                    severity VARCHAR(20) NOT NULL,
                    description TEXT,
                    details TEXT,
                    recommendation TEXT,
                    notified_channels JSONB,
                    acknowledged BOOLEAN DEFAULT FALSE,
                    acknowledged_by VARCHAR(200),
                    acknowledged_at TIMESTAMPTZ,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at TIMESTAMPTZ
                );

                CREATE INDEX IF NOT EXISTS idx_alerts_domain_ts
                    ON alerts (domain, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_alerts_severity
                    ON alerts (severity, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_alerts_unresolved
                    ON alerts (resolved, timestamp DESC)
                    WHERE resolved = FALSE;

                -- Aggregated daily statistics
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id BIGSERIAL PRIMARY KEY,
                    domain VARCHAR(255) NOT NULL,
                    date DATE NOT NULL,
                    uptime_percent FLOAT,
                    avg_response_time_ms FLOAT,
                    max_response_time_ms FLOAT,
                    min_response_time_ms FLOAT,
                    total_checks INTEGER,
                    failed_checks INTEGER,
                    security_score INTEGER,
                    ssl_days_left INTEGER,
                    issues_count INTEGER,
                    UNIQUE(domain, date)
                );

                CREATE INDEX IF NOT EXISTS idx_daily_domain_date
                    ON daily_stats (domain, date DESC);
            """)

    # ===============================
    # SAVE RESULTS
    # ===============================

    async def save_availability_result(self, result):
        """Save availability check result."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO availability_checks
                (domain, timestamp, is_available, http_status,
                 https_status, response_time_ms, dns_resolved,
                 dns_ip, dns_resolve_time_ms, ping_ok,
                 ping_time_ms, ssl_redirect, error_message,
                 pages_status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                        $10, $11, $12, $13, $14)
            """,
                result.domain, result.timestamp,
                result.is_available, result.http_status,
                result.https_status, result.response_time_ms,
                result.dns_resolved, result.dns_ip,
                result.dns_resolve_time_ms, result.ping_ok,
                result.ping_time_ms, result.ssl_redirect,
                result.error_message,
                json.dumps(result.pages_status, default=str)
            )

    async def save_ssl_result(self, result):
        """Save SSL check result."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO ssl_checks
                (domain, timestamp, has_ssl, is_valid, issuer,
                 subject, valid_from, valid_until,
                 days_until_expiry, is_expiring_soon,
                 is_expired, protocol_version, cipher_suite,
                 san_domains, chain_valid, error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                        $10, $11, $12, $13, $14, $15, $16)
            """,
                result.domain, result.timestamp,
                result.has_ssl, result.is_valid,
                result.issuer, result.subject,
                result.valid_from, result.valid_until,
                result.days_until_expiry,
                result.is_expiring_soon, result.is_expired,
                result.protocol_version, result.cipher_suite,
                json.dumps(result.san_domains),
                result.chain_valid, result.error_message
            )

    async def save_ui_result(self, result):
        """Save UI test result."""
        async with self.pool.acquire() as conn:
            elements_data = [
                {
                    'name': e.name,
                    'selector': e.selector,
                    'action': e.action,
                    'is_found': e.is_found,
                    'is_clickable': e.is_clickable,
                    'is_visible': e.is_visible,
                    'action_success': e.action_success,
                    'error_message': e.error_message
                } for e in result.elements
            ]
            await conn.execute("""
                INSERT INTO ui_checks
                (domain, timestamp, page_url, page_loaded,
                 page_load_time_ms, elements,
                 has_critical_issues, screenshot_path,
                 console_errors, error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                result.domain, result.timestamp,
                result.page_url, result.page_loaded,
                result.page_load_time_ms,
                json.dumps(elements_data),
                result.has_critical_issues,
                result.screenshot_path,
                json.dumps(result.console_errors),
                result.error_message
            )

    async def save_sitemap_result(self, result):
        """Save sitemap crawl result."""
        async with self.pool.acquire() as conn:
            pages_detail = {
                path: {
                    'url': page.url,
                    'name': page.name,
                    'status_code': page.status_code,
                    'response_time_ms': page.response_time_ms,
                    'is_ok': page.is_ok,
                    'error_message': page.error_message
                } for path, page in result.pages.items()
            }
            await conn.execute("""
                INSERT INTO sitemap_checks
                (domain, timestamp, sitemap_found, sitemap_url,
                 total_pages, pages_ok, pages_error,
                 pages_detail, tree_structure, error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                result.domain, result.timestamp,
                result.sitemap_found, result.sitemap_url,
                result.total_pages, result.pages_ok,
                result.pages_error,
                json.dumps(pages_detail, default=str),
                json.dumps(result.tree_structure, default=str),
                result.error_message
            )

    async def save_security_result(self, result):
        """Save security scan result."""
        async with self.pool.acquire() as conn:
            threats_data = [
                {
                    'threat_type': t.threat_type,
                    'severity': t.severity,
                    'description': t.description,
                    'location': t.location,
                    'details': t.details,
                    'recommendation': t.recommendation
                } for t in result.threats
            ]
            await conn.execute("""
                INSERT INTO security_checks
                (domain, timestamp, overall_score, threats,
                 security_headers, malware_detected,
                 suspicious_links, suspicious_files,
                 external_scripts, has_waf, waf_name,
                 error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                        $9, $10, $11, $12)
            """,
                result.domain, result.timestamp,
                result.overall_score,
                json.dumps(threats_data),
                json.dumps(result.security_headers),
                result.malware_detected,
                json.dumps(result.suspicious_links),
                json.dumps(result.suspicious_files),
                json.dumps(result.external_scripts),
                result.has_waf, result.waf_name,
                result.error_message
            )

    # ===============================
    # RETRIEVE DATA
    # ===============================

    async def get_uptime_stats(
        self, domain: str, days: int = 30
    ) -> dict:
        """Get uptime statistics for a given period."""
        async with self.pool.acquire() as conn:
            cutoff = datetime.now() - timedelta(days=days)
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_available THEN 1 ELSE 0 END) as available,
                    AVG(response_time_ms) as avg_response,
                    MAX(response_time_ms) as max_response,
                    MIN(response_time_ms) as min_response
                FROM availability_checks
                WHERE domain = $1 AND timestamp >= $2
            """, domain, cutoff)

            total = row['total'] or 0
            available = row['available'] or 0

            return {
                'domain': domain,
                'period_days': days,
                'total_checks': total,
                'available_checks': available,
                'uptime_percent': (
                    round(available / total * 100, 2)
                    if total > 0 else 0
                ),
                'avg_response_ms': (
                    round(row['avg_response'], 2)
                    if row['avg_response'] else None
                ),
                'max_response_ms': row['max_response'],
                'min_response_ms': row['min_response']
            }

    async def get_alert_history(
        self, domain: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[dict]:
        """Get alert history with optional filters."""
        async with self.pool.acquire() as conn:
            query = "SELECT * FROM alerts WHERE 1=1"
            params = []
            param_idx = 1

            if domain:
                query += f" AND domain = ${param_idx}"
                params.append(domain)
                param_idx += 1

            if severity:
                query += f" AND severity = ${param_idx}"
                params.append(severity)
                param_idx += 1

            query += f" ORDER BY timestamp DESC LIMIT ${param_idx}"
            params.append(limit)

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_security_history(
        self, domain: str, limit: int = 30
    ) -> List[dict]:
        """Get security check history."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT timestamp, overall_score,
                       malware_detected, has_waf,
                       threats, security_headers
                FROM security_checks
                WHERE domain = $1
                ORDER BY timestamp DESC
                LIMIT $2
            """, domain, limit)

            return [
                {
                    'timestamp': row['timestamp'].isoformat(),
                    'score': row['overall_score'],
                    'malware': row['malware_detected'],
                    'waf': row['has_waf'],
                    'threats': json.loads(row['threats'] or '[]'),
                    'headers': json.loads(
                        row['security_headers'] or '{}'
                    )
                } for row in rows
            ]

    async def cleanup_old_records(self, cutoff: datetime) -> int:
        """Delete old records before the cutoff date."""
        total_deleted = 0
        tables = [
            'availability_checks', 'ssl_checks',
            'ui_checks', 'sitemap_checks',
            'security_checks', 'alerts'
        ]
        async with self.pool.acquire() as conn:
            for table in tables:
                result = await conn.execute(
                    f"DELETE FROM {table} WHERE timestamp < $1",
                    cutoff
                )
                count = int(result.split(' ')[-1])
                total_deleted += count
                logger.info(
                    f"Cleanup {table}: deleted {count} records"
                )
        return total_deleted

    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")
