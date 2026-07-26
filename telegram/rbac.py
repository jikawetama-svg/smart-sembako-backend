from typing import List
from config import settings

class RBACManager:
    OWNER_ROLE = "owner"
    CASHIER_ROLE = "kasir"
    PUBLIC_ROLE = "public"

    # Restricted tools requiring Owner or Cashier privilege
    RESTRICTED_TOOLS = {
        "owner": [
            "get_stock", "find_product", "get_low_stock", 
            "get_daily_revenue", "get_transaction_summary", 
            "get_top_products", "run_profit_analysis", 
            "sync_to_gsheets", "predict_restock", "get_expiring_products"
        ],
        "kasir": [
            "get_stock", "find_product", "get_low_stock", 
            "get_daily_revenue", "get_expiring_products"
        ],
        "public": [
            "get_stock", "find_product"
        ]
    }

    @classmethod
    def get_user_role(cls, user_id: int) -> str:
        owners = settings.get_owner_ids()
        cashiers = settings.get_cashier_ids()

        if user_id in owners:
            return cls.OWNER_ROLE
        elif user_id in cashiers:
            return cls.CASHIER_ROLE
        
        # If no explicit list configured, default to owner for initial setup
        if not owners and not cashiers:
            return cls.OWNER_ROLE
            
        return cls.PUBLIC_ROLE

    @classmethod
    def can_access_tool(cls, role: str, tool_name: str) -> bool:
        allowed = cls.RESTRICTED_TOOLS.get(role, cls.RESTRICTED_TOOLS["public"])
        return tool_name in allowed
