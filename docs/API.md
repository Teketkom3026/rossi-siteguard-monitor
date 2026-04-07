# SiteGuard Monitor API Documentation

Base URL: `http://87.228.29.55/api`

## Authentication

### POST /api/v1/auth/register

Register a new user.

```json
{
    "email": "user@example.com",
    "password": "securepassword",
    "full_name": "John Doe",
    "company_name": "My Company"
}
```

### POST /api/v1/auth/login

Login and receive JWT token.

```json
{
    "email": "user@example.com",
    "password": "securepassword"
}
```

Response:
```json
{
    "access_token": "eyJ...",
    "token_type": "bearer"
}
```

### GET /api/v1/auth/me

Get current user info. Requires Bearer token.

## Licensing

### POST /api/v1/license/activate

Activate a license key on a device.

```json
{
    "license_key": "SG-A3B5C-D7E9F-G2H4J-K6L8M-N1P3Q",
    "device_id": "abc123def456",
    "device_type": "windows",
    "device_info": {
        "name": "My PC",
        "os": "Windows 11"
    }
}
```

### POST /api/v1/license/validate

Periodic license validation (heartbeat). Same request format as activate.

### GET /api/v1/license/info

Get current license info. Requires authentication.

### GET /api/v1/license/plans

Get available pricing plans. Public endpoint.

### POST /api/v1/license/deactivate-device?device_id=xxx

Remove a device from the license. Requires authentication.

## Monitoring

### POST /api/v1/monitor/sites

Add a site to monitor.

```json
{
    "domain": "example.com",
    "name": "My Site",
    "check_interval": 300,
    "settings": {
        "check_availability": true,
        "check_ssl": true,
        "check_ui": true,
        "check_security": true,
        "check_malware": true
    }
}
```

### GET /api/v1/monitor/sites

List all monitored sites.

### PUT /api/v1/monitor/sites/{site_id}

Update site settings.

### DELETE /api/v1/monitor/sites/{site_id}

Remove a site from monitoring.

### GET /api/v1/monitor/dashboard

Get dashboard data with all sites statuses.

### GET /api/v1/monitor/sites/{site_id}/status

Get detailed status for a specific site.

### POST /api/v1/monitor/sites/{site_id}/check-now

Trigger an immediate check for a site.

## Payments

### POST /api/v1/payments/create

Create a payment for a license plan.

```json
{
    "plan": "professional",
    "payment_method": "card"
}
```

### POST /api/v1/payments/webhook

Payment provider webhook (YooKassa/Stripe).

## Admin

### GET /admin

Admin panel web UI.

### GET /admin/api/stats

Dashboard statistics.

### GET /admin/api/licenses

List all licenses with filtering.

### POST /admin/api/licenses

Create a new license.

### POST /admin/api/licenses/{id}/revoke

Revoke a license.

### GET /admin/api/users

List all users.

### POST /admin/api/users

Create a new user.

## Health

### GET /api/health

Health check endpoint.

```json
{
    "status": "ok",
    "version": "1.0.0"
}
```

## Error Responses

All errors follow the format:

```json
{
    "detail": "Error description"
}
```

HTTP status codes:
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden (license expired, limit reached)
- 404: Not Found
- 409: Conflict (duplicate)
- 429: Rate Limited
- 500: Internal Server Error
