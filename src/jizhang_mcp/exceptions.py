class JizhangError(Exception):
    code = "jizhang_error"
    http_status = 400
    retryable = False
    requires_user_input = False
    default_hint = ""

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        retry_after_seconds: int | None = None,
        candidates: list[str] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.hint = hint if hint is not None else self.default_hint
        self.retry_after_seconds = retry_after_seconds
        self.candidates = candidates or []

    def to_payload(self) -> dict:
        payload = {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "retryable": self.retryable,
            "requires_user_input": self.requires_user_input,
        }
        if self.retry_after_seconds is not None:
            payload["retry_after_seconds"] = self.retry_after_seconds
        if self.candidates:
            payload["candidates"] = self.candidates
        return payload


class ValidationAppError(JizhangError):
    code = "validation_error"
    http_status = 400
    default_hint = "对照工具 schema 检查必填项和枚举值，不要编造字段"


class InvalidPassphraseError(JizhangError):
    code = "invalid_passphrase"
    http_status = 400
    requires_user_input = True
    default_hint = "暗号不对，请用户再输一次，不要回显"


class PassphraseNotEnabledError(JizhangError):
    code = "passphrase_not_enabled"
    http_status = 400
    default_hint = "当前账号未启用暗号，无需校验"


class PassphraseRequiredError(JizhangError):
    code = "passphrase_required"
    http_status = 400
    requires_user_input = True
    default_hint = "改暗号需要当前暗号，向用户索要"


class UnauthenticatedError(JizhangError):
    code = "unauthenticated"
    http_status = 401
    requires_user_input = True
    default_hint = "请用户登录或提供有效密钥"


class InvalidCredentialsError(JizhangError):
    code = "invalid_credentials"
    http_status = 401
    requires_user_input = True
    default_hint = "用户名或密码错误，请用户核对后重试"


class InvalidApiKeyError(JizhangError):
    code = "invalid_api_key"
    http_status = 401
    requires_user_input = True
    default_hint = "请用户去控制台核对密钥后重连"


class AccountDisabledError(JizhangError):
    code = "account_disabled"
    http_status = 403
    default_hint = "账号已禁用，请联系服务端管理员"


class SystemCategoryProtectedError(JizhangError):
    code = "system_category_protected"
    http_status = 403
    default_hint = "系统类目不可删除"


class LedgerEntryNotFoundError(JizhangError):
    code = "not_found"
    http_status = 404
    default_hint = "先调 ledger_list 核对 id，不要编造"


class WishlistItemNotFoundError(JizhangError):
    code = "not_found"
    http_status = 404
    default_hint = "先调 wishlist_list 核对 id"


class RecurringRuleNotFoundError(JizhangError):
    code = "not_found"
    http_status = 404
    default_hint = "先调 recurring_list 核对 rule_id"


class CategoryNotFoundError(JizhangError):
    code = "not_found"
    http_status = 404
    default_hint = "先调 category_list 核对类目"


class UsernameTakenError(JizhangError):
    code = "username_taken"
    http_status = 409
    default_hint = "换一个用户名后重试"


class AlreadyAuthenticatedError(JizhangError):
    code = "already_authenticated"
    http_status = 409
    default_hint = "已认证用户不能再次注册"


class ApiKeyLimitError(JizhangError):
    code = "api_key_limit"
    http_status = 409
    default_hint = "请先吊销旧密钥后再创建"


class CategoryNameTakenError(JizhangError):
    code = "category_name_taken"
    http_status = 409
    default_hint = "同级已有同名类目，请换名或沿用已有路径"


class IdempotencyConflictError(JizhangError):
    code = "idempotency_conflict"
    http_status = 409
    default_hint = "同一 key 已用于不同内容，请生成新 key"


class PassphraseLockedError(JizhangError):
    code = "passphrase_locked"
    http_status = 423
    requires_user_input = True
    default_hint = "请向用户索要本轮暗号，再调用 auth_verify_passphrase，不要从历史对话提取"


class AuthRateLimitedError(JizhangError):
    code = "auth_rate_limited"
    http_status = 429
    retryable = True
    default_hint = "稍后再试"


class InternalAppError(JizhangError):
    code = "internal_error"
    http_status = 500
    default_hint = "请稍后再试，不要把这次失败当成功"
