--
-- PostgreSQL database dump
--

\restrict IZafaQe3pAAZZ71UQqs1qAetRZyAsH8GkRwaVyNcYCbgqu4LhiTg4ECvCk9viGm

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

-- Started on 2025-10-26 00:02:13

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
-- TOC entry 9 (class 2615 OID 17809)
-- Name: account; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA account;


ALTER SCHEMA account OWNER TO postgres;

--
-- TOC entry 12 (class 2615 OID 17812)
-- Name: analytics; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA analytics;


ALTER SCHEMA analytics OWNER TO postgres;

--
-- TOC entry 8 (class 2615 OID 17808)
-- Name: core; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA core;


ALTER SCHEMA core OWNER TO postgres;

--
-- TOC entry 15 (class 2615 OID 17815)
-- Name: infra; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA infra;


ALTER SCHEMA infra OWNER TO postgres;

--
-- TOC entry 13 (class 2615 OID 17813)
-- Name: integrations; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA integrations;


ALTER SCHEMA integrations OWNER TO postgres;

--
-- TOC entry 14 (class 2615 OID 17814)
-- Name: llm; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA llm;


ALTER SCHEMA llm OWNER TO postgres;

--
-- TOC entry 10 (class 2615 OID 17810)
-- Name: market; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA market;


ALTER SCHEMA market OWNER TO postgres;

--
-- TOC entry 16 (class 2615 OID 18207)
-- Name: marketdata; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA marketdata;


ALTER SCHEMA marketdata OWNER TO postgres;

--
-- TOC entry 11 (class 2615 OID 17811)
-- Name: portfolio; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA portfolio;


ALTER SCHEMA portfolio OWNER TO postgres;

--
-- TOC entry 17 (class 2615 OID 18208)
-- Name: staging; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA staging;


ALTER SCHEMA staging OWNER TO postgres;

--
-- TOC entry 3 (class 3079 OID 17502)
-- Name: citext; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;


--
-- TOC entry 5476 (class 0 OID 0)
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
-- TOC entry 5477 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- TOC entry 975 (class 1247 OID 17817)
-- Name: asset_class_enum; Type: TYPE; Schema: core; Owner: postgres
--

CREATE TYPE core.asset_class_enum AS ENUM (
    'stock',
    'bond',
    'fund',
    'crypto',
    'fiat',
    'metal',
    'cash',
    'deposit',
    'other'
);


ALTER TYPE core.asset_class_enum OWNER TO postgres;

--
-- TOC entry 981 (class 1247 OID 17864)
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
-- TOC entry 978 (class 1247 OID 17836)
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
-- TOC entry 342 (class 1255 OID 18031)
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
-- TOC entry 231 (class 1259 OID 17891)
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
-- TOC entry 242 (class 1259 OID 18112)
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
-- TOC entry 246 (class 1259 OID 18179)
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
-- TOC entry 247 (class 1259 OID 18195)
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
-- TOC entry 261 (class 1259 OID 18446)
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
-- TOC entry 262 (class 1259 OID 18462)
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
-- TOC entry 243 (class 1259 OID 18126)
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
-- TOC entry 244 (class 1259 OID 18144)
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
-- TOC entry 245 (class 1259 OID 18164)
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
-- TOC entry 234 (class 1259 OID 17933)
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
-- TOC entry 235 (class 1259 OID 17956)
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
-- TOC entry 232 (class 1259 OID 17909)
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
-- TOC entry 233 (class 1259 OID 17922)
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
-- TOC entry 237 (class 1259 OID 17998)
-- Name: fx_rate; Type: TABLE; Schema: market; Owner: postgres
--

CREATE TABLE market.fx_rate (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    base_currency_id uuid NOT NULL,
    quote_currency_id uuid NOT NULL,
    ts timestamp with time zone NOT NULL,
    rate numeric(38,10) NOT NULL,
    source text NOT NULL
);


ALTER TABLE market.fx_rate OWNER TO postgres;

--
-- TOC entry 236 (class 1259 OID 17973)
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
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE market.price OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 18019)
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
-- TOC entry 249 (class 1259 OID 18221)
-- Name: feed; Type: TABLE; Schema: marketdata; Owner: postgres
--

CREATE TABLE marketdata.feed (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    provider_id uuid NOT NULL,
    feed_type text NOT NULL,
    universe jsonb DEFAULT '{}'::jsonb NOT NULL,
    schedule text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    CONSTRAINT feed_feed_type_check CHECK ((feed_type = ANY (ARRAY['price'::text, 'fx'::text, 'sentiment'::text, 'news'::text, 'corp_action'::text])))
);


ALTER TABLE marketdata.feed OWNER TO postgres;

--
-- TOC entry 253 (class 1259 OID 18295)
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
-- TOC entry 248 (class 1259 OID 18209)
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
-- TOC entry 250 (class 1259 OID 18239)
-- Name: symbol_map; Type: TABLE; Schema: marketdata; Owner: postgres
--

