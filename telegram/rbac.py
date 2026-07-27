from typing import List
from config import settings

class RBACManager:
    OWNER_ROLE = "owner"
    ADMIN_ROLE = "admin"
    CASHIER_ROLE = "kasir"
    PUBLIC_ROLE = "public"

    RESTRICTED_TOOLS = {
        "owner": [
            "get_stock", "find_product", "get_low_stock", "get_low_stock_alert",
            "get_expiring_products", "get_daily_revenue", "get_transaction_summary",
            "get_top_products", "run_profit_analysis", "sync_to_gsheets",
            "predict_restock", "get_restock_history", "get_inventory_history",
            "get_customer_debt",
        ],
        "admin": [
            "get_stock", "find_product", "get_low_stock", "get_low_stock_alert",
            "get_expiring_products", "get_daily_revenue", "get_transaction_summary",
            "get_top_products", "predict_restock", "get_restock_history", "get_inventory_history",
            "get_customer_debt",
        ],
        "kasir": [
            "get_stock", "find_product", "get_low_stock", "get_low_stock_alert",
            "get_daily_revenue", "get_expiring_products",
            "get_restock_history", "get_customer_debt",
        ],
        "public": [
            "get_stock", "find_product",
        ]
    }

    @classmethod
    def get_user_role(cls, user_id: int) -> str:
        owners = settings.get_owner_ids()
        admins = settings.get_admin_ids()
        cashiers = settings.get_cashier_ids()

        if user_id in owners:
            return cls.OWNER_ROLE
        elif user_id in admins:
            return cls.ADMIN_ROLE
        elif user_id in cashiers:
            return cls.CASHIER_ROLE

        # Jika tidak ada list yang dikonfigurasi, default owner (initial setup)
        if not owners and not admins and not cashiers:
            return cls.OWNER_ROLE

        return cls.PUBLIC_ROLE

    @classmethod
    def can_access_tool(cls, role: str, tool_name: str) -> bool:
        allowed = cls.RESTRICTED_TOOLS.get(role, cls.RESTRICTED_TOOLS["public"])
        return tool_name in allowed

