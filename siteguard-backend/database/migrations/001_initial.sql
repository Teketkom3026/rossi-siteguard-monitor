-- ============================================================
-- SiteGuard Monitor - Initial Database Migration
-- PostgreSQL 16+
-- ============================================================

BEGIN;

-- ============================================================
-- Users table for dashboard authentication
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- ============================================================
-- License management
-- ============================================================
CREATE TABLE IF NOT EXISTS licenses (
    id BIGSERIAL PRIMARY KEY,
    license_key VARCHAR(255) NOT NULL UNIQUE,
    organization VARCHAR(500) NOT NULL,
    plan VARCHAR(50) NOT NULL DEFAULT 'basic',
    max_sites INTEGER NOT NULL DEFAULT 10,
    max_checks_per_day INTEGER NOT NULL DEFAULT 1000,
    features JSONB DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    activated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_licenses_key ON licenses (license_key);
CREATE INDEX IF NOT EXISTS idx_licenses_org ON licenses (organization);

-- ============================================================
-- Device activations (track where licenses are used)
-- ============================================================
CREATE TABLE IF NOT EXISTS device_activations (
    id BIGSERIAL PRIMARY KEY,
    license_id BIGINT NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
    device_fingerprint VARCHAR(255) NOT NULL,
    device_name VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deactivated_at TIMESTAMPTZ,
    UNIQUE(license_id, device_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_device_license ON device_activations (license_id);
CREATE INDEX IF NOT EXISTS idx_device_fingerprint ON device_activations (device_fingerprint);

-- ============================================================
-- Monitored sites configuration
-- ============================================================
CREATE TABLE IF NOT EXISTS monitored_sites (
    id BIGSERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(500),
    check_interval INTEGER NOT NULL DEFAULT 300,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    checks_config JSONB NOT NULL DEFAULT '{}',
    critical_pages JSONB DEFAULT '[]',
    ui_elements JSONB DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    added_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sites_domain ON monitored_sites (domain);
CREATE INDEX IF NOT EXISTS idx_sites_priority ON monitored_sites (priority);
CREATE INDEX IF NOT EXISTS idx_sites_active ON monitored_sites (is_active) WHERE is_active = TRUE;

-- ============================================================
-- Check results: Availability
-- ============================================================
CREATE TABLE IF NOT EXISTS check_results (
    id BIGSERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_success BOOLEAN NOT NULL,
    response_time_ms FLOAT,
    status_code INTEGER,
    result_data JSONB,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_check_results_domain_type
    ON check_results (domain, check_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_check_results_ts
    ON check_results (timestamp DESC);

-- Availability checks (detailed)
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

-- ============================================================
-- Check results: SSL
-- ============================================================
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

-- ============================================================
-- Check results: UI Tests
-- ============================================================
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

-- ============================================================
-- Check results: Sitemap
-- ============================================================
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

-- ============================================================
-- Check results: Security
-- ============================================================
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

-- ============================================================
-- Alerts
-- ============================================================
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

-- ============================================================
-- Uptime / Daily aggregated statistics
-- ============================================================
CREATE TABLE IF NOT EXISTS uptime_stats (
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

CREATE INDEX IF NOT EXISTS idx_uptime_domain_date
    ON uptime_stats (domain, date DESC);

-- ============================================================
-- Trigger for updated_at columns
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_licenses_updated_at
    BEFORE UPDATE ON licenses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_monitored_sites_updated_at
    BEFORE UPDATE ON monitored_sites
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- Insert default admin user (password: admin - change immediately)
-- Password hash is bcrypt of 'admin'
-- ============================================================
INSERT INTO users (username, email, password_hash, role)
VALUES (
    'admin',
    'admin@siteguard.local',
    '$2b$12$LJ3m4ys3Lz0QmDGPx8v5/.dummy.hash.change.this.immediately',
    'admin'
) ON CONFLICT (username) DO NOTHING;

COMMIT;