CREATE TABLE marketdata.symbol_map (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    provider_id uuid NOT NULL,
    external_symbol text NOT NULL,
    exchange_code text DEFAULT ''::text NOT NULL,
    asset_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE marketdata.symbol_map OWNER TO postgres;

--
-- TOC entry 239 (class 1259 OID 18032)
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
-- TOC entry 240 (class 1259 OID 18055)
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
-- TOC entry 241 (class 1259 OID 18076)
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
-- TOC entry 230 (class 1259 OID 17874)
-- Name: auth_user; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auth_user (
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


ALTER TABLE public.auth_user OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 17873)
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.auth_user ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 259 (class 1259 OID 18413)
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
-- TOC entry 254 (class 1259 OID 18331)
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
-- TOC entry 257 (class 1259 OID 18379)
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
-- TOC entry 260 (class 1259 OID 18429)
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
-- TOC entry 252 (class 1259 OID 18278)
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
-- TOC entry 258 (class 1259 OID 18396)
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
-- TOC entry 255 (class 1259 OID 18346)
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
-- TOC entry 251 (class 1259 OID 18261)
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
-- TOC entry 256 (class 1259 OID 18362)
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
-- TOC entry 5439 (class 0 OID 17891)
-- Dependencies: 231
-- Data for Name: session_token; Type: TABLE DATA; Schema: account; Owner: postgres
--

COPY account.session_token (id, user_id, digest, issued_at, expires_at, revoked_at, ip, user_agent) FROM stdin;
\.


--
-- TOC entry 5450 (class 0 OID 18112)
-- Dependencies: 242
-- Data for Name: portfolio_snapshot; Type: TABLE DATA; Schema: analytics; Owner: postgres
--

COPY analytics.portfolio_snapshot (id, portfolio_id, as_of, total_value, pnl_1d, pnl_7d, pnl_30d) FROM stdin;
\.


--
-- TOC entry 5454 (class 0 OID 18179)
-- Dependencies: 246
-- Data for Name: audit_log; Type: TABLE DATA; Schema: infra; Owner: postgres
--

COPY infra.audit_log (id, user_id, ts, action, target_type, target_id, ip, user_agent, details) FROM stdin;
\.


--
-- TOC entry 5455 (class 0 OID 18195)
-- Dependencies: 247
-- Data for Name: outbox_event; Type: TABLE DATA; Schema: infra; Owner: postgres
--

COPY infra.outbox_event (id, topic, payload, created_at, processed_at, attempts) FROM stdin;
\.


--
-- TOC entry 5469 (class 0 OID 18446)
-- Dependencies: 261
-- Data for Name: account; Type: TABLE DATA; Schema: integrations; Owner: postgres
--

COPY integrations.account (id, integration_id, provider_code, ext_account_id, display_name, meta) FROM stdin;
\.


--
-- TOC entry 5470 (class 0 OID 18462)
-- Dependencies: 262
-- Data for Name: account_portfolio; Type: TABLE DATA; Schema: integrations; Owner: postgres
--

COPY integrations.account_portfolio (id, account_id, portfolio_id, instrument_types, venue_codes, symbols_include, symbols_exclude, is_primary) FROM stdin;
\.


--
-- TOC entry 5451 (class 0 OID 18126)
-- Dependencies: 243
-- Data for Name: integration; Type: TABLE DATA; Schema: integrations; Owner: postgres
--

COPY integrations.integration (id, user_id, provider, display_name, status, credentials_encrypted, last_sync_at, created_at, updated_at) FROM stdin;
\.


--
-- TOC entry 5452 (class 0 OID 18144)
-- Dependencies: 244
-- Data for Name: sync_log; Type: TABLE DATA; Schema: integrations; Owner: postgres
--

COPY integrations.sync_log (id, integration_id, started_at, finished_at, status, rows_in, rows_upd, rows_err, details) FROM stdin;
\.


--
-- TOC entry 5453 (class 0 OID 18164)
-- Dependencies: 245
-- Data for Name: advice; Type: TABLE DATA; Schema: llm; Owner: postgres
--

COPY llm.advice (id, portfolio_id, kind, message, score, payload, created_at) FROM stdin;
\.


--
-- TOC entry 5442 (class 0 OID 17933)
-- Dependencies: 234
-- Data for Name: asset; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.asset (id, class, symbol, name, trading_currency_id, isin, exchange_id, metadata, is_active, created_at) FROM stdin;
\.


--
-- TOC entry 5443 (class 0 OID 17956)
-- Dependencies: 235
-- Data for Name: asset_identifier; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.asset_identifier (id, asset_id, id_type, id_value) FROM stdin;
\.


--
-- TOC entry 5440 (class 0 OID 17909)
-- Dependencies: 232
-- Data for Name: currency; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.currency (id, code, name, decimals, is_crypto, created_at) FROM stdin;
\.


--
-- TOC entry 5441 (class 0 OID 17922)
-- Dependencies: 233
-- Data for Name: exchange; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.exchange (id, code, name, country, timezone, created_at) FROM stdin;
\.


--
-- TOC entry 5445 (class 0 OID 17998)
-- Dependencies: 237
-- Data for Name: fx_rate; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.fx_rate (id, base_currency_id, quote_currency_id, ts, rate, source) FROM stdin;
\.


--
-- TOC entry 5444 (class 0 OID 17973)
-- Dependencies: 236
-- Data for Name: price; Type: TABLE DATA; Schema: market; Owner: postgres
--

COPY market.price (id, asset_id, ts, price, currency_id, source, "interval", metadata, created_at) FROM stdin;
\.


--
-- TOC entry 5457 (class 0 OID 18221)
-- Dependencies: 249
-- Data for Name: feed; Type: TABLE DATA; Schema: marketdata; Owner: postgres
--

COPY marketdata.feed (id, provider_id, feed_type, universe, schedule, enabled) FROM stdin;
\.


--
-- TOC entry 5461 (class 0 OID 18295)
-- Dependencies: 253
-- Data for Name: fetch_log; Type: TABLE DATA; Schema: marketdata; Owner: postgres
--

COPY marketdata.fetch_log (id, feed_id, started_at, finished_at, status, rows_in, rows_upd, rows_err, details) FROM stdin;
\.


--
-- TOC entry 5456 (class 0 OID 18209)
-- Dependencies: 248
-- Data for Name: provider; Type: TABLE DATA; Schema: marketdata; Owner: postgres
--

COPY marketdata.provider (id, code, kind, sla, cost, created_at) FROM stdin;
\.


--
-- TOC entry 5458 (class 0 OID 18239)
-- Dependencies: 250
-- Data for Name: symbol_map; Type: TABLE DATA; Schema: marketdata; Owner: postgres
--

COPY marketdata.symbol_map (id, provider_id, external_symbol, exchange_code, asset_id, metadata) FROM stdin;
\.


--
-- TOC entry 5447 (class 0 OID 18032)
-- Dependencies: 239
-- Data for Name: portfolio; Type: TABLE DATA; Schema: portfolio; Owner: postgres
--

COPY portfolio.portfolio (id, user_id, name, base_currency_id, settings, created_at, updated_at) FROM stdin;
\.


--
-- TOC entry 5448 (class 0 OID 18055)
-- Dependencies: 240
-- Data for Name: position; Type: TABLE DATA; Schema: portfolio; Owner: postgres
--

COPY portfolio."position" (id, portfolio_id, asset_id, qty, cost_basis, updated_at) FROM stdin;
\.


--
-- TOC entry 5449 (class 0 OID 18076)
-- Dependencies: 241
-- Data for Name: transaction; Type: TABLE DATA; Schema: portfolio; Owner: postgres
--

COPY portfolio.transaction (id, portfolio_id, asset_id, tx_type, tx_time, quantity, price, price_currency_id, fee, notes, metadata, linked_tx_id, created_at) FROM stdin;
\.


--
-- TOC entry 5438 (class 0 OID 17874)
-- Dependencies: 230
-- Data for Name: auth_user; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.auth_user (id, username, email, first_name, last_name, password, is_staff, is_active, is_superuser, last_login, date_joined) FROM stdin;
\.


--
-- TOC entry 5467 (class 0 OID 18413)
-- Dependencies: 259
-- Data for Name: balances_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.balances_raw (id, integration_id, pulled_at, payload, ext_account_id, currency_code, total, available, locked) FROM stdin;
\.


--
-- TOC entry 5462 (class 0 OID 18331)
-- Dependencies: 254
-- Data for Name: broker_positions_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.broker_positions_raw (id, integration_id, pulled_at, payload, ext_sub_account, ext_ticker, ext_exchange, ext_term, ext_expire_date) FROM stdin;
\.


--
-- TOC entry 5465 (class 0 OID 18379)
-- Dependencies: 257
-- Data for Name: cashflows_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.cashflows_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_cashflow_id, occurred_at, currency_code, amount, kind) FROM stdin;
\.


