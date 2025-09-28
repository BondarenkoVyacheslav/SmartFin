-- Расширения
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;
-- (опционально) CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Домены и ENUM'ы
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'asset_class_enum') THEN
    CREATE TYPE asset_class_enum AS ENUM (
      'stock','bond','fund','crypto','fiat','metal','cash','deposit','other'
    );
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transaction_type_enum') THEN
    CREATE TYPE transaction_type_enum AS ENUM (
      'buy','sell','deposit','withdraw','transfer_in','transfer_out',
      'dividend','coupon','interest','fee','split','merge','adjustment'
    );
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'price_interval_enum') THEN
    CREATE TYPE price_interval_enum AS ENUM ('tick','min','hour','day');
  END IF;
END$$;

-- Пользователи (если не используете Django auth)
CREATE TABLE IF NOT EXISTS app_user (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email               citext UNIQUE NOT NULL,
  password_hash       text,                      -- если храните у себя
  is_active           boolean NOT NULL DEFAULT true,
  twofa_secret        text,                      -- шифровать на уровне прилож.
  base_currency_id    uuid,                      -- предпочитаемая валюта
  timezone            text NOT NULL DEFAULT 'UTC',
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Валюты
CREATE TABLE IF NOT EXISTS currency (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code         text UNIQUE NOT NULL,             -- 'USD','RUB','BTC'
  name         text NOT NULL,
  decimals     int NOT NULL DEFAULT 2,           -- для отображения/округления
  is_crypto    boolean NOT NULL DEFAULT false,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- Биржи/площадки (опционально)
CREATE TABLE IF NOT EXISTS exchange (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code         text UNIQUE NOT NULL,             -- 'MOEX','NYSE','BINANCE'
  name         text NOT NULL,
  country      text,
  timezone     text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- Активы (включая 'cash' по каждой валюте)
CREATE TABLE IF NOT EXISTS asset (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  class              asset_class_enum NOT NULL,
  symbol             text NOT NULL,
  name               text NOT NULL,
  trading_currency_id uuid REFERENCES currency(id),
  isin               text,
  exchange_id        uuid REFERENCES exchange(id),
  metadata           jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active          boolean NOT NULL DEFAULT true,
  created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_symbol_exchange
  ON asset(symbol, exchange_id) NULLS NOT DISTINCT;

-- Идентификаторы/алиасы актива (FIGI, ISIN, Yahoo, MOEX, Coingecko и т.п.)
CREATE TABLE IF NOT EXISTS asset_identifier (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id   uuid NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
  id_type    text NOT NULL,           -- 'ISIN','FIGI','YF','MOEX','CGK'...
  id_value   text NOT NULL,
  UNIQUE(id_type, id_value),
  UNIQUE(asset_id, id_type)
);

-- Портфели
CREATE TABLE IF NOT EXISTS portfolio (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  name              text NOT NULL,
  base_currency_id  uuid NOT NULL REFERENCES currency(id),
  settings          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, name)
);

-- Сделки/движения (унифицировано: активы + кэш как asset.class='cash')
CREATE TABLE IF NOT EXISTS transaction (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id        uuid NOT NULL REFERENCES portfolio(id) ON DELETE CASCADE,
  asset_id            uuid NOT NULL REFERENCES asset(id),
  tx_type             transaction_type_enum NOT NULL,
  tx_time             timestamptz NOT NULL,
  quantity            numeric(38, 18) NOT NULL DEFAULT 0,    -- кол-во актива (для cash = сумма)
  price               numeric(38, 10),                       -- цена за 1 в валюте price_currency
  price_currency_id   uuid REFERENCES currency(id),
  fee                 numeric(38, 10) NOT NULL DEFAULT 0,    -- комиссия в валюте price_currency
  notes               text,
  metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- Нормализация для переводов и валютных операций
  linked_tx_id        uuid REFERENCES transaction(id) ON DELETE SET NULL,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CHECK ((price IS NULL) = (price_currency_id IS NULL))  -- либо оба заданы, либо оба NULL
);

CREATE INDEX IF NOT EXISTS ix_tx_portfolio_time ON transaction (portfolio_id, tx_time DESC);
CREATE INDEX IF NOT EXISTS ix_tx_asset_time ON transaction (asset_id, tx_time DESC);
CREATE INDEX IF NOT EXISTS ix_tx_type ON transaction (tx_type);

-- Таймсерии цен на активы
CREATE TABLE IF NOT EXISTS price (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id        uuid NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
  ts              timestamptz NOT NULL,
  price           numeric(38, 10) NOT NULL,
  currency_id     uuid NOT NULL REFERENCES currency(id),  -- валюта цены
  source          text NOT NULL,                          -- 'MOEX','COINGECKO',...
  interval        price_interval_enum NOT NULL DEFAULT 'day',
  metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE(asset_id, ts, source, interval)
);

CREATE INDEX IF NOT EXISTS ix_price_asset_ts ON price (asset_id, ts DESC);
CREATE INDEX IF NOT EXISTS ix_price_source ON price (source);

-- FX курсы (валюта->валюта)
CREATE TABLE IF NOT EXISTS fx_rate (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  base_currency_id uuid NOT NULL REFERENCES currency(id),
  quote_currency_id uuid NOT NULL REFERENCES currency(id),
  ts               timestamptz NOT NULL,
  rate             numeric(38, 10) NOT NULL, -- сколько quote за 1 base
  source           text NOT NULL,            -- 'ECB','OXR','MOEX'
  UNIQUE(base_currency_id, quote_currency_id, ts, source)
);

CREATE INDEX IF NOT EXISTS ix_fx_pair_ts ON fx_rate (base_currency_id, quote_currency_id, ts DESC);

-- Интеграции (биржи/брокеры/банки/апи данных)
CREATE TABLE IF NOT EXISTS integration (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  provider       text NOT NULL,                       -- 'TINKOFF','ALFA','MOEX','BINANCE','COINGECKO'
  display_name   text NOT NULL,
  status         text NOT NULL DEFAULT 'active',      -- 'active','paused','revoked','error'
  credentials_encrypted text NOT NULL,                -- шифруйте на уровне приложения
  last_sync_at   timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, provider, display_name)
);

-- Советы/рекомендации (результаты ML/правил)
CREATE TABLE IF NOT EXISTS advice (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id   uuid NOT NULL REFERENCES portfolio(id) ON DELETE CASCADE,
  kind           text NOT NULL,               -- 'rebalance','risk','tax','yield'
  message        text NOT NULL,
  score          numeric(8, 4),               -- уверенность/приоритет
  payload        jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- Аудит
CREATE TABLE IF NOT EXISTS audit_log (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES app_user(id) ON DELETE SET NULL,
  ts           timestamptz NOT NULL DEFAULT now(),
  action       text NOT NULL,                 -- 'login','create_tx','update_tx','sync_start',...
  target_type  text,                          -- 'transaction','portfolio','integration',...
  target_id    uuid,
  ip           inet,
  user_agent   text,
  details      jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- Ссылки по умолчанию: базовая валюта пользователя
ALTER TABLE app_user
  ADD CONSTRAINT fk_user_base_currency
  FOREIGN KEY (base_currency_id) REFERENCES currency(id);

-- Рекомендации по производительности:
-- 1) Рассмотреть TimescaleDB и сделать price как hypertable по ts.
-- 2) Для vanilla PG: PARTITION BY RANGE (date_trunc('month', ts)) у price при больших объёмах.
-- 3) Создать partial index для свежих цен: CREATE INDEX ... ON price(asset_id, ts DESC) WHERE ts > now() - interval '180 days';