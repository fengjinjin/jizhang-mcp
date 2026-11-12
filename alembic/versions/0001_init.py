"""init schema

Revision ID: 0001
Revises:
Create Date: 2026-11-12
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE_SQL = """CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(32) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    passphrase_hash VARCHAR(255) NULL,
    tier VARCHAR(16) NOT NULL DEFAULT 'free',
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_users_username_len CHECK (char_length(username) BETWEEN 3 AND 32),
    CONSTRAINT ck_users_status CHECK (status IN ('active', 'disabled'))
);

COMMENT ON TABLE users IS '匿名账号。只存用户名与慢哈希，不收手机号邮箱实名。';
COMMENT ON COLUMN users.username IS '展示用原文；唯一性按 LOWER(username) 判断。';
COMMENT ON COLUMN users.password_hash IS 'Argon2id 哈希，禁止存明文。';
COMMENT ON COLUMN users.passphrase_hash IS '可选暗号的 Argon2id 哈希；NULL 表示未启用对暗号。';
COMMENT ON COLUMN users.tier IS '一期恒为 free，预留给后续付费仓，不做配额拦截。';
COMMENT ON COLUMN users.status IS 'active 正常，disabled 禁止登录与使用密钥。';

CREATE UNIQUE INDEX uk_users_username_lower ON users (LOWER(username));

