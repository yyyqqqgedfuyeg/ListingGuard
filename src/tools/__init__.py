"""
Filename: __init__.py
Description: ListingGuard 电商合规工具链统一导出接口。
Author: ListingGuard Team
"""

from src.tools.scan_tool import scan_listing
from src.tools.diagnose_tool import diagnose_violation
from src.tools.rag_tool import query_regulation, get_regulation_retriever
from src.tools.rewrite_tool import rewrite_compliant
from src.tools.verify_tool import verify_rewrite
from src.tools.batch_tool import batch_scan
from src.tools.report_tool import export_report
from src.tools.db_tools import (
    db_query_products,
    db_get_product_detail,
    db_create_product,
    db_update_product,
    db_delete_product,
    db_query_posts,
    db_get_post_detail,
    db_create_post,
    db_update_post,
    db_delete_post,
    db_audit_post,
    get_db_manager,
    set_db_manager,
)

ALL_DB_TOOLS = [
    db_query_products,
    db_get_product_detail,
    db_create_product,
    db_update_product,
    db_delete_product,
    db_query_posts,
    db_get_post_detail,
    db_create_post,
    db_update_post,
    db_delete_post,
    db_audit_post,
]

ALL_COMPLIANCE_TOOLS = [
    scan_listing,
    diagnose_violation,
    query_regulation,
    rewrite_compliant,
    verify_rewrite,
    batch_scan,
    export_report,
    *ALL_DB_TOOLS,
]

__all__ = [
    "scan_listing",
    "diagnose_violation",
    "query_regulation",
    "get_regulation_retriever",
    "rewrite_compliant",
    "verify_rewrite",
    "batch_scan",
    "export_report",
    "db_query_products",
    "db_get_product_detail",
    "db_create_product",
    "db_update_product",
    "db_delete_product",
    "db_query_posts",
    "db_get_post_detail",
    "db_create_post",
    "db_update_post",
    "db_delete_post",
    "db_audit_post",
    "get_db_manager",
    "set_db_manager",
    "ALL_DB_TOOLS",
    "ALL_COMPLIANCE_TOOLS",
]
