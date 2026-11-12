DEFAULT_EXPENSE_PRIMARIES = [
    "餐饮",
    "交通",
    "购物",
    "服饰",
    "日用",
    "数码",
    "娱乐",
    "通讯",
    "住房",
    "医疗",
    "教育",
    "人情",
    "旅行",
    "宠物",
    "其他",
]

DEFAULT_INCOME_PRIMARIES = ["工资", "奖金", "兼职", "红包", "退款", "其他"]

EXPENSE_ALIASES: dict[str, tuple[str, str | None]] = {
    "吃饭": ("餐饮", "午餐"),
    "午饭": ("餐饮", "午餐"),
    "午餐": ("餐饮", "午餐"),
    "中饭": ("餐饮", "午餐"),
    "早饭": ("餐饮", "早餐"),
    "早餐": ("餐饮", "早餐"),
    "晚饭": ("餐饮", "晚餐"),
    "晚餐": ("餐饮", "晚餐"),
    "外卖": ("餐饮", "外卖"),
    "奶茶": ("餐饮", "奶茶"),
    "咖啡": ("餐饮", "咖啡"),
    "食堂": ("餐饮", "食堂"),
    "火锅": ("餐饮", "火锅"),
    "烧烤": ("餐饮", "烧烤"),
    "地铁": ("交通", "地铁"),
    "公交": ("交通", "公交"),
    "打车": ("交通", "打车"),
    "滴滴": ("交通", "打车"),
    "加油": ("交通", "加油"),
    "买菜": ("日用", "买菜"),
    "超市": ("日用", "超市"),
    "衣服": ("服饰", "衣服"),
    "鞋": ("服饰", "衣服"),
    "耳机": ("数码", "耳机"),
    "房租": ("住房", "房租"),
    "房贷": ("住房", "房贷"),
    "物业": ("住房", "物业"),
    "物业费": ("住房", "物业"),
    "电费": ("住房", "水电"),
    "水费": ("住房", "水电"),
    "燃气": ("住房", "水电"),
    "话费": ("通讯", "话费"),
    "宽带": ("通讯", "宽带"),
    "网费": ("通讯", "宽带"),
    "电影": ("娱乐", "电影"),
    "游戏": ("娱乐", "游戏"),
    "挂号": ("医疗", "挂号"),
    "看牙": ("医疗", "看牙"),
    "红包": ("人情", "红包"),
    "请客": ("人情", "请客"),
    "猫粮": ("宠物", "猫粮"),
}

INCOME_ALIASES: dict[str, tuple[str, str | None]] = {
    "工资": ("工资", None),
    "薪水": ("工资", None),
    "发工资": ("工资", None),
    "退款": ("退款", None),
    "退货": ("退款", None),
}

STATS_DISCLAIMER = "以上数字只汇总已经记入账本的流水，不是投资或理财建议。"
COMPARE_DISCLAIMER = "环比只比较两段已记账目，缺记会让对比失真。不构成理财建议。"
CATEGORY_SHARE_DISCLAIMER = "占比只反映已记账目，未入账的消费不会出现。"
TOP_EXPENSES_DISCLAIMER = "排行仅包含已经记下的支出。"
WISHLIST_DISCLAIMER = (
    "评估只使用已经记入账本的收支结余，不预测未来收入，不构成购买建议、投资建议或理财建议。"
)

PROTECTED_TOOL_NAMES = frozenset(
    {
        "ledger_add",
        "ledger_add_batch",
        "ledger_list",
        "ledger_get",
        "ledger_update",
        "ledger_delete",
        "stats_summary",
        "stats_compare",
        "stats_category_share",
        "stats_top_expenses",
        "stats_review",
        "wishlist_add",
        "wishlist_list",
        "wishlist_get",
        "wishlist_update",
        "wishlist_delete",
        "wishlist_evaluate",
        "recurring_add",
        "recurring_list",
        "recurring_get",
        "recurring_update",
        "recurring_pause",
        "recurring_resume",
        "recurring_delete",
        "category_list",
        "category_add",
        "category_delete",
    }
)

GUEST_TOOLS = frozenset({"auth_status", "account_register"})
AUTH_ONLY_TOOLS = frozenset(
    {
        "auth_status",
        "auth_verify_passphrase",
        "auth_lock_session",
        "auth_update_passphrase",
    }
)

ALL_AUTHENTICATED_TOOLS = AUTH_ONLY_TOOLS | PROTECTED_TOOL_NAMES