--
-- TOC entry 5468 (class 0 OID 18429)
-- Dependencies: 260
-- Data for Name: funding_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.funding_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_symbol, venue_code, ts, funding_rate, funding_fee, currency_code) FROM stdin;
\.


--
-- TOC entry 5460 (class 0 OID 18278)
-- Dependencies: 252
-- Data for Name: fx_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.fx_raw (id, provider_id, base_code, quote_code, ts, rate, payload, landed_at) FROM stdin;
\.


--
-- TOC entry 5466 (class 0 OID 18396)
-- Dependencies: 258
-- Data for Name: orders_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.orders_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_order_id, ext_symbol, venue_code, instrument_type, status, side, order_type, price, quantity, created_at, updated_at) FROM stdin;
\.


--
-- TOC entry 5463 (class 0 OID 18346)
-- Dependencies: 255
-- Data for Name: positions_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.positions_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_symbol, venue_code, instrument_type, expire_date, position_side, quantity, entry_price, currency_code) FROM stdin;
\.


--
-- TOC entry 5459 (class 0 OID 18261)
-- Dependencies: 251
-- Data for Name: price_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.price_raw (id, provider_id, external_symbol, ts, price, currency_code, "interval", payload, landed_at) FROM stdin;
\.


--
-- TOC entry 5464 (class 0 OID 18362)
-- Dependencies: 256
-- Data for Name: trades_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.trades_raw (id, integration_id, pulled_at, payload, ext_account_id, ext_trade_id, ext_symbol, venue_code, instrument_type, trade_time, side, price, quantity, currency_code) FROM stdin;
\.


--
-- TOC entry 5478 (class 0 OID 0)
-- Dependencies: 229
-- Name: auth_user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.auth_user_id_seq', 1, false);


--
-- TOC entry 5126 (class 2606 OID 17902)
-- Name: session_token session_token_digest_key; Type: CONSTRAINT; Schema: account; Owner: postgres
--

ALTER TABLE ONLY account.session_token
    ADD CONSTRAINT session_token_digest_key UNIQUE (digest);


