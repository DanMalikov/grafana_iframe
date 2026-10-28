# grafana_iframe

## 1. Запуск

Установите Docker Desktop. В каталоге проекта откройте Git Bash и выполните:

```bash
docker compose up -d --build
docker compose ps
```

Портал: <http://localhost:8000/>. Grafana: <http://localhost:3001/>.
MySQL и ClickHouse заполняются автоматически. Grafana настраивается по разделу 3.

## 2. Пользователи и получение паролей

| Сервис | Пользователи |
| --- | --- |
| Портал, Company 1 | `analyst1`, `director1` |
| Портал, Company 2 | `analyst2`, `director2` |
| Grafana | `admin` |
| ClickHouse | `grafana_reader`, `demo_admin` |
| MySQL | `app`, `root` |

На существующем стенде также остались старые пользователи портала:
`analyst123`, `director123`, `analyst456`, `director456`. На новом компьютере
они не создаются. Пароли генерируются при первом запуске и сохраняются в
Docker volumes. В Git Bash получите пароль нужной учётной записи:

```bash
# Общий пароль пользователей портала
MSYS_NO_PATHCONV=1 docker compose exec -T api cat /run/api-secrets/demo-password

# Grafana: admin
MSYS_NO_PATHCONV=1 docker compose exec -T grafana cat /run/grafana-admin/password

# ClickHouse: grafana_reader и demo_admin
MSYS_NO_PATHCONV=1 docker compose exec -T clickhouse cat /run/clickhouse-reader/password
MSYS_NO_PATHCONV=1 docker compose exec -T clickhouse cat /run/clickhouse-admin/password

# MySQL: app и root
MSYS_NO_PATHCONV=1 docker compose exec -T mysql cat /run/mysql-app/password
MSYS_NO_PATHCONV=1 docker compose exec -T mysql cat /run/mysql-root/password
```

Если пароль `admin` меняли через интерфейс Grafana, значение из Docker volume
может не совпадать с действующим. Для других команд ниже с контейнерными
путями `/run` или `/demo` в Git Bash также добавляйте `MSYS_NO_PATHCONV=1`.

## 3. Настройка Grafana

Войдите на <http://localhost:3001/> как `admin` в отдельном профиле браузера.
Пароль получите по команде из раздела 2.

1. **Organizations:** `Administration → General → Organizations → New org`.
   Создайте `Company 1` и `Company 2` или переименуйте уже существующие.
   Переключитесь в каждую Organization и посмотрите её ID в URL (`orgId`).
   В `grafana.ini` в строке `org_mapping` укажите
   `1:<ID Company 1>:Viewer 2:<ID Company 2>:Viewer`.
   После изменения выполните `docker compose restart grafana`.
2. **Connection:** переключитесь в каждую Organization и откройте
   `Connections → Add new connection → ClickHouse → Add new data source`.
   Укажите Server address `clickhouse`, Protocol `HTTP`, Port `8123`,
   Default database `default`, Username `grafana_reader` и пароль из раздела 2.
   Нажмите `Save & test`. Повторите настройку во второй Organization.
3. **Дашборд:** если дашборда с UID `adkxztz` ещё нет, в каждой Organization
   откройте `Dashboards → New → Import dashboard`, вставьте JSON ниже как код,
   нажмите `Load`, затем `Import`. Затем добавьте или обновите две панели
   `Time series` с ClickHouse datasource: «Температура» и «Влажность». В каждой
   выберите SQL editor (режим кода) и Query type `Time series`.

```json
{
  "id": null,
  "uid": "adkxztz",
  "title": "Company Overview",
  "schemaVersion": 17,
  "version": 0,
  "panels": [],
  "time": {"from": "now-24h", "to": "now"}
}
```

SQL для панели «Температура» Company 1:

```sql
SELECT $__timeInterval(sent_at) AS time,
       device_id,
       avg(value_num) AS value
FROM default.metrics
WHERE $__timeFilter(sent_at)
  AND product = 'grafana_iframe_demo'
  AND metric = 'temperature'
  AND device_id IN ('0030014467', '10')
GROUP BY time, device_id
ORDER BY time
```