CREATE TRIGGER tr_users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE api_keys (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    key_prefix VARCHAR(12) NOT NULL,
    key_hash CHAR(64) NOT NULL,
    last_used_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NULL,
    revoked_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_api_keys_hash_hex CHECK (key_hash ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE api_keys IS '连接密钥。明文只在创建时返回一次，库内仅存 SHA-256 与前缀。';
COMMENT ON COLUMN api_keys.name IS '用户备注名，例如 默认密钥、笔记本。';
COMMENT ON COLUMN api_keys.key_prefix IS '明文前 12 位，用于控制台掩码展示。';
COMMENT ON COLUMN api_keys.key_hash IS '明文 UTF-8 的 SHA-256 hex。';
COMMENT ON COLUMN api_keys.revoked_at IS '非空表示已吊销。';

CREATE UNIQUE INDEX uk_api_keys_key_hash ON api_keys (key_hash);
CREATE INDEX ix_api_keys_user_id ON api_keys (user_id);
CREATE INDEX ix_api_keys_user_active ON api_keys (user_id) WHERE revoked_at IS NULL;

CREATE TABLE categories (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    direction VARCHAR(16) NOT NULL,
    parent_id BIGINT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    level SMALLINT NOT NULL,
    name VARCHAR(16) NOT NULL,
    is_system BOOLEAN NOT NULL DEFAULT false,
    sort_order INT NOT NULL DEFAULT 0,
    deleted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_categories_direction CHECK (direction IN ('expense', 'income')),
    CONSTRAINT ck_categories_name CHECK (
        char_length(name) BETWEEN 1 AND 16
        AND name ~ '^[A-Za-z0-9一-龥]{1,16}$'
    ),
    CONSTRAINT ck_categories_level CHECK (level BETWEEN 1 AND 3),
    CONSTRAINT ck_categories_level_parent CHECK (
        (level = 1 AND parent_id IS NULL)
        OR (level IN (2, 3) AND parent_id IS NOT NULL)
    ),
    CONSTRAINT ck_categories_system_root CHECK (
        is_system = false OR (parent_id IS NULL AND level = 1)
    )
);

COMMENT ON TABLE categories IS '用户级类目，最多三级。注册种下系统一级；用户可自建一级和子级。不要做全局字典表。';
COMMENT ON COLUMN categories.parent_id IS '空表示一级；非空表示挂在父节点下的二/三级。';
COMMENT ON COLUMN categories.level IS '1 一级，2 二级，3 三级。插入时 parent.level 必须小于 3。';
COMMENT ON COLUMN categories.name IS '短中文名，不含连字符。完整路径写在流水的 category_path。';
COMMENT ON COLUMN categories.is_system IS '注册种下的一级为 true，不可删除；用户自建为 false，可软删。';

CREATE UNIQUE INDEX uk_categories_root_name
    ON categories (user_id, direction, LOWER(name))
    WHERE parent_id IS NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX uk_categories_child_name
    ON categories (user_id, direction, parent_id, LOWER(name))
    WHERE parent_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX ix_categories_user_dir_parent
    ON categories (user_id, direction, parent_id)
    WHERE deleted_at IS NULL;

CREATE TRIGGER tr_categories_set_updated_at
BEFORE UPDATE ON categories
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE wishlist_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title VARCHAR(128) NOT NULL,
    estimated_price NUMERIC(12, 2) NULL,
    currency CHAR(3) NOT NULL DEFAULT 'CNY',
    planned_at DATE NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'wanted',
    note TEXT NULL,
    deleted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_wishlist_title_len CHECK (char_length(title) BETWEEN 1 AND 128),
    CONSTRAINT ck_wishlist_price CHECK (estimated_price IS NULL OR estimated_price >= 0),
    CONSTRAINT ck_wishlist_status CHECK (status IN ('wanted', 'bought', 'cancelled')),
    CONSTRAINT ck_wishlist_currency CHECK (char_length(currency) = 3)
);

COMMENT ON TABLE wishlist_items IS '愿望清单。与账本分开，购买评估只引用已记账目结余。';
COMMENT ON COLUMN wishlist_items.planned_at IS '想买的日期，允许空。';
COMMENT ON COLUMN wishlist_items.deleted_at IS '软删除时间，非空即对用户不可见。';

CREATE INDEX ix_wishlist_user_active
    ON wishlist_items (user_id, status, planned_at)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_wishlist_user_created
    ON wishlist_items (user_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE TRIGGER tr_wishlist_set_updated_at
BEFORE UPDATE ON wishlist_items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE recurring_rules (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title VARCHAR(128) NOT NULL,
    direction VARCHAR(16) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'CNY',
    category_id BIGINT NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    root_category_id BIGINT NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    category_path VARCHAR(50) NOT NULL,
    note TEXT NULL,
    frequency VARCHAR(16) NOT NULL,
    day_of_week SMALLINT NULL,
    day_of_month SMALLINT NULL,
    month_of_year SMALLINT NULL,
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    start_date DATE NOT NULL,
    end_date DATE NULL,
    next_run_date DATE NOT NULL,
    last_run_date DATE NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    deleted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_recurring_title_len CHECK (char_length(title) BETWEEN 1 AND 128),
    CONSTRAINT ck_recurring_direction CHECK (direction IN ('expense', 'income')),
    CONSTRAINT ck_recurring_amount CHECK (amount > 0),
    CONSTRAINT ck_recurring_currency CHECK (char_length(currency) = 3),
    CONSTRAINT ck_recurring_category_path CHECK (
        char_length(category_path) BETWEEN 1 AND 50
        AND category_path ~ '^[A-Za-z0-9一-龥]{1,16}(-[A-Za-z0-9一-龥]{1,16}){0,2}$'
    ),
    CONSTRAINT ck_recurring_frequency CHECK (frequency IN ('daily', 'weekly', 'monthly', 'yearly')),
    CONSTRAINT ck_recurring_status CHECK (status IN ('active', 'paused', 'ended')),
    CONSTRAINT ck_recurring_end_date CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ck_recurring_calendar CHECK (
        (frequency = 'daily'
            AND day_of_week IS NULL
            AND day_of_month IS NULL
            AND month_of_year IS NULL)
        OR (frequency = 'weekly'
            AND day_of_week BETWEEN 1 AND 7
            AND day_of_month IS NULL
            AND month_of_year IS NULL)
        OR (frequency = 'monthly'
            AND day_of_week IS NULL
            AND day_of_month BETWEEN 1 AND 31
            AND month_of_year IS NULL)
        OR (frequency = 'yearly'
            AND day_of_week IS NULL
            AND month_of_year BETWEEN 1 AND 12
            AND (
                (month_of_year IN (1, 3, 5, 7, 8, 10, 12)
                    AND day_of_month BETWEEN 1 AND 31)
                OR (month_of_year IN (4, 6, 9, 11)
                    AND day_of_month BETWEEN 1 AND 30)
                OR (month_of_year = 2
                    AND day_of_month BETWEEN 1 AND 29)
            ))
    )
);

COMMENT ON TABLE recurring_rules IS '定时收支规则。到期后写入 ledger_entries，复盘只读已入账流水。';
COMMENT ON COLUMN recurring_rules.category_id IS '实际使用的类目节点：记到哪一级就指向哪一级。';
COMMENT ON COLUMN recurring_rules.root_category_id IS '路径最顶层一级。一级时等于 category_id。';
COMMENT ON COLUMN recurring_rules.category_path IS '服务按节点算出的展示路径，1～3 段，禁止客户端乱传。';
COMMENT ON COLUMN recurring_rules.note IS '生成流水时的备注；为空则用 title。';
COMMENT ON COLUMN recurring_rules.day_of_week IS '1=周一 … 7=周日，仅 weekly 使用。';
COMMENT ON COLUMN recurring_rules.day_of_month IS '1~31，monthly 与 yearly 使用；短月按月底吸附。';
COMMENT ON COLUMN recurring_rules.month_of_year IS '1~12，仅 yearly 使用。';
COMMENT ON COLUMN recurring_rules.next_run_date IS '下一账期日，调度器按此扫描。';
COMMENT ON COLUMN recurring_rules.status IS 'active 调度中，paused 跳过，ended 超过 end_date。';

CREATE INDEX ix_recurring_due
    ON recurring_rules (next_run_date)
    WHERE status = 'active' AND deleted_at IS NULL;
CREATE INDEX ix_recurring_user_active
    ON recurring_rules (user_id, status, next_run_date)
    WHERE deleted_at IS NULL;

CREATE TRIGGER tr_recurring_set_updated_at
BEFORE UPDATE ON recurring_rules
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE ledger_entries (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    direction VARCHAR(16) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'CNY',
    category_id BIGINT NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    root_category_id BIGINT NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    category_path VARCHAR(50) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    note TEXT NULL,
    wishlist_item_id BIGINT NULL REFERENCES wishlist_items (id) ON DELETE SET NULL,
    recurring_rule_id BIGINT NULL REFERENCES recurring_rules (id) ON DELETE SET NULL,
    scheduled_for_date DATE NULL,
    deleted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_ledger_direction CHECK (direction IN ('expense', 'income')),
    CONSTRAINT ck_ledger_amount CHECK (amount > 0),
    CONSTRAINT ck_ledger_currency CHECK (char_length(currency) = 3),
    CONSTRAINT ck_ledger_category_path CHECK (
        char_length(category_path) BETWEEN 1 AND 50
        AND category_path ~ '^[A-Za-z0-9一-龥]{1,16}(-[A-Za-z0-9一-龥]{1,16}){0,2}$'
    ),
    CONSTRAINT ck_ledger_recurring_date CHECK (
        recurring_rule_id IS NULL OR scheduled_for_date IS NOT NULL
    )
);

COMMENT ON TABLE ledger_entries IS '账本流水。统计与复盘只读 deleted_at 为空的行。';
COMMENT ON COLUMN ledger_entries.direction IS 'expense 支出，income 收入。';
COMMENT ON COLUMN ledger_entries.amount IS '正数，单位为该币种元，两位小数。';
COMMENT ON COLUMN ledger_entries.category_id IS '实际使用的类目节点：记到哪一级就指向哪一级。';
COMMENT ON COLUMN ledger_entries.root_category_id IS '路径最顶层一级。按大类查账、按 primary 统计都用它。';
COMMENT ON COLUMN ledger_entries.category_path IS '服务按节点算出，1～3 段。列表展示和 keyword 用它。';
COMMENT ON COLUMN ledger_entries.wishlist_item_id IS '可选，关联愿望清单中的某一项。';
COMMENT ON COLUMN ledger_entries.recurring_rule_id IS '自动入账时指向规则；手记流水为空。';
COMMENT ON COLUMN ledger_entries.scheduled_for_date IS '该笔自动流水所属账期日。规则 id 非空时本列必填，避免 NULL 绕过唯一索引。';
COMMENT ON COLUMN ledger_entries.deleted_at IS '软删除，防误删；查询默认排除。';

CREATE INDEX ix_ledger_user_time
    ON ledger_entries (user_id, occurred_at DESC, id DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_ledger_user_category
    ON ledger_entries (user_id, category_id, occurred_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_ledger_user_root
    ON ledger_entries (user_id, root_category_id, occurred_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_ledger_user_category_path
    ON ledger_entries (user_id, category_path, occurred_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_ledger_user_direction
    ON ledger_entries (user_id, direction, occurred_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_ledger_wishlist
    ON ledger_entries (wishlist_item_id)
    WHERE wishlist_item_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX ix_ledger_recurring_rule
    ON ledger_entries (recurring_rule_id, occurred_at DESC)
    WHERE recurring_rule_id IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX uk_ledger_recurring_period
    ON ledger_entries (recurring_rule_id, scheduled_for_date)
    WHERE recurring_rule_id IS NOT NULL;

CREATE TRIGGER tr_ledger_set_updated_at
BEFORE UPDATE ON ledger_entries
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE idempotency_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    tool_name VARCHAR(32) NOT NULL,
    idempotency_key VARCHAR(64) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    response_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_idempotency_key_len CHECK (char_length(idempotency_key) BETWEEN 1 AND 64),
    CONSTRAINT ck_idempotency_hash_hex CHECK (request_hash ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE idempotency_records IS '手记防重放。按用户+工具+key 记住首次成功响应，流水本身不带这个字段。';
COMMENT ON COLUMN idempotency_records.tool_name IS '如 ledger_add、ledger_add_batch，不同工具的 key 互不占用。';
COMMENT ON COLUMN idempotency_records.request_hash IS '入参规范化 JSON 的 SHA-256 hex，用来发现同 key 不同内容。';
COMMENT ON COLUMN idempotency_records.response_json IS '首次成功的完整响应；写入流水之后再填，失败则整事务回滚不留行。';

CREATE UNIQUE INDEX uk_idempotency_user_tool_key
    ON idempotency_records (user_id, tool_name, idempotency_key);"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS idempotency_records CASCADE;
DROP TABLE IF EXISTS ledger_entries CASCADE;
DROP TABLE IF EXISTS recurring_rules CASCADE;
DROP TABLE IF EXISTS wishlist_items CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP FUNCTION IF EXISTS set_updated_at();
"""


def _dsn() -> str:
    from jizhang_mcp.config import get_settings

    return get_settings().database_url.replace("+asyncpg", "")


def upgrade() -> None:
    import psycopg2

    with psycopg2.connect(_dsn()) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(UPGRADE_SQL)


def downgrade() -> None:
    import psycopg2

    with psycopg2.connect(_dsn()) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(DOWNGRADE_SQL)