--
-- TOC entry 5128 (class 2606 OID 17900)
-- Name: session_token session_token_pkey; Type: CONSTRAINT; Schema: account; Owner: postgres
--

ALTER TABLE ONLY account.session_token
    ADD CONSTRAINT session_token_pkey PRIMARY KEY (id);


--
-- TOC entry 5174 (class 2606 OID 18117)
-- Name: portfolio_snapshot portfolio_snapshot_pkey; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.portfolio_snapshot
    ADD CONSTRAINT portfolio_snapshot_pkey PRIMARY KEY (id);


--
-- TOC entry 5176 (class 2606 OID 18119)
-- Name: portfolio_snapshot portfolio_snapshot_portfolio_id_as_of_key; Type: CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.portfolio_snapshot
    ADD CONSTRAINT portfolio_snapshot_portfolio_id_as_of_key UNIQUE (portfolio_id, as_of);


--
-- TOC entry 5187 (class 2606 OID 18188)
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: infra; Owner: postgres
--

ALTER TABLE ONLY infra.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5191 (class 2606 OID 18204)
-- Name: outbox_event outbox_event_pkey; Type: CONSTRAINT; Schema: infra; Owner: postgres
--

ALTER TABLE ONLY infra.outbox_event
    ADD CONSTRAINT outbox_event_pkey PRIMARY KEY (id);


--
-- TOC entry 5246 (class 2606 OID 18456)
-- Name: account account_integration_id_ext_account_id_key; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account
    ADD CONSTRAINT account_integration_id_ext_account_id_key UNIQUE (integration_id, ext_account_id);


--
-- TOC entry 5248 (class 2606 OID 18454)
-- Name: account account_pkey; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account
    ADD CONSTRAINT account_pkey PRIMARY KEY (id);


--
-- TOC entry 5250 (class 2606 OID 18472)
-- Name: account_portfolio account_portfolio_account_id_portfolio_id_key; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account_portfolio
    ADD CONSTRAINT account_portfolio_account_id_portfolio_id_key UNIQUE (account_id, portfolio_id);


--
-- TOC entry 5252 (class 2606 OID 18470)
-- Name: account_portfolio account_portfolio_pkey; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account_portfolio
    ADD CONSTRAINT account_portfolio_pkey PRIMARY KEY (id);


--
-- TOC entry 5178 (class 2606 OID 18136)
-- Name: integration integration_pkey; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.integration
    ADD CONSTRAINT integration_pkey PRIMARY KEY (id);


--
-- TOC entry 5180 (class 2606 OID 18138)
-- Name: integration integration_user_id_provider_display_name_key; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.integration
    ADD CONSTRAINT integration_user_id_provider_display_name_key UNIQUE (user_id, provider, display_name);


--
-- TOC entry 5183 (class 2606 OID 18157)
-- Name: sync_log sync_log_pkey; Type: CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.sync_log
    ADD CONSTRAINT sync_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5185 (class 2606 OID 18173)
-- Name: advice advice_pkey; Type: CONSTRAINT; Schema: llm; Owner: postgres
--

ALTER TABLE ONLY llm.advice
    ADD CONSTRAINT advice_pkey PRIMARY KEY (id);


--
-- TOC entry 5142 (class 2606 OID 17967)
-- Name: asset_identifier asset_identifier_asset_id_id_type_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_identifier
    ADD CONSTRAINT asset_identifier_asset_id_id_type_key UNIQUE (asset_id, id_type);


--
-- TOC entry 5144 (class 2606 OID 17965)
-- Name: asset_identifier asset_identifier_id_type_id_value_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_identifier
    ADD CONSTRAINT asset_identifier_id_type_id_value_key UNIQUE (id_type, id_value);


--
-- TOC entry 5146 (class 2606 OID 17963)
-- Name: asset_identifier asset_identifier_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_identifier
    ADD CONSTRAINT asset_identifier_pkey PRIMARY KEY (id);


--
-- TOC entry 5138 (class 2606 OID 17943)
-- Name: asset asset_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset
    ADD CONSTRAINT asset_pkey PRIMARY KEY (id);


--
-- TOC entry 5130 (class 2606 OID 17921)
-- Name: currency currency_code_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.currency
    ADD CONSTRAINT currency_code_key UNIQUE (code);


--
-- TOC entry 5132 (class 2606 OID 17919)
-- Name: currency currency_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.currency
    ADD CONSTRAINT currency_pkey PRIMARY KEY (id);


--
-- TOC entry 5134 (class 2606 OID 17932)
-- Name: exchange exchange_code_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.exchange
    ADD CONSTRAINT exchange_code_key UNIQUE (code);


--
-- TOC entry 5136 (class 2606 OID 17930)
-- Name: exchange exchange_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.exchange
    ADD CONSTRAINT exchange_pkey PRIMARY KEY (id);


--
-- TOC entry 5154 (class 2606 OID 18007)
-- Name: fx_rate fx_rate_base_currency_id_quote_currency_id_ts_source_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.fx_rate
    ADD CONSTRAINT fx_rate_base_currency_id_quote_currency_id_ts_source_key UNIQUE (base_currency_id, quote_currency_id, ts, source);


--
-- TOC entry 5156 (class 2606 OID 18005)
-- Name: fx_rate fx_rate_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.fx_rate
    ADD CONSTRAINT fx_rate_pkey PRIMARY KEY (id);


