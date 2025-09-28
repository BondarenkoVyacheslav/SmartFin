```mermaid
erDiagram
  app_user {
    uuid id PK
    citext email UNIQUE
    text password_hash
    boolean is_active
    text twofa_secret
    uuid base_currency_id FK
    text timezone
    timestamptz created_at
    timestamptz updated_at
  }

  currency {
    uuid id PK
    text code UNIQUE
    text name
    int decimals
    boolean is_crypto
    timestamptz created_at
  }

  exchange {
    uuid id PK
    text code UNIQUE
    text name
    text country
    text timezone
    timestamptz created_at
  }

  asset {
    uuid id PK
    asset_class_enum class
    text symbol
    text name
    uuid trading_currency_id FK
    text isin
    uuid exchange_id FK
    jsonb metadata
    boolean is_active
    timestamptz created_at
  }

  asset_identifier {
    uuid id PK
    uuid asset_id FK
    text id_type
    text id_value
  }

  portfolio {
    uuid id PK
    uuid user_id FK
    text name
    uuid base_currency_id FK
    jsonb settings
    timestamptz created_at
    timestamptz updated_at
  }

  transaction {
    uuid id PK
    uuid portfolio_id FK
    uuid asset_id FK
    transaction_type_enum tx_type
    timestamptz tx_time
    numeric quantity
    numeric price
    uuid price_currency_id FK
    numeric fee
    text notes
    jsonb metadata
    uuid linked_tx_id FK
    timestamptz created_at
  }

  price {
    uuid id PK
    uuid asset_id FK
    timestamptz ts
    numeric price
    uuid currency_id FK
    text source
    price_interval_enum interval
    jsonb metadata
    timestamptz created_at
  }

  fx_rate {
    uuid id PK
    uuid base_currency_id FK
    uuid quote_currency_id FK
    timestamptz ts
    numeric rate
    text source
  }

  integration {
    uuid id PK
    uuid user_id FK
    text provider
    text display_name
    text status
    text credentials_encrypted
    timestamptz last_sync_at
    timestamptz created_at
    timestamptz updated_at
  }

  advice {
    uuid id PK
    uuid portfolio_id FK
    text kind
    text message
    numeric score
    jsonb payload
    timestamptz created_at
  }

  audit_log {
    uuid id PK
    uuid user_id FK
    timestamptz ts
    text action
    text target_type
    uuid target_id
    inet ip
    text user_agent
    jsonb details
  }

  %% Relationships
  currency ||--o{ app_user : "base_currency"
  app_user ||--o{ portfolio : "owns"
  currency ||--o{ portfolio : "base_currency"
  exchange ||--o{ asset : "listed_on"
  currency ||--o{ asset : "trading_currency"
  asset ||--o{ asset_identifier : "has_alias"
  portfolio ||--o{ transaction : "has"
  asset ||--o{ transaction : "is_traded"
  currency ||--o{ transaction : "price_currency"
  transaction }o--|| transaction : "linked_tx"
  asset ||--o{ price : "has_price"
  currency ||--o{ price : "price_currency"
  currency ||--o{ fx_rate : "as_base"
  currency ||--o{ fx_rate : "as_quote"
  portfolio ||--o{ advice : "has"
  app_user ||--o{ integration : "has"
  app_user ||--o{ audit_log : "actions"
```