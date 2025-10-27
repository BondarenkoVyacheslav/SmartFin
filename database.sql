--
-- PostgreSQL database dump
--

\restrict Osev1d1fcbkLMGWVvtx0EDVjQcqRHVmv3sj8CR4uc44rMONr6PXlXor6fJGobmH

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

-- Started on 2025-10-27 20:31:18

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 10 (class 2615 OID 17809)
-- Name: account; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA account;


ALTER SCHEMA account OWNER TO postgres;

--
-- TOC entry 13 (class 2615 OID 17812)
-- Name: analytics; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA analytics;


ALTER SCHEMA analytics OWNER TO postgres;

--
-- TOC entry 9 (class 2615 OID 17808)
-- Name: core; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA core;


ALTER SCHEMA core OWNER TO postgres;

--
-- TOC entry 16 (class 2615 OID 17815)
-- Name: infra; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA infra;


ALTER SCHEMA infra OWNER TO postgres;

--
-- TOC entry 14 (class 2615 OID 17813)
-- Name: integrations; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA integrations;


ALTER SCHEMA integrations OWNER TO postgres;

--
-- TOC entry 15 (class 2615 OID 17814)
-- Name: llm; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA llm;


ALTER SCHEMA llm OWNER TO postgres;

--
-- TOC entry 11 (class 2615 OID 17810)
-- Name: market; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA market;


ALTER SCHEMA market OWNER TO postgres;

--
-- TOC entry 17 (class 2615 OID 18207)
-- Name: marketdata; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA marketdata;


ALTER SCHEMA marketdata OWNER TO postgres;

--
-- TOC entry 12 (class 2615 OID 17811)
-- Name: portfolio; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA portfolio;


ALTER SCHEMA portfolio OWNER TO postgres;

--
-- TOC entry 18 (class 2615 OID 18208)
-- Name: staging; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA staging;


ALTER SCHEMA staging OWNER TO postgres;

--
-- TOC entry 4 (class 3079 OID 18732)
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- TOC entry 5919 (class 0 OID 0)
-- Dependencies: 4
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- TOC entry 3 (class 3079 OID 17502)
-- Name: citext; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;


--
-- TOC entry 5920 (class 0 OID 0)
-- Dependencies: 3
-- Name: EXTENSION citext; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION citext IS 'data type for case-insensitive character strings';


--
-- TOC entry 2 (class 3079 OID 17465)
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- TOC entry 5921 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- TOC entry 1183 (class 1247 OID 17817)
-- Name: asset_class_enum; Type: TYPE; Schema: core; Owner: postgres
--

CREATE TYPE core.asset_class_enum AS ENUM (
    'stock',
    'bond',
    'fund',
    'index',
    'crypto',
    'fiat',
    'metal',
    'cash',
    'deposit',
    'other'
);


ALTER TYPE core.asset_class_enum OWNER TO postgres;

--
-- TOC entry 1189 (class 1247 OID 17864)
-- Name: price_interval_enum; Type: TYPE; Schema: core; Owner: postgres
--

CREATE TYPE core.price_interval_enum AS ENUM (
    'tick',
    'min',
    'hour',
    'day'
);


ALTER TYPE core.price_interval_enum OWNER TO postgres;

--
-- TOC entry 1186 (class 1247 OID 17836)
-- Name: transaction_type_enum; Type: TYPE; Schema: core; Owner: postgres
--

CREATE TYPE core.transaction_type_enum AS ENUM (
    'buy',
    'sell',
    'deposit',
    'withdraw',
    'transfer_in',
    'transfer_out',
    'dividend',
    'coupon',
    'interest',
    'fee',
    'split',
    'merge',
    'adjustment'
);


ALTER TYPE core.transaction_type_enum OWNER TO postgres;

--
-- TOC entry 319 (class 1255 OID 18632)
-- Name: recalc_eod(date, uuid); Type: PROCEDURE; Schema: analytics; Owner: postgres
--

CREATE PROCEDURE analytics.recalc_eod(IN p_as_of date, IN p_portfolio_id uuid DEFAULT NULL::uuid)
    LANGUAGE plpgsql
    AS $$
DECLARE
  rec_port       RECORD;
  rec_asset      RECORD;
  rec_tx         RECORD;

  base_ccy       UUID;
  fx_tx2base     NUMERIC;
  fx_px2base     NUMERIC;

  qty            NUMERIC := 0;   -- текущее количество
  avg_cost_base  NUMERIC := 0;   -- средняя себестоимость за 1 ед. в базовой валюте
  realized       NUMERIC := 0;   -- реализованный P&L (накопленный)
  income_acc     NUMERIC := 0;   -- накопленный доход

  px             NUMERIC;        -- EOD цена (в валюте котировки)
  px_ccy         UUID;
  value_base     NUMERIC;
  cost_basis     NUMERIC;
  unrealized     NUMERIC;

  d1             DATE := p_as_of - 1;
  d7             DATE := p_as_of - 7;
  d30            DATE := p_as_of - 30;
BEGIN
  -- по всем портфелям или одному
  FOR rec_port IN
    SELECT id, base_currency_id
    FROM portfolio.portfolio
    WHERE p_portfolio_id IS NULL OR id = p_portfolio_id
  LOOP
    base_ccy := rec_port.base_currency_id;

    -- убираем старые факты на дату (идемпотентно)
    DELETE FROM analytics.position_valuation_daily
     WHERE portfolio_id = rec_port.id AND as_of = p_as_of;

    -- активы с транзакциями до даты
    FOR rec_asset IN
      SELECT DISTINCT t.asset_id
      FROM portfolio.transaction t
      WHERE t.portfolio_id = rec_port.id
        AND t.asset_id IS NOT NULL
        AND t.tx_time::date <= p_as_of
    LOOP
      qty           := 0;
      avg_cost_base := 0;
      realized      := 0;
      income_acc    := 0;

      -- леджер по транзакциям (до даты)
      FOR rec_tx IN
        SELECT
          t.tx_time, t.tx_type, t.asset_id,
          t.quantity, t.price, t.price_currency_id, t.fee
        FROM portfolio.transaction t
        WHERE t.portfolio_id = rec_port.id
          AND t.asset_id     = rec_asset.asset_id
          AND t.tx_time::date <= p_as_of
        ORDER BY t.tx_time, t.id
      LOOP
        fx_tx2base := CASE
                         WHEN rec_tx.price_currency_id IS NULL THEN 1
                         ELSE market.fx_at(rec_tx.tx_time::date, rec_tx.price_currency_id, base_ccy)
                       END;

        -- BUY / TRANSFER_IN
        IF rec_tx.tx_type IN ('buy','transfer_in') THEN
          IF rec_tx.quantity IS NULL OR rec_tx.price IS NULL THEN
            CONTINUE;
          END IF;

          -- стоимость покупки в базовой валюте (комиссию прибавляем к cost)
          -- fee у нас в валюте price (другого поля нет)
          -- новые средние по формуле WAC
          DECLARE
            prev_qty NUMERIC := qty;
            added_cost_base NUMERIC := (rec_tx.quantity * rec_tx.price * fx_tx2base) + (COALESCE(rec_tx.fee,0) * fx_tx2base);
          BEGIN
            qty := qty + rec_tx.quantity;
            IF qty > 0 THEN
              avg_cost_base := (prev_qty*avg_cost_base + added_cost_base) / qty;
            ELSE
              avg_cost_base := 0;
            END IF;
          END;

        -- SELL / TRANSFER_OUT
        ELSIF rec_tx.tx_type IN ('sell','transfer_out') THEN
          IF rec_tx.quantity IS NULL OR rec_tx.price IS NULL OR qty <= 0 THEN
            CONTINUE;
          END IF;

          DECLARE
            sell_qty NUMERIC := rec_tx.quantity;               -- ожидаем положительное число
            proceeds_base NUMERIC := (sell_qty * rec_tx.price * fx_tx2base) - (COALESCE(rec_tx.fee,0) * fx_tx2base);
          BEGIN
            realized := realized + (proceeds_base - sell_qty * avg_cost_base);
            qty := qty - sell_qty;
            IF qty = 0 THEN
              avg_cost_base := 0;
            END IF;
          END;

        -- ДОХОДЫ (dividend/coupon/interest) — берём сумму как price*quantity (если quantity=0 или NULL — как price)
        ELSIF rec_tx.tx_type IN ('dividend','coupon','interest') THEN
          IF rec_tx.price IS NOT NULL THEN
            income_acc := income_acc + (rec_tx.price * COALESCE(NULLIF(rec_tx.quantity,0),1)) * fx_tx2base;
          END IF;

        -- ЧИСТАЯ КОМИССИЯ отдельной транзакцией (если такие есть)
        ELSIF rec_tx.tx_type = 'fee' THEN
          realized := realized - (COALESCE(rec_tx.fee,0) * fx_tx2base);

        ELSE
          -- deposit/withdraw/split/merge/adjustment — игнорируем в расчёте WAC на MVP
          CONTINUE;
        END IF;

      END LOOP; -- транзакции

      -- цена на конец дня
      SELECT price, price_currency_id INTO px, px_ccy
      FROM market.last_daily_price(rec_asset.asset_id, p_as_of);

      -- если цены нет — пропускаем (в твоей таблице analytics.position_valuation_daily price NOT NULL)
      IF px IS NULL OR px_ccy IS NULL THEN
        CONTINUE;
      END IF;

      fx_px2base := market.fx_at(p_as_of, px_ccy, base_ccy);

      cost_basis := qty * avg_cost_base;
      value_base := qty * px * fx_px2base;
      unrealized := value_base - cost_basis;

      -- запись факта EOD (UPSERT по уникальному ключу)
      INSERT INTO analytics.position_valuation_daily (
        portfolio_id, asset_id, as_of,
        qty, price, price_currency_id, fx_to_base,
        value_base, cost_basis_base,
        realized_pnl_base, unrealized_pnl_base, income_acc_base,
        metadata
      )
      VALUES (
        rec_port.id, rec_asset.asset_id, p_as_of,
        COALESCE(qty,0), px, px_ccy, fx_px2base,
        COALESCE(value_base,0), COALESCE(cost_basis,0),
        COALESCE(realized,0), COALESCE(unrealized,0), COALESCE(income_acc,0),
        jsonb_build_object('avg_cost_per_unit_base', COALESCE(avg_cost_base,0))
      )
      ON CONFLICT (portfolio_id, asset_id, as_of) DO UPDATE
      SET qty               = EXCLUDED.qty,
          price             = EXCLUDED.price,
          price_currency_id = EXCLUDED.price_currency_id,
          fx_to_base        = EXCLUDED.fx_to_base,
          value_base        = EXCLUDED.value_base,
          cost_basis_base   = EXCLUDED.cost_basis_base,
          realized_pnl_base = EXCLUDED.realized_pnl_base,
          unrealized_pnl_base = EXCLUDED.unrealized_pnl_base,
          income_acc_base   = EXCLUDED.income_acc_base,
          metadata          = analytics.position_valuation_daily.metadata || EXCLUDED.metadata;
    END LOOP; -- активы портфеля

    -- ---------- СВОДКА ПО ПОРТФЕЛЮ ----------
    -- удаляем старый срез за дату
    DELETE FROM analytics.portfolio_snapshot
     WHERE portfolio_id = rec_port.id AND as_of = p_as_of::timestamptz;

    WITH
    today AS (
      SELECT COALESCE(SUM(value_base),0) AS tv
      FROM analytics.position_valuation_daily
      WHERE portfolio_id = rec_port.id AND as_of = p_as_of
    ),
    d_1 AS (
      SELECT COALESCE(SUM(value_base),0) AS tv
      FROM analytics.position_valuation_daily
      WHERE portfolio_id = rec_port.id AND as_of = d1
    ),
    d_7 AS (
      SELECT COALESCE(SUM(value_base),0) AS tv
      FROM analytics.position_valuation_daily
      WHERE portfolio_id = rec_port.id AND as_of = d7
    ),
    d_30 AS (
      SELECT COALESCE(SUM(value_base),0) AS tv
      FROM analytics.position_valuation_daily
      WHERE portfolio_id = rec_port.id AND as_of = d30
    )
    INSERT INTO analytics.portfolio_snapshot (portfolio_id, as_of, total_value, pnl_1d, pnl_7d, pnl_30d)
    SELECT
      rec_port.id,
      p_as_of::timestamptz,
      t.tv,
      t.tv - d1.tv,
      t.tv - d7.tv,
      t.tv - d30.tv
    FROM today t, d_1 d1, d_7 d7, d_30 d30
    ON CONFLICT (portfolio_id, as_of) DO UPDATE
    SET total_value = EXCLUDED.total_value,
        pnl_1d      = EXCLUDED.pnl_1d,
        pnl_7d      = EXCLUDED.pnl_7d,
        pnl_30d     = EXCLUDED.pnl_30d;

  END LOOP; -- портфели