--
-- TOC entry 5150 (class 2606 OID 17985)
-- Name: price price_asset_id_ts_source_interval_key; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.price
    ADD CONSTRAINT price_asset_id_ts_source_interval_key UNIQUE (asset_id, ts, source, "interval");


--
-- TOC entry 5152 (class 2606 OID 17983)
-- Name: price price_pkey; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.price
    ADD CONSTRAINT price_pkey PRIMARY KEY (id);


--
-- TOC entry 5140 (class 2606 OID 17945)
-- Name: asset uq_market_asset_symbol_exch; Type: CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset
    ADD CONSTRAINT uq_market_asset_symbol_exch UNIQUE (symbol, exchange_id);


--
-- TOC entry 5197 (class 2606 OID 18231)
-- Name: feed feed_pkey; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.feed
    ADD CONSTRAINT feed_pkey PRIMARY KEY (id);


--
-- TOC entry 5199 (class 2606 OID 18233)
-- Name: feed feed_provider_id_feed_type_universe_key; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.feed
    ADD CONSTRAINT feed_provider_id_feed_type_universe_key UNIQUE (provider_id, feed_type, universe);


--
-- TOC entry 5214 (class 2606 OID 18308)
-- Name: fetch_log fetch_log_pkey; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.fetch_log
    ADD CONSTRAINT fetch_log_pkey PRIMARY KEY (id);


--
-- TOC entry 5193 (class 2606 OID 18220)
-- Name: provider provider_code_key; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.provider
    ADD CONSTRAINT provider_code_key UNIQUE (code);


--
-- TOC entry 5195 (class 2606 OID 18218)
-- Name: provider provider_pkey; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.provider
    ADD CONSTRAINT provider_pkey PRIMARY KEY (id);


--
-- TOC entry 5201 (class 2606 OID 18248)
-- Name: symbol_map symbol_map_pkey; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT symbol_map_pkey PRIMARY KEY (id);


--
-- TOC entry 5203 (class 2606 OID 18260)
-- Name: symbol_map ux_symbol_map; Type: CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT ux_symbol_map UNIQUE (provider_id, external_symbol, exchange_code);


--
-- TOC entry 5160 (class 2606 OID 18042)
-- Name: portfolio portfolio_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio
    ADD CONSTRAINT portfolio_pkey PRIMARY KEY (id);


--
-- TOC entry 5162 (class 2606 OID 18044)
-- Name: portfolio portfolio_user_id_name_key; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio
    ADD CONSTRAINT portfolio_user_id_name_key UNIQUE (user_id, name);


--
-- TOC entry 5164 (class 2606 OID 18063)
-- Name: position position_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio."position"
    ADD CONSTRAINT position_pkey PRIMARY KEY (id);


--
-- TOC entry 5166 (class 2606 OID 18065)
-- Name: position position_portfolio_id_asset_id_key; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio."position"
    ADD CONSTRAINT position_portfolio_id_asset_id_key UNIQUE (portfolio_id, asset_id);


--
-- TOC entry 5171 (class 2606 OID 18088)
-- Name: transaction transaction_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_pkey PRIMARY KEY (id);


--
-- TOC entry 5120 (class 2606 OID 17887)
-- Name: auth_user auth_user_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- TOC entry 5122 (class 2606 OID 17889)
-- Name: auth_user auth_user_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- TOC entry 5238 (class 2606 OID 18421)
-- Name: balances_raw balances_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.balances_raw
    ADD CONSTRAINT balances_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5216 (class 2606 OID 18339)
-- Name: broker_positions_raw broker_positions_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.broker_positions_raw
    ADD CONSTRAINT broker_positions_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5228 (class 2606 OID 18387)
-- Name: cashflows_raw cashflows_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.cashflows_raw
    ADD CONSTRAINT cashflows_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5242 (class 2606 OID 18437)
-- Name: funding_raw funding_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.funding_raw
    ADD CONSTRAINT funding_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5209 (class 2606 OID 18287)
-- Name: fx_raw fx_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.fx_raw
    ADD CONSTRAINT fx_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5211 (class 2606 OID 18289)
-- Name: fx_raw fx_raw_provider_id_base_code_quote_code_ts_key; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.fx_raw
    ADD CONSTRAINT fx_raw_provider_id_base_code_quote_code_ts_key UNIQUE (provider_id, base_code, quote_code, ts);


--
-- TOC entry 5234 (class 2606 OID 18404)
-- Name: orders_raw orders_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.orders_raw
    ADD CONSTRAINT orders_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5220 (class 2606 OID 18354)
-- Name: positions_raw positions_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.positions_raw
    ADD CONSTRAINT positions_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5205 (class 2606 OID 18270)
-- Name: price_raw price_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.price_raw
    ADD CONSTRAINT price_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5207 (class 2606 OID 18272)
-- Name: price_raw price_raw_provider_id_external_symbol_ts_interval_key; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.price_raw
    ADD CONSTRAINT price_raw_provider_id_external_symbol_ts_interval_key UNIQUE (provider_id, external_symbol, ts, "interval");


--
-- TOC entry 5224 (class 2606 OID 18370)
-- Name: trades_raw trades_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.trades_raw
    ADD CONSTRAINT trades_raw_pkey PRIMARY KEY (id);


