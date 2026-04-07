# Architecture

## Overview

SiteGuard Monitor is a multi-platform site monitoring system consisting of:

1. **Backend Server** (Python/FastAPI) - Core monitoring engine, REST API, licensing
2. **Windows Desktop** (Python/PyQt6) - Native Windows client
3. **Android App** (Kotlin/Jetpack Compose) - Mobile client
4. **Landing Page** (HTML/CSS/JS) - Product marketing page
5. **Admin Panel** (HTML/JS) - License and user management

## Backend Architecture

### Tech Stack
- **Framework**: FastAPI (async)
- **Database**: PostgreSQL 15 (via SQLAlchemy async)
- **Cache/Queue**: Redis 7
- **Scheduler**: APScheduler
- **Browser Testing**: Playwright (Chromium)
- **Reverse Proxy**: Nginx

### Module Structure

```
siteguard-backend/
├── app/                    # FastAPI application
│   ├── main.py            # Entry point, middleware, routers
│   ├── config.py          # Settings (pydantic-settings)
│   ├── database.py        # Async SQLAlchemy engine
│   ├── auth/              # JWT authentication
│   ├── licensing/         # License management
│   │   ├── models.py     # SQLAlchemy models
│   │   ├── key_generator.py  # HMAC-based key generation
│   │   └── routes.py     # API endpoints
│   ├── monitoring/        # Site monitoring API
│   ├── payments/          # YooKassa/Stripe integration
│   ├── admin/             # Admin panel
│   └── notifications/     # Push notifications (Firebase)
├── checkers/              # Monitoring modules
│   ├── availability.py   # HTTP/DNS/Ping checks
│   ├── ssl_checker.py    # SSL certificate validation
│   ├── ui_tester.py      # Playwright UI element testing
│   ├── sitemap_crawler.py # Sitemap parsing & crawling
│   ├── security_scanner.py # Security header/vuln scanning
│   └── malware_detector.py # Malware pattern detection
├── notifications/         # Alert channels
│   ├── telegram_bot.py   # Aiogram-based bot
│   ├── email_sender.py   # SMTP (aiosmtplib)
│   └── sms_sender.py     # SMS.ru/SMSC/SMS Aero
├── dashboard/             # Flask web dashboard
├── scheduler/             # APScheduler + Redis queue
├── database/              # Migrations
└── main.py               # Monitoring orchestrator
```

### Data Flow

```
Scheduler (cron) → Task Queue (Redis) → Checker Modules
                                            │
                                    Process Results
                                            │
                                    ┌───────┴───────┐
                                    │               │
                              Update DB       Send Alerts
                              (PostgreSQL)    (if severity threshold)
                                    │               │
                              Dashboard      Telegram/Email/SMS/Push
```

### License Key Format

```
SG-XXXXX-XXXXX-XXXXX-XXXXX-HHHHH
│   │     │     │     │     └── HMAC-SHA256 checksum (5 chars)
│   └─────┴─────┴─────┴── Random chars (A-Z, 0-9, no O/I/L)
└── Prefix
```

### Severity Levels

| Level | Color | Notifications | Examples |
|-------|-------|--------------|----------|
| Critical | Red | Telegram + Email + SMS + Push | Site down, SSL expired |
| High | Orange | Telegram + Email + Push | Malware detected, security < 40 |
| Medium | Yellow | Telegram + Email | SSL expiring < 14d, slow response |
| Low | Blue | Telegram | Minor security warnings |
| OK | Green | - | All checks passed |

## Database Schema

### Core Tables

- **users** - User accounts (email, password, company, notification settings)
- **licenses** - License keys with plan, status, limits, device bindings
- **device_activations** - Device activation records
- **monitored_sites** - Sites being monitored per user
- **check_results** - Historical check data
- **alerts** - Alert history

## Security

- JWT authentication with HS256
- HMAC-SHA256 license key validation
- Rate limiting via slowapi + Nginx
- CORS configuration
- Security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- Password hashing with bcrypt
- Environment-based secret management

## Deployment

- Docker Compose for all services
- Nginx reverse proxy with rate limiting
- PostgreSQL with persistent volumes
- Redis with append-only persistence
- Automatic SSL via Let's Encrypt
- CI/CD via GitHub Actions (tag-triggered)