END $$;


ALTER PROCEDURE analytics.recalc_eod(IN p_as_of date, IN p_portfolio_id uuid) OWNER TO postgres;

--
-- TOC entry 472 (class 1255 OID 18484)
-- Name: fn_check_account_portfolio_same_user(); Type: FUNCTION; Schema: integrations; Owner: postgres
--

CREATE FUNCTION integrations.fn_check_account_portfolio_same_user() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  acc_user_id integer;
  pf_user_id  integer;
BEGIN
  SELECT i.user_id INTO acc_user_id
  FROM integrations.account a
  JOIN integrations.integration i ON i.id = a.integration_id
  WHERE a.id = NEW.account_id;

  SELECT p.user_id INTO pf_user_id
  FROM portfolio.portfolio p
  WHERE p.id = NEW.portfolio_id;

  IF acc_user_id IS NULL OR pf_user_id IS NULL OR acc_user_id <> pf_user_id THEN
    RAISE EXCEPTION 'Cross-tenant link not allowed: account belongs to user %, portfolio belongs to user %',
      acc_user_id, pf_user_id
      USING ERRCODE = '42501';
  END IF;

  RETURN NEW;
END$$;


ALTER FUNCTION integrations.fn_check_account_portfolio_same_user() OWNER TO postgres;

--
-- TOC entry 401 (class 1255 OID 18630)
-- Name: fx_at(date, uuid, uuid); Type: FUNCTION; Schema: market; Owner: postgres
--

CREATE FUNCTION market.fx_at(_as_of date, _from uuid, _to uuid) RETURNS numeric
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
  r NUMERIC;
BEGIN
  IF _from = _to THEN
    RETURN 1;
  END IF;

  -- прямое направление
  SELECT fr.rate INTO r
  FROM market.fx_rate fr
  WHERE fr.base_currency_id = _from
    AND fr.quote_currency_id = _to
    AND fr.ts::date <= _as_of
  ORDER BY fr.ts DESC
  LIMIT 1;

  IF r IS NOT NULL THEN
    RETURN r;
  END IF;

  -- инверсия
  SELECT 1.0 / fr.rate INTO r
  FROM market.fx_rate fr
  WHERE fr.base_currency_id = _to
    AND fr.quote_currency_id = _from
    AND fr.ts::date <= _as_of
  ORDER BY fr.ts DESC
  LIMIT 1;

  IF r IS NULL THEN
    RAISE EXCEPTION 'FX rate not found for pair (% -> %) as of %', _from, _to, _as_of;
  END IF;

  RETURN r;
END $$;


ALTER FUNCTION market.fx_at(_as_of date, _from uuid, _to uuid) OWNER TO postgres;

--
-- TOC entry 349 (class 1255 OID 18631)
-- Name: last_daily_price(uuid, date); Type: FUNCTION; Schema: market; Owner: postgres
--

CREATE FUNCTION market.last_daily_price(_asset_id uuid, _as_of date) RETURNS TABLE(price numeric, price_currency_id uuid)
    LANGUAGE sql STABLE
    AS $$
  SELECT p.price, p.currency_id
  FROM market.price p
  WHERE p.asset_id = _asset_id
    AND p."interval" = 'day'
    AND p.ts::date <= _as_of
  ORDER BY p.ts DESC
  LIMIT 1
$$;


ALTER FUNCTION market.last_daily_price(_asset_id uuid, _as_of date) OWNER TO postgres;

--
-- TOC entry 459 (class 1255 OID 18722)
-- Name: refresh_mv_latest_daily_fx(); Type: FUNCTION; Schema: market; Owner: postgres
--

CREATE FUNCTION market.refresh_mv_latest_daily_fx() RETURNS void
    LANGUAGE sql
    AS $$
  REFRESH MATERIALIZED VIEW CONCURRENTLY market.fx_rate_daily;
  REFRESH MATERIALIZED VIEW CONCURRENTLY market.mv_latest_daily_fx;
$$;


ALTER FUNCTION market.refresh_mv_latest_daily_fx() OWNER TO postgres;

--
-- TOC entry 525 (class 1255 OID 18031)
-- Name: refresh_mv_latest_daily_price(); Type: FUNCTION; Schema: market; Owner: postgres
--

CREATE FUNCTION market.refresh_mv_latest_daily_price() RETURNS void
    LANGUAGE sql
    AS $$
  REFRESH MATERIALIZED VIEW CONCURRENTLY market.mv_latest_daily_price;
$$;


ALTER FUNCTION market.refresh_mv_latest_daily_price() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 231 (class 1259 OID 17874)
-- Name: auth_user; Type: TABLE; Schema: account; Owner: postgres
--

CREATE TABLE account.auth_user (
    id integer NOT NULL,
    username public.citext NOT NULL,
    email public.citext DEFAULT ''::public.citext NOT NULL,
    first_name text DEFAULT ''::text NOT NULL,
    last_name text DEFAULT ''::text NOT NULL,
    password text NOT NULL,
    is_staff boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_superuser boolean DEFAULT false NOT NULL,
    last_login timestamp with time zone,
    date_joined timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE account.auth_user OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 17873)
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: account; Owner: postgres
--

ALTER TABLE account.auth_user ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME account.auth_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 232 (class 1259 OID 17891)
-- Name: session_token; Type: TABLE; Schema: account; Owner: postgres
--

CREATE TABLE account.session_token (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer NOT NULL,
    digest character(64) NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    ip inet,
    user_agent text,
    CONSTRAINT ck_account_session_not_expired CHECK ((expires_at > issued_at))
);


ALTER TABLE account.session_token OWNER TO postgres;

--
-- TOC entry 266 (class 1259 OID 18528)
-- Name: benchmark; Type: TABLE; Schema: analytics; Owner: postgres
--

CREATE TABLE analytics.benchmark (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL
);


ALTER TABLE analytics.benchmark OWNER TO postgres;

--
-- TOC entry 267 (class 1259 OID 18538)
-- Name: benchmark_component; Type: TABLE; Schema: analytics; Owner: postgres
--

CREATE TABLE analytics.benchmark_component (
    benchmark_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    weight numeric(20,10) NOT NULL
);


ALTER TABLE analytics.benchmark_component OWNER TO postgres;

--
-- TOC entry 270 (class 1259 OID 18584)
-- Name: feature_view; Type: TABLE; Schema: analytics; Owner: postgres
--

CREATE TABLE analytics.feature_view (
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    as_of date NOT NULL,
    version text DEFAULT 'v1'::text NOT NULL,
    features jsonb NOT NULL,
    CONSTRAINT feature_view_entity_type_check CHECK ((entity_type = ANY (ARRAY['portfolio'::text, 'asset'::text, 'position'::text])))
);


ALTER TABLE analytics.feature_view OWNER TO postgres;

--
-- TOC entry 271 (class 1259 OID 18593)
-- Name: model_registry; Type: TABLE; Schema: analytics; Owner: postgres
--

CREATE TABLE analytics.model_registry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    version text NOT NULL,
    kind text NOT NULL,
    params jsonb DEFAULT '{}'::jsonb NOT NULL,
    trained_at timestamp with time zone,
    metrics jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE analytics.model_registry OWNER TO postgres;

--
-- TOC entry 243 (class 1259 OID 18112)
-- Name: portfolio_snapshot; Type: TABLE; Schema: analytics; Owner: postgres
--

CREATE TABLE analytics.portfolio_snapshot (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    portfolio_id uuid NOT NULL,
    as_of timestamp with time zone NOT NULL,
    total_value numeric(38,10) NOT NULL,
    pnl_1d numeric(38,10) NOT NULL,
    pnl_7d numeric(38,10) NOT NULL,
    pnl_30d numeric(38,10) NOT NULL
);


ALTER TABLE analytics.portfolio_snapshot OWNER TO postgres;

--
-- TOC entry 264 (class 1259 OID 18486)
-- Name: position_valuation_daily; Type: TABLE; Schema: analytics; Owner: postgres
--

