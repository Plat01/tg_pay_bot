# Local vs Production Deployment

## Running from Russia (Telegram blocked)

Для запуска бота локально из России, где Telegram API заблокирован:

### 1. Network Mode: Host
Оба контейнера должны использовать `network_mode: host`:

```yaml
services:
  app:
    network_mode: host
    environment:
      DB_HOST: localhost

  db:
    network_mode: host
```

**Почему:**
- Контейнер с `network_mode: host` использует сетевой стек хост-системы напрямую
- Это позволяет использовать VPN/прокси системы для обхода блокировки Telegram
- Без host mode контейнер изолирован и не может получить доступ к external API

### 2. Database Connection
- `DB_HOST=localhost` или `DB_HOST=127.0.0.1`
- PostgreSQL доступен на localhost:5432 благодаря host network

### 3. Proxy (optional)
Если VPN не используется, можно настроить прокси:
```
PROXY_URL=http://user:password@proxy_host:port
```

---

## Production (Non-Russian server)

На сервере вне России Telegram API доступен напрямую. Можно убрать:

### Remove: network_mode: host
```yaml
services:
  app:
    # network_mode: host - REMOVE
    environment:
      DB_HOST: db  # Use container name

  db:
    # network_mode: host - REMOVE
    ports:
      - "5432:5432"  # Optional: only if external access needed
```

### Benefits of bridge network:
- Контейнеры изолированы от хост-системы (безопаснее)
- Docker DNS: контейнер `app` резолвит `db` как имя контейнера
- Можно использовать несколько проектов без конфликтов портов

### Remove: PROXY_URL
```
# PROXY_URL - REMOVE (Telegram API доступен напрямую)
```

---

## Quick Comparison

| Setting | Russia (blocked) | Production |
|---------|------------------|------------|
| `network_mode` | `host` (both) | bridge (default) |
| `DB_HOST` | `localhost` | `db` |
| `PROXY_URL` | Optional | Remove |
| `ports` (db) | Not needed | Optional |

---

## Docker Compose Examples

### Local (Russia)
```yaml
services:
  app:
    build:
      context: .
      network: host  # For build
    network_mode: host
    environment:
      DB_HOST: localhost
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./src:/app/src:ro

  db:
    image: postgres:16-alpine
    network_mode: host
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: tg_pay_bot
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -h localhost"]
      interval: 5s
      timeout: 5s
      retries: 5
```

### Production
```yaml
services:
  app:
    build:
      context: .
    env_file: .env
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: tg_pay_bot
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    # ports: - "5432:5432"  # Only if external access needed
```