-- Household ledger MVP schema
-- Target: PostgreSQL 15+

BEGIN;

-- 1) import/raw
CREATE TABLE IF NOT EXISTS import_batch (
  id BIGSERIAL PRIMARY KEY,
  source_type TEXT NOT NULL CHECK (source_type IN ('csv','xlsx','manual')),
  source_filename TEXT,
  imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  timezone TEXT NOT NULL DEFAULT 'Asia/Seoul',
  status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('pending','completed','failed'))
);

CREATE TABLE IF NOT EXISTS raw_import (
  id BIGSERIAL PRIMARY KEY,
  import_batch_id BIGINT NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
  row_no INTEGER NOT NULL,
  raw_payload JSONB NOT NULL,
  row_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (import_batch_id, row_no),
  UNIQUE (row_hash)
);

-- 2) master data
CREATE TABLE IF NOT EXISTS category_major (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  type_scope TEXT NOT NULL CHECK (type_scope IN ('expense','income','common')),
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS category_minor (
  id BIGSERIAL PRIMARY KEY,
  major_id BIGINT NOT NULL REFERENCES category_major(id),
  name TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (major_id, name)
);

CREATE TABLE IF NOT EXISTS payment_method (
  id BIGSERIAL PRIMARY KEY,
  name_original TEXT NOT NULL,
  name_normalized TEXT NOT NULL,
  method_kind TEXT NOT NULL CHECK (method_kind IN ('bank_account','card','easy_pay','cash','etc')),
  issuer TEXT,
  last4 TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (name_normalized)
);

CREATE TABLE IF NOT EXISTS asset_account (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  account_type TEXT NOT NULL CHECK (account_type IN ('checking','savings','pocket','pay_wallet','investment','other')),
  currency TEXT NOT NULL DEFAULT 'KRW',
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- 3) transactions
CREATE TABLE IF NOT EXISTS transaction_entry (
  id BIGSERIAL PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('income','expense','transfer')),
  direction TEXT NOT NULL CHECK (direction IN ('in','out','neutral')),
  amount BIGINT NOT NULL CHECK (amount >= 0),
  signed_amount BIGINT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'KRW',
  merchant_or_counterparty TEXT,
  category_major_id BIGINT REFERENCES category_major(id),
  category_minor_id BIGINT REFERENCES category_minor(id),
  payment_method_id BIGINT REFERENCES payment_method(id),
  note TEXT,
  raw_import_id BIGINT REFERENCES raw_import(id),
  transfer_group_id UUID,
  transfer_external BOOLEAN NOT NULL DEFAULT FALSE,
  review_required BOOLEAN NOT NULL DEFAULT FALSE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','deleted','merged')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transaction_account_link (
  transaction_id BIGINT NOT NULL REFERENCES transaction_entry(id) ON DELETE CASCADE,
  asset_account_id BIGINT NOT NULL REFERENCES asset_account(id),
  role TEXT NOT NULL CHECK (role IN ('source','destination','payment')),
  PRIMARY KEY (transaction_id, asset_account_id, role)
);

CREATE TABLE IF NOT EXISTS category_feedback (
  id BIGSERIAL PRIMARY KEY,
  transaction_id BIGINT NOT NULL REFERENCES transaction_entry(id) ON DELETE CASCADE,
  previous_major_id BIGINT REFERENCES category_major(id),
  previous_minor_id BIGINT REFERENCES category_minor(id),
  updated_major_id BIGINT REFERENCES category_major(id),
  updated_minor_id BIGINT REFERENCES category_minor(id),
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS monthly_snapshot (
  id BIGSERIAL PRIMARY KEY,
  month_key DATE NOT NULL,
  currency TEXT NOT NULL DEFAULT 'KRW',
  total_income BIGINT NOT NULL DEFAULT 0,
  total_expense BIGINT NOT NULL DEFAULT 0,
  total_transfer BIGINT NOT NULL DEFAULT 0,
  net_cashflow BIGINT NOT NULL DEFAULT 0,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (month_key, currency)
);

-- 4) indexes
CREATE INDEX IF NOT EXISTS idx_transaction_entry_occurred_at ON transaction_entry (occurred_at);
CREATE INDEX IF NOT EXISTS idx_transaction_entry_type ON transaction_entry (type);
CREATE INDEX IF NOT EXISTS idx_transaction_entry_category_major_id ON transaction_entry (category_major_id);
CREATE INDEX IF NOT EXISTS idx_transaction_entry_payment_method_id ON transaction_entry (payment_method_id);
CREATE INDEX IF NOT EXISTS idx_transaction_entry_transfer_group_id ON transaction_entry (transfer_group_id);
CREATE INDEX IF NOT EXISTS idx_raw_import_import_batch_id ON raw_import (import_batch_id);

-- 5) updated_at trigger helper
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_transaction_entry_updated_at ON transaction_entry;
CREATE TRIGGER trg_transaction_entry_updated_at
BEFORE UPDATE ON transaction_entry
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
