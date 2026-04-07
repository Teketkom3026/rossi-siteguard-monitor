# SiteGuard Monitor

**Комплексная система мониторинга сайтов 24/7 с мгновенными уведомлениями**

Автоматический мониторинг доступности, SSL-сертификатов, безопасности, UI-элементов и вредоносного кода для всех ваших сайтов. Уведомления в Telegram, Email и SMS.

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      Nginx Reverse Proxy                     │
│    / → Landing  /admin → Admin  /dashboard → Dashboard       │
│    /api → FastAPI Backend                                    │
└────────┬──────────────┬──────────────┬──────────────────────┘
         │              │              │
┌────────▼────┐  ┌──────▼──────┐  ┌───▼────────────────┐
│  Landing    │  │  Admin      │  │  FastAPI Backend    │
│  (HTML)     │  │  Panel      │  │  (API + Auth +      │
│             │  │  (HTML/JS)  │  │   Licensing)        │
└─────────────┘  └─────────────┘  └───┬────────────────┘
                                      │
                           ┌──────────┼──────────┐
                           │          │          │
                    ┌──────▼──┐  ┌───▼────┐  ┌──▼──────┐
                    │ Postgres │  │ Redis  │  │ Monitor │
                    │ 15       │  │ 7      │  │ Worker  │
                    └──────────┘  └────────┘  └─────────┘
                                                  │
                              ┌────────────────────┼────────────┐
                              │                    │            │
                        ┌─────▼─────┐  ┌──────────▼──┐  ┌─────▼─────┐
                        │ Checkers  │  │ Notifications│  │ Dashboard │
                        │ - HTTP    │  │ - Telegram   │  │ (Flask)   │
                        │ - SSL     │  │ - Email      │  │           │
                        │ - UI Test │  │ - SMS        │  │           │
                        │ - Security│  │ - Push       │  │           │
                        │ - Malware │  │              │  │           │
                        └───────────┘  └──────────────┘  └───────────┘

┌──────────────────────┐  ┌──────────────────────┐
│  Windows Desktop     │  │  Android App         │
│  (PyQt6)             │  │  (Kotlin/Compose)    │
│  - Setup Wizard      │  │  - License Screen    │
│  - Dashboard         │  │  - Dashboard         │
│  - System Tray       │  │  - Push Notifications│
└──────────────────────┘  └──────────────────────┘
```

## Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/your-org/rossi-siteguard-monitor.git
cd rossi-siteguard-monitor
```

### 2. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env, заполнив все необходимые значения
```

### 3. Запуск через Docker Compose

```bash
cd siteguard-backend
docker compose up -d
```

Сервисы будут доступны:
- **Landing page**: http://87.228.29.55/
- **Admin panel**: http://87.228.29.55/admin
- **Dashboard**: http://87.228.29.55/dashboard
- **API**: http://87.228.29.55/api
- **API Docs (Swagger)**: http://87.228.29.55/api/docs

### 4. Инициализация базы данных

При первом запуске миграции выполняются автоматически из `database/migrations/001_initial.sql`.

## Компоненты

### Backend (siteguard-backend/)

Серверная часть на FastAPI:
- **API**: REST API для управления лицензиями, мониторингом, уведомлениями
- **Checkers**: Модули проверки (доступность, SSL, UI, безопасность, malware)
- **Notifications**: Telegram, Email, SMS, Firebase Push
- **Dashboard**: Веб-дашборд мониторинга (Flask)
- **Admin**: Панель администрирования
- **Scheduler**: Планировщик проверок на базе APScheduler + Redis

### Desktop (siteguard-desktop/)

Windows-приложение на PyQt6:
- Setup Wizard при первом запуске
- Активация лицензионного ключа
- Дашборд мониторинга
- System tray с уведомлениями

### Android (siteguard-android/)

Android-приложение на Kotlin + Jetpack Compose:
- Material 3 дизайн с тёмной темой
- Push-уведомления через Firebase
- Дашборд мониторинга в реальном времени

## Формат лицензионного ключа

```
SG-XXXXX-XXXXX-XXXXX-XXXXX-CHECKSUM
```

- Префикс: `SG-`
- 4 группы по 5 символов (A-Z, 0-9, без O/I/L)
- Контрольная сумма HMAC-SHA256 (5 символов)
- Пример: `SG-A3B5C-D7E9F-G2H4J-K6L8M-N1P3Q`

## Тарифные планы

| План | Цена | Сайты | Устройства | Проверки/день |
|------|------|-------|------------|---------------|
| Trial | Бесплатно (14 дней) | 3 | 1 | 100 |
| Starter | 2 990 ₽/год | 5 | 2 | 500 |
| Professional | 9 990 ₽/год | 25 | 5 | 5 000 |
| Business | 29 990 ₽/год | 100 | 10 | 50 000 |
| Enterprise | 99 990 ₽/год | Безлимит | 50 | Безлимит |

## API Документация

Полная документация API доступна:
- **Swagger UI**: `/api/docs`
- **ReDoc**: `/api/redoc`
- **Файл**: [docs/API.md](docs/API.md)

## CI/CD

Автоматическая сборка и деплой при создании тега:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Workflow (`.github/workflows/build.yml`) выполняет:
1. Сборку Docker-образа бэкенда и деплой на сервер
2. Сборку Windows EXE (PyInstaller + NSIS)
3. Сборку Android APK/AAB
4. Создание GitHub Release
5. Загрузку в Google Play и RuStore
6. Уведомление в Telegram

### Необходимые GitHub Secrets

| Secret | Описание |
|--------|----------|
| `PROD_HOST` | IP сервера (87.228.29.55) |
| `PROD_USER` | SSH пользователь |
| `PROD_SSH_KEY` | SSH приватный ключ |
| `DOCKER_REGISTRY` | Адрес Docker registry |
| `DOCKER_USERNAME` | Логин Docker registry |
| `DOCKER_PASSWORD` | Пароль Docker registry |
| `CODE_SIGN_PASSWORD` | Пароль сертификата подписи |
| `S3_BUCKET` | S3 бакет для релизов |
| `AWS_ACCESS_KEY_ID` | AWS ключ |
| `AWS_SECRET_ACCESS_KEY` | AWS секрет |
| `ANDROID_KEYSTORE_BASE64` | Keystore в base64 |
| `KEYSTORE_PASSWORD` | Пароль keystore |
| `KEY_ALIAS` | Alias ключа |
| `KEY_PASSWORD` | Пароль ключа |
| `GOOGLE_PLAY_SERVICE_ACCOUNT` | JSON сервисного аккаунта |
| `RUSTORE_TOKEN` | Токен RuStore |
| `TG_BOT_TOKEN` | Токен бота для деплой-уведомлений |
| `TG_DEPLOY_CHAT` | Chat ID для уведомлений |

## Деплой

Подробная инструкция: [docs/DEPLOY.md](docs/DEPLOY.md)

## Мониторинг сайтов

Система мониторит 19 сайтов группы Росси:

- rossimarket.ru, bvs.com.ru, cargat.ru, ceresit.com.ru
- cisa.com.ru, commax.com.ru, dkc-russia.com.ru, rvi.com.ru
- systeme-electric.com.ru, tantos.com.ru, baofeng.com.ru
- cas.com.ru, commandcore.ru, rossipotok.ru, rossi.ru
- rossiac.ru, rossiparts.ru, rossiproekt.ru, suverenitet.tech

## Лицензия

Проприетарное ПО. Все права защищены.