Для «Влажности» замените `temperature` на `humidity`. Для Company 2 в обеих
панелях замените список устройств на `('1140000464', '1050')`. Выберите диапазон
`Last 24 hours`. Откройте каждый дашборд и проверьте UID в URL:
`/d/<UID>/company-overview`. У обоих нужен одинаковый UID. Если он отличается
от `adkxztz`, замените UID в пути iframe в `app/main.py` (маршрут
`portal_monitoring`). Если точки устарели, обновите их в Git Bash:

```bash
MSYS_NO_PATHCONV=1 docker compose exec -T clickhouse sh /demo/refresh.sh
```

## 4. Базы данных и таблицы

**MySQL, база `grafana_iframe`:**

| Таблица | Столбцы |
| --- | --- |
| `companies` | `id VARCHAR(36)` — PK; `name VARCHAR(100)` |
| `users` | `id VARCHAR(36)` — PK; `username VARCHAR(80)` и `email VARCHAR(255)` — UNIQUE; `password_hash VARCHAR(255)`; `business_role VARCHAR(20)`; `company_id VARCHAR(36)` — FK на `companies.id` |
| `devices` | `id VARCHAR(80)` — PK; `company_id VARCHAR(36)` — FK на `companies.id` |
| `alembic_version` | `version_num VARCHAR(32)` — текущая версия миграции |

В чистой базе создаются Company 1 (`id='1'`) и Company 2 (`id='2'`), по два
пользователя на компанию. Устройства: `0030014467`, `10` у Company 1;
`1140000464`, `1050` у Company 2. На текущем стенде также остались старые
демонстрационные записи компаний `123` и `456`.

**ClickHouse, база `default`:** таблица `metrics` с движком `MergeTree` и
`ORDER BY (device_id, metric, sent_at)`.

| Столбец | Тип |
| --- | --- |
| `metric` | `LowCardinality(String)` |
| `serial_number` | `String` |
| `model` | `String` |
| `product` | `String` |
| `value_str` | `String` |
| `value_num` | `Nullable(Float64)` |
| `sent_at` | `DateTime` |
| `device_id` | `String` |

Демоданные имеют `product='grafana_iframe_demo'`. **Grafana** отдельно хранит
свои служебные таблицы в SQLite-файле `grafana.db` внутри volume `grafana_data`.
Их текущую полную схему показывает команда из раздела 6. Системные базы MySQL
и ClickHouse также перечисляются командой `SHOW DATABASES` из раздела 6.

## 5. Добавление пользователя

Укажите уникальный логин, компанию `1` или `2`, роль `analyst` или `director`:

```powershell
docker compose exec api python -m app.add_user newanalyst --company-id 1 --role analyst --email newanalyst@example.local
```

Введите и повторите пароль по запросу. Пользователь появится в MySQL и сможет
войти в портал; Grafana выберет Organization по компании в его JWT. Чтобы
добавить пользователя Company 2, замените `--company-id 1` на `2`.

## 6. Просмотр состояния таблиц

**MySQL:**

```powershell
docker compose exec mysql mysql -u root -p
```

Введите пароль `root` из раздела 2. В консоли MySQL:

```sql
SHOW DATABASES;
USE grafana_iframe;
SHOW TABLES;
DESCRIBE users;
SELECT * FROM companies;
SELECT username, business_role, company_id FROM users;
SELECT * FROM devices;
SELECT * FROM alembic_version;
```

Для любой другой таблицы используйте `DESCRIBE имя_таблицы` и
`SELECT COUNT(*) FROM имя_таблицы`.

**ClickHouse:** быстрая проверка демонстрационных строк:

```powershell
docker compose exec -T clickhouse sh /demo/check.sh
```

Для просмотра всех баз и структуры войдите в оболочку контейнера:

```powershell
docker compose exec clickhouse sh
clickhouse-client --user demo_admin --password="$(cat /run/clickhouse-admin/password)"
```

В консоли ClickHouse:

```sql
SHOW DATABASES;
SHOW TABLES FROM default;
DESCRIBE TABLE default.metrics;
SELECT device_id, metric, count() FROM default.metrics
GROUP BY device_id, metric ORDER BY device_id, metric;
```

**Grafana SQLite:** список всех внутренних таблиц и число строк в каждой;
флаг `--schema` дополнительно выводит их точные определения:

```powershell
docker compose run --rm --no-deps init python scripts/inspect_grafana.py
docker compose run --rm --no-deps init python scripts/inspect_grafana.py --schema
```