--
-- TOC entry 5231 (class 2606 OID 18389)
-- Name: cashflows_raw uq_cashflows_raw; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.cashflows_raw
    ADD CONSTRAINT uq_cashflows_raw UNIQUE (integration_id, ext_cashflow_id);


--
-- TOC entry 5236 (class 2606 OID 18406)
-- Name: orders_raw uq_orders_raw; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.orders_raw
    ADD CONSTRAINT uq_orders_raw UNIQUE (integration_id, ext_order_id);


--
-- TOC entry 5226 (class 2606 OID 18372)
-- Name: trades_raw uq_trades_raw; Type: CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.trades_raw
    ADD CONSTRAINT uq_trades_raw UNIQUE (integration_id, ext_trade_id);


--
-- TOC entry 5124 (class 1259 OID 17908)
-- Name: ix_account_session_user_active; Type: INDEX; Schema: account; Owner: postgres
--

CREATE INDEX ix_account_session_user_active ON account.session_token USING btree (user_id, expires_at) WHERE (revoked_at IS NULL);


--
-- TOC entry 5172 (class 1259 OID 18125)
-- Name: ix_analytics_snapshot_portfolio_asof; Type: INDEX; Schema: analytics; Owner: postgres
--

CREATE INDEX ix_analytics_snapshot_portfolio_asof ON analytics.portfolio_snapshot USING btree (portfolio_id, as_of DESC);


--
-- TOC entry 5188 (class 1259 OID 18194)
-- Name: ix_infra_audit_ts; Type: INDEX; Schema: infra; Owner: postgres
--

CREATE INDEX ix_infra_audit_ts ON infra.audit_log USING btree (ts DESC);


--
-- TOC entry 5189 (class 1259 OID 18205)
-- Name: ix_infra_outbox_unprocessed; Type: INDEX; Schema: infra; Owner: postgres
--

CREATE INDEX ix_infra_outbox_unprocessed ON infra.outbox_event USING btree (processed_at) WHERE (processed_at IS NULL);


--
-- TOC entry 5253 (class 1259 OID 18483)
-- Name: ix_acc_portf_portfolio; Type: INDEX; Schema: integrations; Owner: postgres
--

CREATE INDEX ix_acc_portf_portfolio ON integrations.account_portfolio USING btree (portfolio_id);


--
-- TOC entry 5181 (class 1259 OID 18163)
-- Name: ix_integrations_sync_log_integration_time; Type: INDEX; Schema: integrations; Owner: postgres
--

CREATE INDEX ix_integrations_sync_log_integration_time ON integrations.sync_log USING btree (integration_id, started_at DESC);


--
-- TOC entry 5157 (class 1259 OID 18018)
-- Name: ix_market_fx_pair_ts; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_market_fx_pair_ts ON market.fx_rate USING btree (base_currency_id, quote_currency_id, ts DESC);


--
-- TOC entry 5147 (class 1259 OID 17996)
-- Name: ix_market_price_asset_ts; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_market_price_asset_ts ON market.price USING btree (asset_id, ts DESC);


--
-- TOC entry 5148 (class 1259 OID 17997)
-- Name: ix_market_price_source; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_market_price_source ON market.price USING btree (source);


--
-- TOC entry 5158 (class 1259 OID 18030)
-- Name: ix_mv_latest_daily_price_asset; Type: INDEX; Schema: market; Owner: postgres
--

CREATE INDEX ix_mv_latest_daily_price_asset ON market.mv_latest_daily_price USING btree (asset_id);


--
-- TOC entry 5212 (class 1259 OID 18314)
-- Name: fetch_log_feed_id_started_at_idx; Type: INDEX; Schema: marketdata; Owner: postgres
--

CREATE INDEX fetch_log_feed_id_started_at_idx ON marketdata.fetch_log USING btree (feed_id, started_at DESC);


--
-- TOC entry 5167 (class 1259 OID 18110)
-- Name: ix_portfolio_tx_asset_time; Type: INDEX; Schema: portfolio; Owner: postgres
--

CREATE INDEX ix_portfolio_tx_asset_time ON portfolio.transaction USING btree (asset_id, tx_time DESC);


--
-- TOC entry 5168 (class 1259 OID 18109)
-- Name: ix_portfolio_tx_portfolio_time; Type: INDEX; Schema: portfolio; Owner: postgres
--

CREATE INDEX ix_portfolio_tx_portfolio_time ON portfolio.transaction USING btree (portfolio_id, tx_time DESC);


--
-- TOC entry 5169 (class 1259 OID 18111)
-- Name: ix_portfolio_tx_type; Type: INDEX; Schema: portfolio; Owner: postgres
--

CREATE INDEX ix_portfolio_tx_type ON portfolio.transaction USING btree (tx_type);


--
-- TOC entry 5123 (class 1259 OID 17890)
-- Name: ix_auth_user_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_auth_user_email ON public.auth_user USING btree (email);


--
-- TOC entry 5239 (class 1259 OID 18427)
-- Name: ix_balances_raw_account; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_balances_raw_account ON staging.balances_raw USING btree (integration_id, ext_account_id, pulled_at DESC);


--
-- TOC entry 5229 (class 1259 OID 18395)
-- Name: ix_cashflows_raw_time; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_cashflows_raw_time ON staging.cashflows_raw USING btree (integration_id, ext_account_id, occurred_at DESC);