CREATE TABLE analytics.position_valuation_daily (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    portfolio_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    as_of date NOT NULL,
    qty numeric(38,18) NOT NULL,
    price numeric(38,10) NOT NULL,
    price_currency_id uuid NOT NULL,
    fx_to_base numeric(38,10) NOT NULL,
    value_base numeric(38,10) NOT NULL,
    cost_basis_base numeric(38,10),
    realized_pnl_base numeric(38,10) DEFAULT 0,
    unrealized_pnl_base numeric(38,10) DEFAULT 0,
    income_acc_base numeric(38,10) DEFAULT 0,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE analytics.position_valuation_daily OWNER TO postgres;

--
-- TOC entry 272 (class 1259 OID 18605)
-- Name: prediction; Type: TABLE; Schema: analytics; Owner: postgres
--

CREATE TABLE analytics.prediction (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    model_id uuid NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    as_of timestamp with time zone NOT NULL,
    horizon text NOT NULL,
    target text NOT NULL,
    value numeric(38,10) NOT NULL,
    confidence numeric(10,5),
    features_version text,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT prediction_entity_type_check CHECK ((entity_type = ANY (ARRAY['portfolio'::text, 'asset'::text, 'position'::text])))
);


ALTER TABLE analytics.prediction OWNER TO postgres;

--
-- TOC entry 273 (class 1259 OID 18622)
-- Name: training_label; Type: TABLE; Schema: analytics; Owner: postgres
--

CREATE TABLE analytics.training_label (
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    as_of date NOT NULL,
    horizon text NOT NULL,
    label_name text NOT NULL,
    label_value numeric(38,10) NOT NULL,
    CONSTRAINT training_label_entity_type_check CHECK ((entity_type = ANY (ARRAY['portfolio'::text, 'asset'::text])))
);


ALTER TABLE analytics.training_label OWNER TO postgres;

--
-- TOC entry 247 (class 1259 OID 18179)
-- Name: audit_log; Type: TABLE; Schema: infra; Owner: postgres
--

CREATE TABLE infra.audit_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    action text NOT NULL,
    target_type text,
    target_id uuid,
    ip inet,
    user_agent text,
    details jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE infra.audit_log OWNER TO postgres;

--
-- TOC entry 248 (class 1259 OID 18195)
-- Name: outbox_event; Type: TABLE; Schema: infra; Owner: postgres
--

CREATE TABLE infra.outbox_event (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    topic text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone,
    attempts integer DEFAULT 0 NOT NULL
);


ALTER TABLE infra.outbox_event OWNER TO postgres;

--
-- TOC entry 262 (class 1259 OID 18446)
-- Name: account; Type: TABLE; Schema: integrations; Owner: postgres
--

CREATE TABLE integrations.account (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    integration_id uuid NOT NULL,
    provider_code text NOT NULL,
    ext_account_id text NOT NULL,
    display_name text,
    meta jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE integrations.account OWNER TO postgres;

--
-- TOC entry 263 (class 1259 OID 18462)
-- Name: account_portfolio; Type: TABLE; Schema: integrations; Owner: postgres
--

CREATE TABLE integrations.account_portfolio (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    account_id uuid NOT NULL,
    portfolio_id uuid NOT NULL,
    instrument_types text[],
    venue_codes text[],
    symbols_include text[],
    symbols_exclude text[],
    is_primary boolean DEFAULT true NOT NULL
);


ALTER TABLE integrations.account_portfolio OWNER TO postgres;

--
-- TOC entry 244 (class 1259 OID 18126)
-- Name: integration; Type: TABLE; Schema: integrations; Owner: postgres
--

CREATE TABLE integrations.integration (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer NOT NULL,
    provider text NOT NULL,
    display_name text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    credentials_encrypted text NOT NULL,
    last_sync_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE integrations.integration OWNER TO postgres;

--
-- TOC entry 245 (class 1259 OID 18144)
-- Name: sync_log; Type: TABLE; Schema: integrations; Owner: postgres
--

CREATE TABLE integrations.sync_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    integration_id uuid NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    status text DEFAULT 'running'::text NOT NULL,
    rows_in integer DEFAULT 0 NOT NULL,
    rows_upd integer DEFAULT 0 NOT NULL,
    rows_err integer DEFAULT 0 NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE integrations.sync_log OWNER TO postgres;

--
-- TOC entry 246 (class 1259 OID 18164)
-- Name: advice; Type: TABLE; Schema: llm; Owner: postgres
--

CREATE TABLE llm.advice (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    portfolio_id uuid NOT NULL,
    kind text NOT NULL,
    message text NOT NULL,
    score numeric(8,4),
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE llm.advice OWNER TO postgres;

--
-- TOC entry 235 (class 1259 OID 17933)
-- Name: asset; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.asset (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    class core.asset_class_enum NOT NULL,
    symbol text NOT NULL,
    name text NOT NULL,
    trading_currency_id uuid,
    isin text,
    exchange_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE market.asset OWNER TO postgres;

--
-- TOC entry 236 (class 1259 OID 17956)
-- Name: asset_identifier; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.asset_identifier (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    asset_id uuid NOT NULL,
    id_type text NOT NULL,
    id_value text NOT NULL
);


ALTER TABLE market.asset_identifier OWNER TO postgres;

--
-- TOC entry 265 (class 1259 OID 18516)
-- Name: asset_tag; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.asset_tag (
    asset_id uuid NOT NULL,
    tag_type text NOT NULL,
    tag_value text NOT NULL
);


ALTER TABLE market.asset_tag OWNER TO postgres;

--
-- TOC entry 274 (class 1259 OID 18648)
-- Name: bar; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.bar (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    asset_id uuid NOT NULL,
    ts timestamp with time zone NOT NULL,
    "interval" core.price_interval_enum NOT NULL,
    open numeric(38,10) NOT NULL,
    high numeric(38,10) NOT NULL,
    low numeric(38,10) NOT NULL,
    close numeric(38,10) NOT NULL,
    volume numeric(38,18),
    trades_count integer,
    currency_id uuid NOT NULL,
    provider_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT bar_ohlc_check CHECK (((low <= LEAST(open, close)) AND (high >= GREATEST(open, close)) AND (low <= high)))
);


ALTER TABLE market.bar OWNER TO postgres;

--
-- TOC entry 269 (class 1259 OID 18568)
-- Name: corporate_action; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.corporate_action (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    asset_id uuid NOT NULL,
    action_type text NOT NULL,
    ex_date date NOT NULL,
    ratio numeric(38,10),
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT corporate_action_action_type_check CHECK ((action_type = ANY (ARRAY['split'::text, 'merge'::text, 'symbol_change'::text, 'delisting'::text, 'spin_off'::text])))
);


ALTER TABLE market.corporate_action OWNER TO postgres;

--
-- TOC entry 233 (class 1259 OID 17909)
-- Name: currency; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.currency (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    decimals integer DEFAULT 2 NOT NULL,
    is_crypto boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE market.currency OWNER TO postgres;

--
-- TOC entry 234 (class 1259 OID 17922)
-- Name: exchange; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.exchange (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    country text,
    timezone text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE market.exchange OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 17998)
-- Name: fx_rate; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.fx_rate (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    base_currency_id uuid NOT NULL,
    quote_currency_id uuid NOT NULL,
    ts timestamp with time zone NOT NULL,
    rate numeric(38,10) NOT NULL,
    source text NOT NULL,
    provider_id uuid
);


ALTER TABLE market.fx_rate OWNER TO postgres;

--
-- TOC entry 276 (class 1259 OID 18712)
-- Name: fx_rate_daily; Type: MATERIALIZED VIEW; Schema: market; Owner: postgres
--

CREATE MATERIALIZED VIEW market.fx_rate_daily AS
 SELECT DISTINCT ON (base_currency_id, quote_currency_id, (date_trunc('day'::text, ts))) base_currency_id,
    quote_currency_id,
    (date_trunc('day'::text, ts))::date AS d,
    ts,
    rate
   FROM market.fx_rate
  ORDER BY base_currency_id, quote_currency_id, (date_trunc('day'::text, ts)), ts DESC
  WITH NO DATA;


ALTER MATERIALIZED VIEW market.fx_rate_daily OWNER TO postgres;

--
-- TOC entry 277 (class 1259 OID 18717)
-- Name: mv_latest_daily_fx; Type: MATERIALIZED VIEW; Schema: market; Owner: postgres
--

CREATE MATERIALIZED VIEW market.mv_latest_daily_fx AS
 SELECT DISTINCT ON (base_currency_id, quote_currency_id) base_currency_id,
    quote_currency_id,
    d,
    ts,
    rate
   FROM market.fx_rate_daily
  ORDER BY base_currency_id, quote_currency_id, d DESC
  WITH NO DATA;


ALTER MATERIALIZED VIEW market.mv_latest_daily_fx OWNER TO postgres;

--
-- TOC entry 237 (class 1259 OID 17973)
-- Name: price; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.price (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    asset_id uuid NOT NULL,
    ts timestamp with time zone NOT NULL,
    price numeric(38,10) NOT NULL,
    currency_id uuid NOT NULL,
    source text NOT NULL,
    "interval" core.price_interval_enum DEFAULT 'day'::core.price_interval_enum NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    provider_id uuid
);


ALTER TABLE market.price OWNER TO postgres;

--
-- TOC entry 239 (class 1259 OID 18019)
-- Name: mv_latest_daily_price; Type: MATERIALIZED VIEW; Schema: market; Owner: postgres
--

CREATE MATERIALIZED VIEW market.mv_latest_daily_price AS
 SELECT DISTINCT ON (asset_id) asset_id,
    ts,
    price,
    currency_id,
    source
   FROM market.price p
  WHERE ("interval" = 'day'::core.price_interval_enum)
  ORDER BY asset_id, ts DESC
  WITH NO DATA;


ALTER MATERIALIZED VIEW market.mv_latest_daily_price OWNER TO postgres;

--
-- TOC entry 275 (class 1259 OID 18678)
-- Name: quote; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.quote (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    asset_id uuid NOT NULL,
    ts timestamp with time zone NOT NULL,
    bid numeric(38,10),
    ask numeric(38,10),
    mid numeric(38,10) GENERATED ALWAYS AS (
CASE
    WHEN ((bid IS NOT NULL) AND (ask IS NOT NULL)) THEN ((bid + ask) / (2)::numeric)
    WHEN (bid IS NOT NULL) THEN bid
    WHEN (ask IS NOT NULL) THEN ask
    ELSE NULL::numeric
END) STORED,
    currency_id uuid NOT NULL,
    provider_id uuid,
    depth jsonb DEFAULT '{}'::jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT quote_bid_ask_check CHECK (((bid IS NULL) OR (ask IS NULL) OR (bid <= ask)))
);


ALTER TABLE market.quote OWNER TO postgres;

--
-- TOC entry 250 (class 1259 OID 18221)
-- Name: feed; Type: TABLE; Schema: marketdata; Owner: postgres
--

CREATE TABLE marketdata.feed (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    provider_id uuid NOT NULL,
    feed_type text NOT NULL,
    universe jsonb DEFAULT '{}'::jsonb NOT NULL,
    schedule text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    last_run_at timestamp with time zone,
    next_run_at timestamp with time zone,
    watermark_ts timestamp with time zone,
    CONSTRAINT feed_feed_type_check CHECK ((feed_type = ANY (ARRAY['price'::text, 'fx'::text, 'sentiment'::text, 'news'::text, 'corp_action'::text])))
);


ALTER TABLE marketdata.feed OWNER TO postgres;

--
-- TOC entry 254 (class 1259 OID 18295)
-- Name: fetch_log; Type: TABLE; Schema: marketdata; Owner: postgres
--

CREATE TABLE marketdata.fetch_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    feed_id uuid NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    status text DEFAULT 'running'::text NOT NULL,
    rows_in integer DEFAULT 0 NOT NULL,
    rows_upd integer DEFAULT 0 NOT NULL,
    rows_err integer DEFAULT 0 NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE marketdata.fetch_log OWNER TO postgres;

--
-- TOC entry 249 (class 1259 OID 18209)
-- Name: provider; Type: TABLE; Schema: marketdata; Owner: postgres
--

CREATE TABLE marketdata.provider (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    kind text NOT NULL,
    sla text,
    cost jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE marketdata.provider OWNER TO postgres;

--
-- TOC entry 251 (class 1259 OID 18239)
-- Name: symbol_map; Type: TABLE; Schema: marketdata; Owner: postgres
--

CREATE TABLE marketdata.symbol_map (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    provider_id uuid NOT NULL,
    external_symbol text NOT NULL,
    exchange_code text,
    asset_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    valid_from date DEFAULT '1970-01-01'::date NOT NULL,
    valid_to date DEFAULT '9999-12-31'::date NOT NULL,
    CONSTRAINT ck_symbol_map_valid CHECK ((valid_from <= valid_to))
);


ALTER TABLE marketdata.symbol_map OWNER TO postgres;

--
-- TOC entry 240 (class 1259 OID 18032)
-- Name: portfolio; Type: TABLE; Schema: portfolio; Owner: postgres
--

CREATE TABLE portfolio.portfolio (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer NOT NULL,
    name text NOT NULL,
    base_currency_id uuid NOT NULL,
    settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE portfolio.portfolio OWNER TO postgres;

--
-- TOC entry 268 (class 1259 OID 18553)
-- Name: portfolio_benchmark; Type: TABLE; Schema: portfolio; Owner: postgres
--

CREATE TABLE portfolio.portfolio_benchmark (
    portfolio_id uuid NOT NULL,
    benchmark_id uuid NOT NULL
);


ALTER TABLE portfolio.portfolio_benchmark OWNER TO postgres;

--
-- TOC entry 241 (class 1259 OID 18055)
-- Name: position; Type: TABLE; Schema: portfolio; Owner: postgres
--

CREATE TABLE portfolio."position" (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    portfolio_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    qty numeric(38,18) DEFAULT 0 NOT NULL,
    cost_basis numeric(38,10) DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE portfolio."position" OWNER TO postgres;

--
-- TOC entry 242 (class 1259 OID 18076)
-- Name: transaction; Type: TABLE; Schema: portfolio; Owner: postgres
--

CREATE TABLE portfolio.transaction (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    portfolio_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    tx_type core.transaction_type_enum NOT NULL,
    tx_time timestamp with time zone NOT NULL,
    quantity numeric(38,18) DEFAULT 0 NOT NULL,
    price numeric(38,10),
    price_currency_id uuid,
    fee numeric(38,10) DEFAULT 0 NOT NULL,
    notes text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    linked_tx_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT transaction_check CHECK (((price IS NULL) = (price_currency_id IS NULL)))
);


ALTER TABLE portfolio.transaction OWNER TO postgres;

--
-- TOC entry 260 (class 1259 OID 18413)
-- Name: balances_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.balances_raw (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    integration_id uuid NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb NOT NULL,
    ext_account_id text NOT NULL,
    currency_code text NOT NULL,
    total numeric(38,10),
    available numeric(38,10),
    locked numeric(38,10)
);


ALTER TABLE staging.balances_raw OWNER TO postgres;

--
-- TOC entry 255 (class 1259 OID 18331)
-- Name: broker_positions_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.broker_positions_raw (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    integration_id uuid NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb NOT NULL,
    ext_sub_account text NOT NULL,
    ext_ticker text NOT NULL,
    ext_exchange text,
    ext_term text,
    ext_expire_date date
);


ALTER TABLE staging.broker_positions_raw OWNER TO postgres;

--
-- TOC entry 258 (class 1259 OID 18379)
-- Name: cashflows_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.cashflows_raw (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    integration_id uuid NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb NOT NULL,
    ext_account_id text NOT NULL,
    ext_cashflow_id text NOT NULL,
    occurred_at timestamp with time zone NOT NULL,
    currency_code text NOT NULL,
    amount numeric(38,10) NOT NULL,
    kind text
);


ALTER TABLE staging.cashflows_raw OWNER TO postgres;

--
-- TOC entry 261 (class 1259 OID 18429)
-- Name: funding_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.funding_raw (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    integration_id uuid NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb NOT NULL,
    ext_account_id text NOT NULL,
    ext_symbol text NOT NULL,
    venue_code text,
    ts timestamp with time zone NOT NULL,
    funding_rate numeric(16,8),
    funding_fee numeric(38,10),
    currency_code text
);


ALTER TABLE staging.funding_raw OWNER TO postgres;

--
-- TOC entry 253 (class 1259 OID 18278)
-- Name: fx_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.fx_raw (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    provider_id uuid NOT NULL,
    base_code text NOT NULL,
    quote_code text NOT NULL,
    ts timestamp with time zone NOT NULL,
    rate numeric(38,10) NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    landed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.fx_raw OWNER TO postgres;

--
-- TOC entry 259 (class 1259 OID 18396)
-- Name: orders_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.orders_raw (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    integration_id uuid NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb NOT NULL,
    ext_account_id text NOT NULL,
    ext_order_id text NOT NULL,
    ext_symbol text NOT NULL,
    venue_code text,
    instrument_type text,
    status text,
    side text,
    order_type text,
    price numeric(38,10),
    quantity numeric(38,18),
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE staging.orders_raw OWNER TO postgres;

--
-- TOC entry 256 (class 1259 OID 18346)
-- Name: positions_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.positions_raw (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    integration_id uuid NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb NOT NULL,
    ext_account_id text NOT NULL,
    ext_symbol text NOT NULL,
    venue_code text,
    instrument_type text,
    expire_date date,
    position_side text,
    quantity numeric(38,18),
    entry_price numeric(38,10),
    currency_code text
);


ALTER TABLE staging.positions_raw OWNER TO postgres;

--
-- TOC entry 252 (class 1259 OID 18261)
-- Name: price_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.price_raw (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    provider_id uuid NOT NULL,
    external_symbol text NOT NULL,
    ts timestamp with time zone NOT NULL,
    price numeric(38,10) NOT NULL,
    currency_code text NOT NULL,
    "interval" text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    landed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.price_raw OWNER TO postgres;

--
-- TOC entry 257 (class 1259 OID 18362)
-- Name: trades_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.trades_raw (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    integration_id uuid NOT NULL,
    pulled_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb NOT NULL,
    ext_account_id text NOT NULL,
    ext_trade_id text NOT NULL,
    ext_symbol text NOT NULL,
    venue_code text,
    instrument_type text,
    trade_time timestamp with time zone NOT NULL,
    side text,
    price numeric(38,10),
    quantity numeric(38,18),
    currency_code text
);


ALTER TABLE staging.trades_raw OWNER TO postgres;

--
-- TOC entry 5867 (class 0 OID 17874)
-- Dependencies: 231
-- Data for Name: auth_user; Type: TABLE DATA; Schema: account; Owner: postgres
--

COPY account.auth_user (id, username, email, first_name, last_name, password, is_staff, is_active, is_superuser, last_login, date_joined) FROM stdin;
\.


--
-- TOC entry 5868 (class 0 OID 17891)
-- Dependencies: 232
-- Data for Name: session_token; Type: TABLE DATA; Schema: account; Owner: postgres
--

COPY account.session_token (id, user_id, digest, issued_at, expires_at, revoked_at, ip, user_agent) FROM stdin;
\.


--
-- TOC entry 5902 (class 0 OID 18528)
-- Dependencies: 266
-- Data for Name: benchmark; Type: TABLE DATA; Schema: analytics; Owner: postgres
--

COPY analytics.benchmark (id, code, name) FROM stdin;
\.


--
-- TOC entry 5903 (class 0 OID 18538)
-- Dependencies: 267
-- Data for Name: benchmark_component; Type: TABLE DATA; Schema: analytics; Owner: postgres
--

COPY analytics.benchmark_component (benchmark_id, asset_id, weight) FROM stdin;
\.


--
-- TOC entry 5906 (class 0 OID 18584)
-- Dependencies: 270
-- Data for Name: feature_view; Type: TABLE DATA; Schema: analytics; Owner: postgres
--

COPY analytics.feature_view (entity_type, entity_id, as_of, version, features) FROM stdin;
\.


--
-- TOC entry 5907 (class 0 OID 18593)
-- Dependencies: 271
-- Data for Name: model_registry; Type: TABLE DATA; Schema: analytics; Owner: postgres
--

COPY analytics.model_registry (id, name, version, kind, params, trained_at, metrics) FROM stdin;
\.


--
-- TOC entry 5879 (class 0 OID 18112)
-- Dependencies: 243
-- Data for Name: portfolio_snapshot; Type: TABLE DATA; Schema: analytics; Owner: postgres
--

COPY analytics.portfolio_snapshot (id, portfolio_id, as_of, total_value, pnl_1d, pnl_7d, pnl_30d) FROM stdin;
\.


--
-- TOC entry 5900 (class 0 OID 18486)
-- Dependencies: 264
-- Data for Name: position_valuation_daily; Type: TABLE DATA; Schema: analytics; Owner: postgres
--

COPY analytics.position_valuation_daily (id, portfolio_id, asset_id, as_of, qty, price, price_currency_id, fx_to_base, value_base, cost_basis_base, realized_pnl_base, unrealized_pnl_base, income_acc_base, metadata) FROM stdin;
\.


--
-- TOC entry 5908 (class 0 OID 18605)
-- Dependencies: 272
-- Data for Name: prediction; Type: TABLE DATA; Schema: analytics; Owner: postgres
--

COPY analytics.prediction (id, model_id, entity_type, entity_id, as_of, horizon, target, value, confidence, features_version, payload) FROM stdin;
\.


--
-- TOC entry 5909 (class 0 OID 18622)
-- Dependencies: 273
-- Data for Name: training_label; Type: TABLE DATA; Schema: analytics; Owner: postgres
--

COPY analytics.training_label (entity_type, entity_id, as_of, horizon, label_name, label_value) FROM stdin;
\.


--
-- TOC entry 5883 (class 0 OID 18179)
-- Dependencies: 247
-- Data for Name: audit_log; Type: TABLE DATA; Schema: infra; Owner: postgres
--

COPY infra.audit_log (id, user_id, ts, action, target_type, target_id, ip, user_agent, details) FROM stdin;
\.


--
-- TOC entry 5884 (class 0 OID 18195)
-- Dependencies: 248
-- Data for Name: outbox_event; Type: TABLE DATA; Schema: infra; Owner: postgres
--

COPY infra.outbox_event (id, topic, payload, created_at, processed_at, attempts) FROM stdin;
\.


--
-- TOC entry 5898 (class 0 OID 18446)
-- Dependencies: 262
-- Data for Name: account; Type: TABLE DATA; Schema: integrations; Owner: postgres
--

COPY integrations.account (id, integration_id, provider_code, ext_account_id, display_name, meta) FROM stdin;
\.


--
-- TOC entry 5899 (class 0 OID 18462)
-- Dependencies: 263
-- Data for Name: account_portfolio; Type: TABLE DATA; Schema: integrations; Owner: postgres
--

COPY integrations.account_portfolio (id, account_id, portfolio_id, instrument_types, venue_codes, symbols_include, symbols_exclude, is_primary) FROM stdin;
\.


--
-- TOC entry 5880 (class 0 OID 18126)
-- Dependencies: 244
-- Data for Name: integration; Type: TABLE DATA; Schema: integrations; Owner: postgres
--

COPY integrations.integration (id, user_id, provider, display_name, status, credentials_encrypted, last_sync_at, created_at, updated_at) FROM stdin;
\.


--
-- TOC entry 5881 (class 0 OID 18144)
-- Dependencies: 245
-- Data for Name: sync_log; Type: TABLE DATA; Schema: integrations; Owner: postgres
--

COPY integrations.sync_log (id, integration_id, started_at, finished_at, status, rows_in, rows_upd, rows_err, details) FROM stdin;
\.


--
-- TOC entry 5882 (class 0 OID 18164)
-- Dependencies: 246
-- Data for Name: advice; Type: TABLE DATA; Schema: llm; Owner: postgres
--

COPY llm.advice (id, portfolio_id, kind, message, score, payload, created_at) FROM stdin;
\.


--
-- TOC entry 5871 (class 0 OID 17933)
-- Dependencies: 235
-- Data for Name: asset; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.asset (id, class, symbol, name, trading_currency_id, isin, exchange_id, metadata, is_active, created_at) FROM stdin;
\.


--
-- TOC entry 5872 (class 0 OID 17956)
-- Dependencies: 236
-- Data for Name: asset_identifier; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.asset_identifier (id, asset_id, id_type, id_value) FROM stdin;
\.


--
-- TOC entry 5901 (class 0 OID 18516)
-- Dependencies: 265
-- Data for Name: asset_tag; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.asset_tag (asset_id, tag_type, tag_value) FROM stdin;
\.


--
-- TOC entry 5910 (class 0 OID 18648)
-- Dependencies: 274
-- Data for Name: bar; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.bar (id, asset_id, ts, "interval", open, high, low, close, volume, trades_count, currency_id, provider_id, metadata, created_at) FROM stdin;
\.


--
-- TOC entry 5905 (class 0 OID 18568)
-- Dependencies: 269
-- Data for Name: corporate_action; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.corporate_action (id, asset_id, action_type, ex_date, ratio, payload) FROM stdin;
\.


--
-- TOC entry 5869 (class 0 OID 17909)
-- Dependencies: 233
-- Data for Name: currency; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.currency (id, code, name, decimals, is_crypto, created_at) FROM stdin;
\.


--
-- TOC entry 5870 (class 0 OID 17922)
-- Dependencies: 234
-- Data for Name: exchange; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.exchange (id, code, name, country, timezone, created_at) FROM stdin;
\.


--
-- TOC entry 5874 (class 0 OID 17998)
-- Dependencies: 238
-- Data for Name: fx_rate; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.fx_rate (id, base_currency_id, quote_currency_id, ts, rate, source, provider_id) FROM stdin;
\.


--
-- TOC entry 5873 (class 0 OID 17973)
-- Dependencies: 237
-- Data for Name: price; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.price (id, asset_id, ts, price, currency_id, source, "interval", metadata, created_at, provider_id) FROM stdin;
\.


--
-- TOC entry 5911 (class 0 OID 18678)
-- Dependencies: 275
-- Data for Name: quote; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.quote (id, asset_id, ts, bid, ask, currency_id, provider_id, depth, metadata, created_at) FROM stdin;
\.


--
-- TOC entry 5886 (class 0 OID 18221)
-- Dependencies: 250
-- Data for Name: feed; Type: TABLE DATA; Schema: marketdata; Owner: postgres
--

COPY marketdata.feed (id, provider_id, feed_type, universe, schedule, enabled, last_run_at, next_run_at, watermark_ts) FROM stdin;
\.


--
-- TOC entry 5890 (class 0 OID 18295)
-- Dependencies: 254
-- Data for Name: fetch_log; Type: TABLE DATA; Schema: marketdata; Owner: postgres
--

COPY marketdata.fetch_log (id, feed_id, started_at, finished_at, status, rows_in, rows_upd, rows_err, details) FROM stdin;
\.


--
-- TOC entry 5885 (class 0 OID 18209)
-- Dependencies: 249
-- Data for Name: provider; Type: TABLE DATA; Schema: marketdata; Owner: postgres
--

COPY marketdata.provider (id, code, kind, sla, cost, created_at) FROM stdin;
\.


--
-- TOC entry 5887 (class 0 OID 18239)
-- Dependencies: 251
-- Data for Name: symbol_map; Type: TABLE DATA; Schema: marketdata; Owner: postgres
--

COPY marketdata.symbol_map (id, provider_id, external_symbol, exchange_code, asset_id, metadata, valid_from, valid_to) FROM stdin;
\.


--
-- TOC entry 5876 (class 0 OID 18032)
-- Dependencies: 240
-- Data for Name: portfolio; Type: TABLE DATA; Schema: portfolio; Owner: postgres
--

COPY portfolio.portfolio (id, user_id, name, base_currency_id, settings, created_at, updated_at) FROM stdin;
\.


--
-- TOC entry 5904 (class 0 OID 18553)
-- Dependencies: 268
-- Data for Name: portfolio_benchmark; Type: TABLE DATA; Schema: portfolio; Owner: postgres
--

COPY portfolio.portfolio_benchmark (portfolio_id, benchmark_id) FROM stdin;
\.


--
-- TOC entry 5877 (class 0 OID 18055)
-- Dependencies: 241
-- Data for Name: position; Type: TABLE DATA; Schema: portfolio; Owner: postgres
--

COPY portfolio."position" (id, portfolio_id, asset_id, qty, cost_basis, updated_at) FROM stdin;
\.


--
-- TOC entry 5878 (class 0 OID 18076)
-- Dependencies: 242
-- Data for Name: transaction; Type: TABLE DATA; Schema: portfolio; Owner: postgres
--

COPY portfolio.transaction (id, portfolio_id, asset_id, tx_type, tx_time, quantity, price, price_currency_id, fee, notes, metadata, linked_tx_id, created_at) FROM stdin;
\.


--
-- TOC entry 5896 (class 0 OID 18413)
-- Dependencies: 260
-- Data for Name: balances_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.balances_raw (id, integration_id, pulled_at, payload, ext_account_id, currency_code, total, available, locked) FROM stdin;
\.


--
-- TOC entry 5891 (class 0 OID 18331)
-- Dependencies: 255
-- Data for Name: broker_positions_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.broker_positions_raw (id, integration_id, pulled_at, payload, ext_sub_account, ext_ticker, ext_exchange, ext_term, ext_expire_date) FROM stdin;
\.


--
-- TOC entry 5894 (class 0 OID 18379)
-- Dependencies: 258
-- Data for Name: cashflows_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.cashflows_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_cashflow_id, occurred_at, currency_code, amount, kind) FROM stdin;
\.


--
-- TOC entry 5897 (class 0 OID 18429)
-- Dependencies: 261
-- Data for Name: funding_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.funding_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_symbol, venue_code, ts, funding_rate, funding_fee, currency_code) FROM stdin;
\.


--
-- TOC entry 5889 (class 0 OID 18278)
-- Dependencies: 253
-- Data for Name: fx_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.fx_raw (id, provider_id, base_code, quote_code, ts, rate, payload, landed_at) FROM stdin;
\.


--
-- TOC entry 5895 (class 0 OID 18396)
-- Dependencies: 259
-- Data for Name: orders_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.orders_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_order_id, ext_symbol, venue_code, instrument_type, status, side, order_type, price, quantity, created_at, updated_at) FROM stdin;
\.


--
-- TOC entry 5892 (class 0 OID 18346)
-- Dependencies: 256
-- Data for Name: positions_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.positions_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_symbol, venue_code, instrument_type, expire_date, position_side, quantity, entry_price, currency_code) FROM stdin;
\.


--
-- TOC entry 5888 (class 0 OID 18261)
-- Dependencies: 252
-- Data for Name: price_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.price_raw (id, provider_id, external_symbol, ts, price, currency_code, "interval", payload, landed_at) FROM stdin;
\.


--
-- TOC entry 5893 (class 0 OID 18362)
-- Dependencies: 257
-- Data for Name: trades_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.trades_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_trade_id, ext_symbol, venue_code, instrument_type, trade_time, side, price, quantity, currency_code) FROM stdin;
\.


--
-- TOC entry 5922 (class 0 OID 0)
-- Dependencies: 230
-- Name: auth_user_id_seq; Type: SEQUENCE SET; Schema: account; Owner: postgres
--

SELECT pg_catalog.setval('account.auth_user_id_seq', 1, false);


--
-- TOC entry 5476 (class 2606 OID 17887)
-- Name: auth_user auth_user_pkey; Type: CONSTRAINT; Schema: account; Owner: postgres
--

ALTER TABLE ONLY account.auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- TOC entry 5478 (class 2606 OID 17889)
-- Name: auth_user auth_user_username_key; Type: CONSTRAINT; Schema: account; Owner: postgres
--

ALTER TABLE ONLY account.auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- TOC entry 5482 (class 2606 OID 17902)
-- Name: session_token session_token_digest_key; Type: CONSTRAINT; Schema: account; Owner: postgres
--

ALTER TABLE ONLY account.session_token
    ADD CONSTRAINT session_token_digest_key UNIQUE (digest);


--
-- TOC entry 5484 (class 2606 OID 17900)
-- Name: session_token session_token_pkey; Type: CONSTRAINT; Schema: account; Owner: postgres
--

ALTER TABLE ONLY account.session_token
    ADD CONSTRAINT session_token_pkey PRIMARY KEY (id);


--
-- TOC entry 5625 (class 2606 OID 18537)
-- Name: benchmark benchmark_code_key; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.benchmark
    ADD CONSTRAINT benchmark_code_key UNIQUE (code);


--
-- TOC entry 5629 (class 2606 OID 18542)
-- Name: benchmark_component benchmark_component_pkey; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.benchmark_component
    ADD CONSTRAINT benchmark_component_pkey PRIMARY KEY (benchmark_id, asset_id);


--
-- TOC entry 5627 (class 2606 OID 18535)
-- Name: benchmark benchmark_pkey; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.benchmark
    ADD CONSTRAINT benchmark_pkey PRIMARY KEY (id);


--
-- TOC entry 5636 (class 2606 OID 18592)
-- Name: feature_view feature_view_pkey; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.feature_view
    ADD CONSTRAINT feature_view_pkey PRIMARY KEY (entity_type, entity_id, as_of, version);


--
-- TOC entry 5638 (class 2606 OID 18604)
-- Name: model_registry model_registry_name_version_key; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.model_registry
    ADD CONSTRAINT model_registry_name_version_key UNIQUE (name, version);


--
-- TOC entry 5640 (class 2606 OID 18602)
-- Name: model_registry model_registry_pkey; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.model_registry
    ADD CONSTRAINT model_registry_pkey PRIMARY KEY (id);


--
-- TOC entry 5532 (class 2606 OID 18117)
-- Name: portfolio_snapshot portfolio_snapshot_pkey; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.portfolio_snapshot
    ADD CONSTRAINT portfolio_snapshot_pkey PRIMARY KEY (id);


--
-- TOC entry 5534 (class 2606 OID 18119)
-- Name: portfolio_snapshot portfolio_snapshot_portfolio_id_as_of_key; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.portfolio_snapshot
    ADD CONSTRAINT portfolio_snapshot_portfolio_id_as_of_key UNIQUE (portfolio_id, as_of);


--
-- TOC entry 5619 (class 2606 OID 18497)
-- Name: position_valuation_daily position_valuation_daily_pkey; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.position_valuation_daily
    ADD CONSTRAINT position_valuation_daily_pkey PRIMARY KEY (id);


--
-- TOC entry 5621 (class 2606 OID 18499)
-- Name: position_valuation_daily position_valuation_daily_portfolio_id_asset_id_as_of_key; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.position_valuation_daily
    ADD CONSTRAINT position_valuation_daily_portfolio_id_asset_id_as_of_key UNIQUE (portfolio_id, asset_id, as_of);


--
-- TOC entry 5642 (class 2606 OID 18616)
-- Name: prediction prediction_model_id_entity_type_entity_id_as_of_horizon_tar_key; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.prediction
    ADD CONSTRAINT prediction_model_id_entity_type_entity_id_as_of_horizon_tar_key UNIQUE (model_id, entity_type, entity_id, as_of, horizon, target);


--
-- TOC entry 5644 (class 2606 OID 18614)
-- Name: prediction prediction_pkey; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.prediction
    ADD CONSTRAINT prediction_pkey PRIMARY KEY (id);


--
-- TOC entry 5646 (class 2606 OID 18629)
-- Name: training_label training_label_pkey; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.training_label
    ADD CONSTRAINT training_label_pkey PRIMARY KEY (entity_type, entity_id, as_of, horizon, label_name);


--
-- TOC entry 5545 (class 2606 OID 18188)
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: infra; Owner: postgres
--

ALTER TABLE ONLY infra.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5549 (class 2606 OID 18204)
-- Name: outbox_event outbox_event_pkey; Type: CONSTRAINT; Schema: infra; Owner: postgres
--

ALTER TABLE ONLY infra.outbox_event
    ADD CONSTRAINT outbox_event_pkey PRIMARY KEY (id);


--
-- TOC entry 5609 (class 2606 OID 18456)
-- Name: account account_integration_id_ext_account_id_key; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account
    ADD CONSTRAINT account_integration_id_ext_account_id_key UNIQUE (integration_id, ext_account_id);


--
-- TOC entry 5611 (class 2606 OID 18454)
-- Name: account account_pkey; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account
    ADD CONSTRAINT account_pkey PRIMARY KEY (id);


--
-- TOC entry 5613 (class 2606 OID 18472)
-- Name: account_portfolio account_portfolio_account_id_portfolio_id_key; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account_portfolio
    ADD CONSTRAINT account_portfolio_account_id_portfolio_id_key UNIQUE (account_id, portfolio_id);


--
-- TOC entry 5615 (class 2606 OID 18470)
-- Name: account_portfolio account_portfolio_pkey; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account_portfolio
    ADD CONSTRAINT account_portfolio_pkey PRIMARY KEY (id);


--
-- TOC entry 5536 (class 2606 OID 18136)
-- Name: integration integration_pkey; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.integration
    ADD CONSTRAINT integration_pkey PRIMARY KEY (id);


--
-- TOC entry 5538 (class 2606 OID 18138)
-- Name: integration integration_user_id_provider_display_name_key; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.integration
    ADD CONSTRAINT integration_user_id_provider_display_name_key UNIQUE (user_id, provider, display_name);


--
-- TOC entry 5541 (class 2606 OID 18157)
-- Name: sync_log sync_log_pkey; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.sync_log
    ADD CONSTRAINT sync_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5543 (class 2606 OID 18173)
-- Name: advice advice_pkey; Type: CONSTRAINT; Schema: llm; Owner: postgres
--

ALTER TABLE ONLY llm.advice
    ADD CONSTRAINT advice_pkey PRIMARY KEY (id);


--
-- TOC entry 5498 (class 2606 OID 17967)
-- Name: asset_identifier asset_identifier_asset_id_id_type_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_identifier
    ADD CONSTRAINT asset_identifier_asset_id_id_type_key UNIQUE (asset_id, id_type);


--
-- TOC entry 5500 (class 2606 OID 17965)
-- Name: asset_identifier asset_identifier_id_type_id_value_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_identifier
    ADD CONSTRAINT asset_identifier_id_type_id_value_key UNIQUE (id_type, id_value);


--
-- TOC entry 5502 (class 2606 OID 17963)
-- Name: asset_identifier asset_identifier_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_identifier
    ADD CONSTRAINT asset_identifier_pkey PRIMARY KEY (id);


--
-- TOC entry 5494 (class 2606 OID 17943)
-- Name: asset asset_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset
    ADD CONSTRAINT asset_pkey PRIMARY KEY (id);


--
-- TOC entry 5623 (class 2606 OID 18522)
-- Name: asset_tag asset_tag_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_tag
    ADD CONSTRAINT asset_tag_pkey PRIMARY KEY (asset_id, tag_type, tag_value);


--
-- TOC entry 5648 (class 2606 OID 18658)
-- Name: bar bar_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.bar
    ADD CONSTRAINT bar_pkey PRIMARY KEY (id);


--
-- TOC entry 5633 (class 2606 OID 18577)
-- Name: corporate_action corporate_action_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.corporate_action
    ADD CONSTRAINT corporate_action_pkey PRIMARY KEY (id);


--
-- TOC entry 5486 (class 2606 OID 17921)
-- Name: currency currency_code_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.currency
    ADD CONSTRAINT currency_code_key UNIQUE (code);


--
-- TOC entry 5488 (class 2606 OID 17919)
-- Name: currency currency_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.currency
    ADD CONSTRAINT currency_pkey PRIMARY KEY (id);


--
-- TOC entry 5490 (class 2606 OID 17932)
-- Name: exchange exchange_code_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.exchange
    ADD CONSTRAINT exchange_code_key UNIQUE (code);


--
-- TOC entry 5492 (class 2606 OID 17930)
-- Name: exchange exchange_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.exchange
    ADD CONSTRAINT exchange_pkey PRIMARY KEY (id);


--
-- TOC entry 5511 (class 2606 OID 18007)
-- Name: fx_rate fx_rate_base_currency_id_quote_currency_id_ts_source_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.fx_rate
    ADD CONSTRAINT fx_rate_base_currency_id_quote_currency_id_ts_source_key UNIQUE (base_currency_id, quote_currency_id, ts, source);


--
-- TOC entry 5513 (class 2606 OID 18005)
-- Name: fx_rate fx_rate_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.fx_rate
    ADD CONSTRAINT fx_rate_pkey PRIMARY KEY (id);


--
-- TOC entry 5507 (class 2606 OID 17985)
-- Name: price price_asset_id_ts_source_interval_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.price
    ADD CONSTRAINT price_asset_id_ts_source_interval_key UNIQUE (asset_id, ts, source, "interval");


--
-- TOC entry 5509 (class 2606 OID 17983)
-- Name: price price_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.price
    ADD CONSTRAINT price_pkey PRIMARY KEY (id);


--
-- TOC entry 5656 (class 2606 OID 18690)
-- Name: quote quote_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.quote
    ADD CONSTRAINT quote_pkey PRIMARY KEY (id);


--
-- TOC entry 5496 (class 2606 OID 17945)
-- Name: asset uq_market_asset_symbol_exch; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset
    ADD CONSTRAINT uq_market_asset_symbol_exch UNIQUE (symbol, exchange_id);


--
-- TOC entry 5561 (class 2606 OID 19383)
-- Name: symbol_map ex_symbol_map_no_overlap; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT ex_symbol_map_no_overlap EXCLUDE USING gist (provider_id WITH =, external_symbol WITH =, COALESCE(exchange_code, ''::text) WITH =, daterange(valid_from, valid_to, '[]'::text) WITH &&);


--
-- TOC entry 5555 (class 2606 OID 18231)
-- Name: feed feed_pkey; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.feed
    ADD CONSTRAINT feed_pkey PRIMARY KEY (id);


--
-- TOC entry 5557 (class 2606 OID 18233)
-- Name: feed feed_provider_id_feed_type_universe_key; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.feed
    ADD CONSTRAINT feed_provider_id_feed_type_universe_key UNIQUE (provider_id, feed_type, universe);


--
-- TOC entry 5577 (class 2606 OID 18308)
-- Name: fetch_log fetch_log_pkey; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.fetch_log
    ADD CONSTRAINT fetch_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5551 (class 2606 OID 18220)
-- Name: provider provider_code_key; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.provider
    ADD CONSTRAINT provider_code_key UNIQUE (code);


--
-- TOC entry 5553 (class 2606 OID 18218)
-- Name: provider provider_pkey; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.provider
    ADD CONSTRAINT provider_pkey PRIMARY KEY (id);


--
-- TOC entry 5564 (class 2606 OID 18248)
-- Name: symbol_map symbol_map_pkey; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT symbol_map_pkey PRIMARY KEY (id);


--
-- TOC entry 5566 (class 2606 OID 18260)
-- Name: symbol_map ux_symbol_map; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT ux_symbol_map UNIQUE (provider_id, external_symbol, exchange_code);


--
-- TOC entry 5631 (class 2606 OID 18557)
-- Name: portfolio_benchmark portfolio_benchmark_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio_benchmark
    ADD CONSTRAINT portfolio_benchmark_pkey PRIMARY KEY (portfolio_id);


--
-- TOC entry 5518 (class 2606 OID 18042)
-- Name: portfolio portfolio_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio
    ADD CONSTRAINT portfolio_pkey PRIMARY KEY (id);


--
-- TOC entry 5520 (class 2606 OID 18044)
-- Name: portfolio portfolio_user_id_name_key; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio
    ADD CONSTRAINT portfolio_user_id_name_key UNIQUE (user_id, name);


--
-- TOC entry 5522 (class 2606 OID 18063)
-- Name: position position_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio."position"
    ADD CONSTRAINT position_pkey PRIMARY KEY (id);


--
-- TOC entry 5524 (class 2606 OID 18065)
-- Name: position position_portfolio_id_asset_id_key; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio."position"
    ADD CONSTRAINT position_portfolio_id_asset_id_key UNIQUE (portfolio_id, asset_id);


--
-- TOC entry 5529 (class 2606 OID 18088)
-- Name: transaction transaction_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_pkey PRIMARY KEY (id);


--
-- TOC entry 5601 (class 2606 OID 18421)
-- Name: balances_raw balances_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.balances_raw
    ADD CONSTRAINT balances_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5579 (class 2606 OID 18339)
-- Name: broker_positions_raw broker_positions_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.broker_positions_raw
    ADD CONSTRAINT broker_positions_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5591 (class 2606 OID 18387)
-- Name: cashflows_raw cashflows_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.cashflows_raw
    ADD CONSTRAINT cashflows_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5605 (class 2606 OID 18437)
-- Name: funding_raw funding_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.funding_raw
    ADD CONSTRAINT funding_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5572 (class 2606 OID 18287)
-- Name: fx_raw fx_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.fx_raw
    ADD CONSTRAINT fx_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5574 (class 2606 OID 18289)
-- Name: fx_raw fx_raw_provider_id_base_code_quote_code_ts_key; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.fx_raw
    ADD CONSTRAINT fx_raw_provider_id_base_code_quote_code_ts_key UNIQUE (provider_id, base_code, quote_code, ts);


--
-- TOC entry 5597 (class 2606 OID 18404)
-- Name: orders_raw orders_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.orders_raw
    ADD CONSTRAINT orders_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5583 (class 2606 OID 18354)
-- Name: positions_raw positions_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.positions_raw
    ADD CONSTRAINT positions_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5568 (class 2606 OID 18270)
-- Name: price_raw price_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.price_raw
    ADD CONSTRAINT price_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5570 (class 2606 OID 18272)
-- Name: price_raw price_raw_provider_id_external_symbol_ts_interval_key; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.price_raw
    ADD CONSTRAINT price_raw_provider_id_external_symbol_ts_interval_key UNIQUE (provider_id, external_symbol, ts, "interval");


--
-- TOC entry 5587 (class 2606 OID 18370)
-- Name: trades_raw trades_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.trades_raw
    ADD CONSTRAINT trades_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5594 (class 2606 OID 18389)
-- Name: cashflows_raw uq_cashflows_raw; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.cashflows_raw
    ADD CONSTRAINT uq_cashflows_raw UNIQUE (integration_id, ext_cashflow_id);


--
-- TOC entry 5599 (class 2606 OID 18406)
-- Name: orders_raw uq_orders_raw; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.orders_raw
    ADD CONSTRAINT uq_orders_raw UNIQUE (integration_id, ext_order_id);


--
-- TOC entry 5589 (class 2606 OID 18372)
-- Name: trades_raw uq_trades_raw; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.trades_raw
    ADD CONSTRAINT uq_trades_raw UNIQUE (integration_id, ext_trade_id);


--
-- TOC entry 5480 (class 1259 OID 17908)
-- Name: ix_account_session_user_active; Type: INDEX; Schema: account; Owner: postgres
--

CREATE INDEX ix_account_session_user_active ON account.session_token USING btree (user_id, expires_at) WHERE (revoked_at IS NULL);


--
-- TOC entry 5479 (class 1259 OID 17890)
-- Name: ix_auth_user_email; Type: INDEX; Schema: account; Owner: postgres
--

CREATE INDEX ix_auth_user_email ON account.auth_user USING btree (email);


--
-- TOC entry 5530 (class 1259 OID 18125)
-- Name: ix_analytics_snapshot_portfolio_asof; Type: INDEX; Schema: analytics; Owner: postgres
--

CREATE INDEX ix_analytics_snapshot_portfolio_asof ON analytics.portfolio_snapshot USING btree (portfolio_id, as_of DESC);


--
-- TOC entry 5617 (class 1259 OID 18515)
-- Name: ix_pvd_portfolio_date; Type: INDEX; Schema: analytics; Owner: postgres
--

CREATE INDEX ix_pvd_portfolio_date ON analytics.position_valuation_daily USING btree (portfolio_id, as_of DESC);


--
-- TOC entry 5546 (class 1259 OID 18194)
-- Name: ix_infra_audit_ts; Type: INDEX; Schema: infra; Owner: postgres
--

CREATE INDEX ix_infra_audit_ts ON infra.audit_log USING btree (ts DESC);


--
-- TOC entry 5547 (class 1259 OID 18205)
-- Name: ix_infra_outbox_unprocessed; Type: INDEX; Schema: infra; Owner: postgres
--

CREATE INDEX ix_infra_outbox_unprocessed ON infra.outbox_event USING btree (processed_at) WHERE (processed_at IS NULL);


--
-- TOC entry 5616 (class 1259 OID 18483)
-- Name: ix_acc_portf_portfolio; Type: INDEX; Schema: integrations; Owner: postgres
--

CREATE INDEX ix_acc_portf_portfolio ON integrations.account_portfolio USING btree (portfolio_id);


--
-- TOC entry 5539 (class 1259 OID 18163)
-- Name: ix_integrations_sync_log_integration_time; Type: INDEX; Schema: integrations; Owner: postgres
--

CREATE INDEX ix_integrations_sync_log_integration_time ON integrations.sync_log USING btree (integration_id, started_at DESC);


--
-- TOC entry 5649 (class 1259 OID 18676)
-- Name: ix_bar_asset_ts; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_bar_asset_ts ON market.bar USING btree (asset_id, ts DESC);


--
-- TOC entry 5650 (class 1259 OID 18677)
-- Name: ix_bar_provider; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_bar_provider ON market.bar USING btree (provider_id);


--
-- TOC entry 5634 (class 1259 OID 18583)
-- Name: ix_ca_asset_exdate; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_ca_asset_exdate ON market.corporate_action USING btree (asset_id, ex_date);


--
-- TOC entry 5659 (class 1259 OID 18716)
-- Name: ix_fx_rate_daily_pair_d; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_fx_rate_daily_pair_d ON market.fx_rate_daily USING btree (base_currency_id, quote_currency_id, d DESC);


--
-- TOC entry 5514 (class 1259 OID 18018)
-- Name: ix_market_fx_pair_ts; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_market_fx_pair_ts ON market.fx_rate USING btree (base_currency_id, quote_currency_id, ts DESC);


--
-- TOC entry 5515 (class 1259 OID 18647)
-- Name: ix_market_fx_provider; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_market_fx_provider ON market.fx_rate USING btree (provider_id);


--
-- TOC entry 5503 (class 1259 OID 17996)
-- Name: ix_market_price_asset_ts; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_market_price_asset_ts ON market.price USING btree (asset_id, ts DESC);


--
-- TOC entry 5504 (class 1259 OID 18641)
-- Name: ix_market_price_provider; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_market_price_provider ON market.price USING btree (provider_id);


--
-- TOC entry 5505 (class 1259 OID 17997)
-- Name: ix_market_price_source; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_market_price_source ON market.price USING btree (source);


--
-- TOC entry 5660 (class 1259 OID 18721)
-- Name: ix_mv_latest_daily_fx_pair; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_mv_latest_daily_fx_pair ON market.mv_latest_daily_fx USING btree (base_currency_id, quote_currency_id);


--
-- TOC entry 5516 (class 1259 OID 18030)
-- Name: ix_mv_latest_daily_price_asset; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_mv_latest_daily_price_asset ON market.mv_latest_daily_price USING btree (asset_id);


--
-- TOC entry 5653 (class 1259 OID 18708)
-- Name: ix_quote_asset_ts; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_quote_asset_ts ON market.quote USING btree (asset_id, ts DESC);


--
-- TOC entry 5654 (class 1259 OID 18709)
-- Name: ix_quote_provider; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_quote_provider ON market.quote USING btree (provider_id);


--
-- TOC entry 5651 (class 1259 OID 18675)
-- Name: uq_bar_no_provider; Type: INDEX; Schema: market; Owner: postgres
--

CREATE UNIQUE INDEX uq_bar_no_provider ON market.bar USING btree (asset_id, ts, "interval") WHERE (provider_id IS NULL);


--
-- TOC entry 5652 (class 1259 OID 18674)
-- Name: uq_bar_with_provider; Type: INDEX; Schema: market; Owner: postgres
--

CREATE UNIQUE INDEX uq_bar_with_provider ON market.bar USING btree (asset_id, ts, "interval", provider_id) WHERE (provider_id IS NOT NULL);


--
-- TOC entry 5657 (class 1259 OID 18707)
-- Name: uq_quote_no_provider; Type: INDEX; Schema: market; Owner: postgres
--

CREATE UNIQUE INDEX uq_quote_no_provider ON market.quote USING btree (asset_id, ts) WHERE (provider_id IS NULL);


--
-- TOC entry 5658 (class 1259 OID 18706)
-- Name: uq_quote_with_provider; Type: INDEX; Schema: market; Owner: postgres
--

CREATE UNIQUE INDEX uq_quote_with_provider ON market.quote USING btree (asset_id, ts, provider_id) WHERE (provider_id IS NOT NULL);


--
-- TOC entry 5575 (class 1259 OID 18314)
-- Name: fetch_log_feed_id_started_at_idx; Type: INDEX; Schema: marketdata; Owner: postgres
--

CREATE INDEX fetch_log_feed_id_started_at_idx ON marketdata.fetch_log USING btree (feed_id, started_at DESC);


--
-- TOC entry 5558 (class 1259 OID 18710)
-- Name: ix_feed_next_run; Type: INDEX; Schema: marketdata; Owner: postgres
--

CREATE INDEX ix_feed_next_run ON marketdata.feed USING btree (enabled, next_run_at);


--
-- TOC entry 5559 (class 1259 OID 18711)
-- Name: ix_feed_watermark; Type: INDEX; Schema: marketdata; Owner: postgres
--

CREATE INDEX ix_feed_watermark ON marketdata.feed USING btree (watermark_ts);


--
-- TOC entry 5562 (class 1259 OID 18728)
-- Name: ix_symbol_map_provider_symbol; Type: INDEX; Schema: marketdata; Owner: postgres
--

CREATE INDEX ix_symbol_map_provider_symbol ON marketdata.symbol_map USING btree (provider_id, external_symbol);


--
-- TOC entry 5525 (class 1259 OID 18110)
-- Name: ix_portfolio_tx_asset_time; Type: INDEX; Schema: portfolio; Owner: postgres
--

CREATE INDEX ix_portfolio_tx_asset_time ON portfolio.transaction USING btree (asset_id, tx_time DESC);


--
-- TOC entry 5526 (class 1259 OID 18109)
-- Name: ix_portfolio_tx_portfolio_time; Type: INDEX; Schema: portfolio; Owner: postgres
--

CREATE INDEX ix_portfolio_tx_portfolio_time ON portfolio.transaction USING btree (portfolio_id, tx_time DESC);


--
-- TOC entry 5527 (class 1259 OID 18111)
-- Name: ix_portfolio_tx_type; Type: INDEX; Schema: portfolio; Owner: postgres
--

CREATE INDEX ix_portfolio_tx_type ON portfolio.transaction USING btree (tx_type);


--
-- TOC entry 5602 (class 1259 OID 18427)
-- Name: ix_balances_raw_account; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_balances_raw_account ON staging.balances_raw USING btree (integration_id, ext_account_id, pulled_at DESC);


--
-- TOC entry 5592 (class 1259 OID 18395)
-- Name: ix_cashflows_raw_time; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_cashflows_raw_time ON staging.cashflows_raw USING btree (integration_id, ext_account_id, occurred_at DESC);


--
-- TOC entry 5606 (class 1259 OID 18444)
-- Name: ix_funding_raw_time; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_funding_raw_time ON staging.funding_raw USING btree (integration_id, ext_account_id, ts DESC);


--
-- TOC entry 5595 (class 1259 OID 18412)
-- Name: ix_orders_raw_account; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_orders_raw_account ON staging.orders_raw USING btree (integration_id, ext_account_id, created_at DESC);


--
-- TOC entry 5581 (class 1259 OID 18361)
-- Name: ix_positions_raw_pull; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_positions_raw_pull ON staging.positions_raw USING btree (integration_id, ext_account_id, pulled_at DESC);


--
-- TOC entry 5585 (class 1259 OID 18378)
-- Name: ix_trades_raw_time; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_trades_raw_time ON staging.trades_raw USING btree (integration_id, ext_account_id, trade_time DESC);


--
-- TOC entry 5603 (class 1259 OID 18428)
-- Name: ux_balances_raw_point; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE UNIQUE INDEX ux_balances_raw_point ON staging.balances_raw USING btree (integration_id, ext_account_id, currency_code, pulled_at);


--
-- TOC entry 5580 (class 1259 OID 18345)
-- Name: ux_broker_positions_raw_dedup; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE UNIQUE INDEX ux_broker_positions_raw_dedup ON staging.broker_positions_raw USING btree (integration_id, ext_sub_account, ext_ticker, COALESCE(ext_exchange, ''::text), COALESCE(ext_term, ''::text), COALESCE(ext_expire_date, '0001-01-01'::date));


--
-- TOC entry 5607 (class 1259 OID 18443)
-- Name: ux_funding_raw_dedup; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE UNIQUE INDEX ux_funding_raw_dedup ON staging.funding_raw USING btree (integration_id, ext_account_id, ext_symbol, COALESCE(venue_code, ''::text), ts);


--
-- TOC entry 5584 (class 1259 OID 18360)
-- Name: ux_positions_raw_dedup; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE UNIQUE INDEX ux_positions_raw_dedup ON staging.positions_raw USING btree (integration_id, ext_account_id, ext_symbol, COALESCE(venue_code, ''::text), COALESCE(instrument_type, ''::text), COALESCE(expire_date, '0001-01-01'::date), COALESCE(position_side, ''::text));


--
-- TOC entry 5717 (class 2620 OID 18485)
-- Name: account_portfolio trg_check_acc_portf_user; Type: TRIGGER; Schema: integrations; Owner: postgres
--

CREATE TRIGGER trg_check_acc_portf_user BEFORE INSERT OR UPDATE ON integrations.account_portfolio FOR EACH ROW EXECUTE FUNCTION integrations.fn_check_account_portfolio_same_user();


--
-- TOC entry 5661 (class 2606 OID 17903)
-- Name: session_token session_token_user_id_fkey; Type: FK CONSTRAINT; Schema: account; Owner: postgres
--

ALTER TABLE ONLY account.session_token
    ADD CONSTRAINT session_token_user_id_fkey FOREIGN KEY (user_id) REFERENCES account.auth_user(id) ON DELETE CASCADE;


--
-- TOC entry 5705 (class 2606 OID 18548)
-- Name: benchmark_component benchmark_component_asset_id_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.benchmark_component
    ADD CONSTRAINT benchmark_component_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id);


--
-- TOC entry 5706 (class 2606 OID 18543)
-- Name: benchmark_component benchmark_component_benchmark_id_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.benchmark_component
    ADD CONSTRAINT benchmark_component_benchmark_id_fkey FOREIGN KEY (benchmark_id) REFERENCES analytics.benchmark(id) ON DELETE CASCADE;


--
-- TOC entry 5679 (class 2606 OID 18120)
-- Name: portfolio_snapshot portfolio_snapshot_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.portfolio_snapshot
    ADD CONSTRAINT portfolio_snapshot_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5701 (class 2606 OID 18505)
-- Name: position_valuation_daily position_valuation_daily_asset_id_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.position_valuation_daily
    ADD CONSTRAINT position_valuation_daily_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id);


--
-- TOC entry 5702 (class 2606 OID 18500)
-- Name: position_valuation_daily position_valuation_daily_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.position_valuation_daily
    ADD CONSTRAINT position_valuation_daily_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5703 (class 2606 OID 18510)
-- Name: position_valuation_daily position_valuation_daily_price_currency_id_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.position_valuation_daily
    ADD CONSTRAINT position_valuation_daily_price_currency_id_fkey FOREIGN KEY (price_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5710 (class 2606 OID 18617)
-- Name: prediction prediction_model_id_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.prediction
    ADD CONSTRAINT prediction_model_id_fkey FOREIGN KEY (model_id) REFERENCES analytics.model_registry(id) ON DELETE CASCADE;


--
-- TOC entry 5683 (class 2606 OID 18189)
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: infra; Owner: postgres
--

ALTER TABLE ONLY infra.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES account.auth_user(id) ON DELETE SET NULL;


--
-- TOC entry 5698 (class 2606 OID 18457)
-- Name: account account_integration_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account
    ADD CONSTRAINT account_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5699 (class 2606 OID 18473)
-- Name: account_portfolio account_portfolio_account_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account_portfolio
    ADD CONSTRAINT account_portfolio_account_id_fkey FOREIGN KEY (account_id) REFERENCES integrations.account(id) ON DELETE CASCADE;


--
-- TOC entry 5700 (class 2606 OID 18478)
-- Name: account_portfolio account_portfolio_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account_portfolio
    ADD CONSTRAINT account_portfolio_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5680 (class 2606 OID 18139)
-- Name: integration integration_user_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.integration
    ADD CONSTRAINT integration_user_id_fkey FOREIGN KEY (user_id) REFERENCES account.auth_user(id) ON DELETE CASCADE;


--
-- TOC entry 5681 (class 2606 OID 18158)
-- Name: sync_log sync_log_integration_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.sync_log
    ADD CONSTRAINT sync_log_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5682 (class 2606 OID 18174)
-- Name: advice advice_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: llm; Owner: postgres
--

ALTER TABLE ONLY llm.advice
    ADD CONSTRAINT advice_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5662 (class 2606 OID 17951)
-- Name: asset asset_exchange_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset
    ADD CONSTRAINT asset_exchange_id_fkey FOREIGN KEY (exchange_id) REFERENCES market.exchange(id);


--
-- TOC entry 5664 (class 2606 OID 17968)
-- Name: asset_identifier asset_identifier_asset_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_identifier
    ADD CONSTRAINT asset_identifier_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id) ON DELETE CASCADE;


--
-- TOC entry 5704 (class 2606 OID 18523)
-- Name: asset_tag asset_tag_asset_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_tag
    ADD CONSTRAINT asset_tag_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id) ON DELETE CASCADE;


--
-- TOC entry 5663 (class 2606 OID 17946)
-- Name: asset asset_trading_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset
    ADD CONSTRAINT asset_trading_currency_id_fkey FOREIGN KEY (trading_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5711 (class 2606 OID 18659)
-- Name: bar bar_asset_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.bar
    ADD CONSTRAINT bar_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id) ON DELETE CASCADE;


--
-- TOC entry 5712 (class 2606 OID 18664)
-- Name: bar bar_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.bar
    ADD CONSTRAINT bar_currency_id_fkey FOREIGN KEY (currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5713 (class 2606 OID 18669)
-- Name: bar bar_provider_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.bar
    ADD CONSTRAINT bar_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id) ON DELETE SET NULL;


--
-- TOC entry 5709 (class 2606 OID 18578)
-- Name: corporate_action corporate_action_asset_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.corporate_action
    ADD CONSTRAINT corporate_action_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id);


--
-- TOC entry 5668 (class 2606 OID 18008)
-- Name: fx_rate fx_rate_base_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.fx_rate
    ADD CONSTRAINT fx_rate_base_currency_id_fkey FOREIGN KEY (base_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5669 (class 2606 OID 18642)
-- Name: fx_rate fx_rate_provider_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.fx_rate
    ADD CONSTRAINT fx_rate_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id) ON DELETE SET NULL;


--
-- TOC entry 5670 (class 2606 OID 18013)
-- Name: fx_rate fx_rate_quote_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.fx_rate
    ADD CONSTRAINT fx_rate_quote_currency_id_fkey FOREIGN KEY (quote_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5665 (class 2606 OID 17986)
-- Name: price price_asset_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.price
    ADD CONSTRAINT price_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id) ON DELETE CASCADE;


--
-- TOC entry 5666 (class 2606 OID 17991)
-- Name: price price_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.price
    ADD CONSTRAINT price_currency_id_fkey FOREIGN KEY (currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5667 (class 2606 OID 18636)
-- Name: price price_provider_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.price
    ADD CONSTRAINT price_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id) ON DELETE SET NULL;


--
-- TOC entry 5714 (class 2606 OID 18691)
-- Name: quote quote_asset_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.quote
    ADD CONSTRAINT quote_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id) ON DELETE CASCADE;


--
-- TOC entry 5715 (class 2606 OID 18696)
-- Name: quote quote_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.quote
    ADD CONSTRAINT quote_currency_id_fkey FOREIGN KEY (currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5716 (class 2606 OID 18701)
-- Name: quote quote_provider_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.quote
    ADD CONSTRAINT quote_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id) ON DELETE SET NULL;


--
-- TOC entry 5684 (class 2606 OID 18234)
-- Name: feed feed_provider_id_fkey; Type: FK CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.feed
    ADD CONSTRAINT feed_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id) ON DELETE CASCADE;


--
-- TOC entry 5690 (class 2606 OID 18309)
-- Name: fetch_log fetch_log_feed_id_fkey; Type: FK CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.fetch_log
    ADD CONSTRAINT fetch_log_feed_id_fkey FOREIGN KEY (feed_id) REFERENCES marketdata.feed(id) ON DELETE CASCADE;


--
-- TOC entry 5685 (class 2606 OID 18723)
-- Name: symbol_map fk_symbol_map_exchange; Type: FK CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT fk_symbol_map_exchange FOREIGN KEY (exchange_code) REFERENCES market.exchange(code) ON DELETE SET NULL;


--
-- TOC entry 5686 (class 2606 OID 18254)
-- Name: symbol_map symbol_map_asset_id_fkey; Type: FK CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT symbol_map_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id);