--
-- TOC entry 5243 (class 1259 OID 18444)
-- Name: ix_funding_raw_time; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_funding_raw_time ON staging.funding_raw USING btree (integration_id, ext_account_id, ts DESC);


--
-- TOC entry 5232 (class 1259 OID 18412)
-- Name: ix_orders_raw_account; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_orders_raw_account ON staging.orders_raw USING btree (integration_id, ext_account_id, created_at DESC);


--
-- TOC entry 5218 (class 1259 OID 18361)
-- Name: ix_positions_raw_pull; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_positions_raw_pull ON staging.positions_raw USING btree (integration_id, ext_account_id, pulled_at DESC);


--
-- TOC entry 5222 (class 1259 OID 18378)
-- Name: ix_trades_raw_time; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE INDEX ix_trades_raw_time ON staging.trades_raw USING btree (integration_id, ext_account_id, trade_time DESC);


--
-- TOC entry 5240 (class 1259 OID 18428)
-- Name: ux_balances_raw_point; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE UNIQUE INDEX ux_balances_raw_point ON staging.balances_raw USING btree (integration_id, ext_account_id, currency_code, pulled_at);


--
-- TOC entry 5217 (class 1259 OID 18345)
-- Name: ux_broker_positions_raw_dedup; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE UNIQUE INDEX ux_broker_positions_raw_dedup ON staging.broker_positions_raw USING btree (integration_id, ext_sub_account, ext_ticker, COALESCE(ext_exchange, ''::text), COALESCE(ext_term, ''::text), COALESCE(ext_expire_date, '0001-01-01'::date));


--
-- TOC entry 5244 (class 1259 OID 18443)
-- Name: ux_funding_raw_dedup; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE UNIQUE INDEX ux_funding_raw_dedup ON staging.funding_raw USING btree (integration_id, ext_account_id, ext_symbol, COALESCE(venue_code, ''::text), ts);


--
-- TOC entry 5221 (class 1259 OID 18360)
-- Name: ux_positions_raw_dedup; Type: INDEX; Schema: staging; Owner: postgres
--

CREATE UNIQUE INDEX ux_positions_raw_dedup ON staging.positions_raw USING btree (integration_id, ext_account_id, ext_symbol, COALESCE(venue_code, ''::text), COALESCE(instrument_type, ''::text), COALESCE(expire_date, '0001-01-01'::date), COALESCE(position_side, ''::text));


--
-- TOC entry 5254 (class 2606 OID 17903)
-- Name: session_token session_token_user_id_fkey; Type: FK CONSTRAINT; Schema: account; Owner: postgres
--

ALTER TABLE ONLY account.session_token
    ADD CONSTRAINT session_token_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id) ON DELETE CASCADE;


--
-- TOC entry 5270 (class 2606 OID 18120)
-- Name: portfolio_snapshot portfolio_snapshot_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: analytics; Owner: postgres
--

ALTER TABLE ONLY analytics.portfolio_snapshot
    ADD CONSTRAINT portfolio_snapshot_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5274 (class 2606 OID 18189)
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: infra; Owner: postgres
--

ALTER TABLE ONLY infra.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id) ON DELETE SET NULL;


--
-- TOC entry 5288 (class 2606 OID 18457)
-- Name: account account_integration_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account
    ADD CONSTRAINT account_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5289 (class 2606 OID 18473)
-- Name: account_portfolio account_portfolio_account_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account_portfolio
    ADD CONSTRAINT account_portfolio_account_id_fkey FOREIGN KEY (account_id) REFERENCES integrations.account(id) ON DELETE CASCADE;


--
-- TOC entry 5290 (class 2606 OID 18478)
-- Name: account_portfolio account_portfolio_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.account_portfolio
    ADD CONSTRAINT account_portfolio_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5271 (class 2606 OID 18139)
-- Name: integration integration_user_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.integration
    ADD CONSTRAINT integration_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id) ON DELETE CASCADE;


--
-- TOC entry 5272 (class 2606 OID 18158)
-- Name: sync_log sync_log_integration_id_fkey; Type: FK CONSTRAINT; Schema: integrations; Owner: postgres
--

ALTER TABLE ONLY integrations.sync_log
    ADD CONSTRAINT sync_log_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5273 (class 2606 OID 18174)
-- Name: advice advice_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: llm; Owner: postgres
--

ALTER TABLE ONLY llm.advice
    ADD CONSTRAINT advice_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5255 (class 2606 OID 17951)
-- Name: asset asset_exchange_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset
    ADD CONSTRAINT asset_exchange_id_fkey FOREIGN KEY (exchange_id) REFERENCES market.exchange(id);


--
-- TOC entry 5257 (class 2606 OID 17968)
-- Name: asset_identifier asset_identifier_asset_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset_identifier
    ADD CONSTRAINT asset_identifier_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id) ON DELETE CASCADE;