--
-- TOC entry 5687 (class 2606 OID 18249)
-- Name: symbol_map symbol_map_provider_id_fkey; Type: FK CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT symbol_map_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id) ON DELETE CASCADE;


--
-- TOC entry 5671 (class 2606 OID 18050)
-- Name: portfolio portfolio_base_currency_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio
    ADD CONSTRAINT portfolio_base_currency_id_fkey FOREIGN KEY (base_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5707 (class 2606 OID 18563)
-- Name: portfolio_benchmark portfolio_benchmark_benchmark_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio_benchmark
    ADD CONSTRAINT portfolio_benchmark_benchmark_id_fkey FOREIGN KEY (benchmark_id) REFERENCES analytics.benchmark(id);


--
-- TOC entry 5708 (class 2606 OID 18558)
-- Name: portfolio_benchmark portfolio_benchmark_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio_benchmark
    ADD CONSTRAINT portfolio_benchmark_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5672 (class 2606 OID 18045)
-- Name: portfolio portfolio_user_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio
    ADD CONSTRAINT portfolio_user_id_fkey FOREIGN KEY (user_id) REFERENCES account.auth_user(id) ON DELETE CASCADE;


--
-- TOC entry 5673 (class 2606 OID 18071)
-- Name: position position_asset_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio."position"
    ADD CONSTRAINT position_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id);


--
-- TOC entry 5674 (class 2606 OID 18066)
-- Name: position position_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio."position"
    ADD CONSTRAINT position_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5675 (class 2606 OID 18094)
-- Name: transaction transaction_asset_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id);


--
-- TOC entry 5676 (class 2606 OID 18104)
-- Name: transaction transaction_linked_tx_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_linked_tx_id_fkey FOREIGN KEY (linked_tx_id) REFERENCES portfolio.transaction(id) ON DELETE SET NULL;


--
-- TOC entry 5677 (class 2606 OID 18089)
-- Name: transaction transaction_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5678 (class 2606 OID 18099)
-- Name: transaction transaction_price_currency_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_price_currency_id_fkey FOREIGN KEY (price_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5696 (class 2606 OID 18422)
-- Name: balances_raw balances_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.balances_raw
    ADD CONSTRAINT balances_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5691 (class 2606 OID 18340)
-- Name: broker_positions_raw broker_positions_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.broker_positions_raw
    ADD CONSTRAINT broker_positions_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5694 (class 2606 OID 18390)
-- Name: cashflows_raw cashflows_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.cashflows_raw
    ADD CONSTRAINT cashflows_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5697 (class 2606 OID 18438)
-- Name: funding_raw funding_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.funding_raw
    ADD CONSTRAINT funding_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5689 (class 2606 OID 18290)
-- Name: fx_raw fx_raw_provider_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.fx_raw
    ADD CONSTRAINT fx_raw_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id);


--
-- TOC entry 5695 (class 2606 OID 18407)
-- Name: orders_raw orders_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.orders_raw
    ADD CONSTRAINT orders_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5692 (class 2606 OID 18355)
-- Name: positions_raw positions_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.positions_raw
    ADD CONSTRAINT positions_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5688 (class 2606 OID 18273)
-- Name: price_raw price_raw_provider_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.price_raw
    ADD CONSTRAINT price_raw_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id);


--
-- TOC entry 5693 (class 2606 OID 18373)
-- Name: trades_raw trades_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.trades_raw
    ADD CONSTRAINT trades_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5875 (class 0 OID 18019)
-- Dependencies: 239 5915
-- Name: mv_latest_daily_price; Type: MATERIALIZED VIEW DATA; Schema: market; Owner: postgres
--

REFRESH MATERIALIZED VIEW market.mv_latest_daily_price;


-- Completed on 2025-10-27 20:31:18

--
-- PostgreSQL database dump complete
--

\unrestrict Osev1d1fcbkLMGWVvtx0EDVjQcqRHVmv3sj8CR4uc44rMONr6PXlXor6fJGobmH