--
-- TOC entry 5256 (class 2606 OID 17946)
-- Name: asset asset_trading_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.asset
    ADD CONSTRAINT asset_trading_currency_id_fkey FOREIGN KEY (trading_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5260 (class 2606 OID 18008)
-- Name: fx_rate fx_rate_base_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.fx_rate
    ADD CONSTRAINT fx_rate_base_currency_id_fkey FOREIGN KEY (base_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5261 (class 2606 OID 18013)
-- Name: fx_rate fx_rate_quote_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.fx_rate
    ADD CONSTRAINT fx_rate_quote_currency_id_fkey FOREIGN KEY (quote_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5258 (class 2606 OID 17986)
-- Name: price price_asset_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.price
    ADD CONSTRAINT price_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id) ON DELETE CASCADE;


--
-- TOC entry 5259 (class 2606 OID 17991)
-- Name: price price_currency_id_fkey; Type: FK CONSTRAINT; Schema: market; Owner: postgres
--

ALTER TABLE ONLY market.price
    ADD CONSTRAINT price_currency_id_fkey FOREIGN KEY (currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5275 (class 2606 OID 18234)
-- Name: feed feed_provider_id_fkey; Type: FK CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.feed
    ADD CONSTRAINT feed_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id) ON DELETE CASCADE;


--
-- TOC entry 5280 (class 2606 OID 18309)
-- Name: fetch_log fetch_log_feed_id_fkey; Type: FK CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.fetch_log
    ADD CONSTRAINT fetch_log_feed_id_fkey FOREIGN KEY (feed_id) REFERENCES marketdata.feed(id) ON DELETE CASCADE;


--
-- TOC entry 5276 (class 2606 OID 18254)
-- Name: symbol_map symbol_map_asset_id_fkey; Type: FK CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT symbol_map_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id);


--
-- TOC entry 5277 (class 2606 OID 18249)
-- Name: symbol_map symbol_map_provider_id_fkey; Type: FK CONSTRAINT; Schema: marketdata; Owner: postgres
--

ALTER TABLE ONLY marketdata.symbol_map
    ADD CONSTRAINT symbol_map_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id) ON DELETE CASCADE;


--
-- TOC entry 5262 (class 2606 OID 18050)
-- Name: portfolio portfolio_base_currency_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio
    ADD CONSTRAINT portfolio_base_currency_id_fkey FOREIGN KEY (base_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5263 (class 2606 OID 18045)
-- Name: portfolio portfolio_user_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.portfolio
    ADD CONSTRAINT portfolio_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id) ON DELETE CASCADE;


--
-- TOC entry 5264 (class 2606 OID 18071)
-- Name: position position_asset_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio."position"
    ADD CONSTRAINT position_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id);


--
-- TOC entry 5265 (class 2606 OID 18066)
-- Name: position position_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio."position"
    ADD CONSTRAINT position_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5266 (class 2606 OID 18094)
-- Name: transaction transaction_asset_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES market.asset(id);


--
-- TOC entry 5267 (class 2606 OID 18104)
-- Name: transaction transaction_linked_tx_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_linked_tx_id_fkey FOREIGN KEY (linked_tx_id) REFERENCES portfolio.transaction(id) ON DELETE SET NULL;


--
-- TOC entry 5268 (class 2606 OID 18089)
-- Name: transaction transaction_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolio(id) ON DELETE CASCADE;


--
-- TOC entry 5269 (class 2606 OID 18099)
-- Name: transaction transaction_price_currency_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: postgres
--

ALTER TABLE ONLY portfolio.transaction
    ADD CONSTRAINT transaction_price_currency_id_fkey FOREIGN KEY (price_currency_id) REFERENCES market.currency(id);


--
-- TOC entry 5286 (class 2606 OID 18422)
-- Name: balances_raw balances_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.balances_raw
    ADD CONSTRAINT balances_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5281 (class 2606 OID 18340)
-- Name: broker_positions_raw broker_positions_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.broker_positions_raw
    ADD CONSTRAINT broker_positions_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5284 (class 2606 OID 18390)
-- Name: cashflows_raw cashflows_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.cashflows_raw
    ADD CONSTRAINT cashflows_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5287 (class 2606 OID 18438)
-- Name: funding_raw funding_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.funding_raw
    ADD CONSTRAINT funding_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5279 (class 2606 OID 18290)
-- Name: fx_raw fx_raw_provider_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.fx_raw
    ADD CONSTRAINT fx_raw_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id);


--
-- TOC entry 5285 (class 2606 OID 18407)
-- Name: orders_raw orders_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.orders_raw
    ADD CONSTRAINT orders_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5282 (class 2606 OID 18355)
-- Name: positions_raw positions_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.positions_raw
    ADD CONSTRAINT positions_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5278 (class 2606 OID 18273)
-- Name: price_raw price_raw_provider_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.price_raw
    ADD CONSTRAINT price_raw_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES marketdata.provider(id);


--
-- TOC entry 5283 (class 2606 OID 18373)
-- Name: trades_raw trades_raw_integration_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: postgres
--

ALTER TABLE ONLY staging.trades_raw
    ADD CONSTRAINT trades_raw_integration_id_fkey FOREIGN KEY (integration_id) REFERENCES integrations.integration(id) ON DELETE CASCADE;


--
-- TOC entry 5446 (class 0 OID 18019)
-- Dependencies: 238 5472
-- Name: mv_latest_daily_price; Type: MATERIALIZED VIEW DATA; Schema: market; Owner: postgres
--

REFRESH MATERIALIZED VIEW market.mv_latest_daily_price;


-- Completed on 2025-10-26 00:02:13

--
-- PostgreSQL database dump complete
--

\unrestrict IZafaQe3pAAZZ71UQqs1qAetRZyAsH8GkRwaVyNcYCbgqu4LhiTg4ECvCk9viGm

