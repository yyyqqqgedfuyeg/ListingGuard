"""
Filename: manager.py
Description: SQLite 数据库持久化管理器，提供完整商品、营销帖子、RBAC用户及管理员二次确认令牌的存储与CRUD操作。
Author: ListingGuard Team
"""

import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.database.models import (
    AuditLog,
    ConfirmationRequest,
    Post,
    PostStatus,
    Product,
    ProductStatus,
    User,
    UserRole,
)
from src.models.enums import Platform


class DatabaseManager:
    """电商商品合规与营销帖子 SQLite 数据库管理器。"""

    DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "listing_guard.db"

    def __init__(self, db_path: Optional[str | Path] = None):
        """初始化数据库连接，自动建表并按需预填充基准数据。

        Args:
            db_path (Optional[str | Path]): 数据库文件路径，支持 ":memory:" 用于内存隔离测试。
        """
        if db_path == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path) if db_path else self.DEFAULT_DB_PATH
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(self.db_path)

        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """获取或创建活跃数据库连接。"""
        if self.db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:")
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA foreign_keys = ON;")
            return self._conn
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn

    def close(self):
        """关闭数据库连接（主要针对内存库）。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _init_db(self):
        """创建基础表结构与索引。"""
        conn = self.get_connection()
        cur = conn.cursor()

        # 1. users 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                display_name TEXT,
                email TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # 2. products 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                price REAL,
                original_price REAL,
                stock INTEGER DEFAULT 100,
                status TEXT NOT NULL,
                attributes TEXT,
                images TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 3. posts 表（与商品关联）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                tags TEXT,
                compliance_status TEXT NOT NULL,
                risk_score REAL DEFAULT 0.0,
                flagged_violations TEXT,
                author_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(product_id) ON DELETE CASCADE
            )
        """)

        # 4. audit_logs 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                operator_role TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # 5. confirmation_requests 表（二次确认凭证）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS confirmation_requests (
                token TEXT PRIMARY KEY,
                action_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                status TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()

        # 检查是否已包含种子数据，若无则初始化
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            self.seed_initial_data(conn)

        if self.db_path != ":memory:":
            conn.close()

    def seed_initial_data(self, conn: Optional[sqlite3.Connection] = None):
        """预填充符合各电商平台特性的真实基准商品、帖子与用户数据。"""
        should_close = False
        if conn is None:
            conn = self.get_connection()
            if self.db_path != ":memory:":
                should_close = True

        cur = conn.cursor()
        now_str = datetime.now().isoformat()

        # 1. 基础用户 (RBAC 覆盖)
        seed_users = [
            ("USR-ADMIN-001", "admin_super", "ADMIN", "系统超级合规管理员", "admin@listingguard.com", now_str),
            ("USR-EMP-001", "ops_specialist", "EMPLOYEE", "电商运营审核专员", "ops@listingguard.com", now_str),
            ("USR-CUST-001", "seller_vip", "CUSTOMER", "认证品牌商家卖家", "seller@brand.com", now_str),
        ]
        cur.executemany(
            "INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?, ?)",
            seed_users
        )

        # 2. 基准商品
        seed_products = [
            (
                "PROD-TB-001",
                "taobao",
                "天然草本补水修复精华液 50ml",
                "萃取积雪草、玻尿酸精华，深层补水，温和舒缓肌肤干燥紧绷，适用于各类脆弱敏肌日常修护护理。",
                "美妆个护",
                199.0,
                299.0,
                500,
                "APPROVED",
                json.dumps({"brand": "NatureCare", "origin": "中国上海", "skin_type": "敏感肌/干皮"}),
                json.dumps(["https://img.example.com/tb001_main.jpg", "https://img.example.com/tb001_detail.jpg"]),
                "USR-CUST-001",
                now_str,
                now_str,
            ),
            (
                "PROD-PDD-001",
                "pdd",
                "高纤维即食无蔗糖纯燕麦片 1kg",
                "精选澳洲阳光燕麦，物理碾压轻烘焙，富含膳食纤维与β-葡聚糖，无额外添加蔗糖与香精，早餐代餐饱腹佳选。",
                "食品保健",
                29.9,
                49.9,
                2000,
                "APPROVED",
                json.dumps({"net_weight": "1kg", "sugar_free": "是", "shelf_life": "12个月"}),
                json.dumps(["https://img.example.com/pdd001_main.jpg"]),
                "USR-CUST-001",
                now_str,
                now_str,
            ),
            (
                "PROD-EBAY-001",
                "ebay",
                "Vintage Mechanical Diver Watch 200m Waterproof",
                "Authentic stainless steel automatic winding dive watch with sapphire crystal, luminous dials, and 200m water resistance certified.",
                "钟表珠宝",
                129.99,
                159.99,
                60,
                "APPROVED",
                json.dumps({"movement": "Automatic", "case_material": "316L Steel", "waterproof": "200m"}),
                json.dumps(["https://img.example.com/ebay001_main.jpg"]),
                "USR-CUST-001",
                now_str,
                now_str,
            ),
            (
                "PROD-TB-002",
                "taobao",
                "全网第一顶级生发神水30天彻底根治脱发",
                "绝密古方生发神油，全球最好配方，30天彻底治愈雄脱斑秃，原价9999现价9.9元亏本甩卖，永不再复发！",
                "美妆个护",
                9.9,
                9999.0,
                10,
                "REJECTED",
                json.dumps({"efficacy": "根治脱发", "fake_promo": "true"}),
                json.dumps(["https://img.example.com/tb002_viol.jpg"]),
                "USR-CUST-001",
                now_str,
                now_str,
            ),
        ]
        cur.executemany(
            "INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            seed_products
        )

        # 3. 商品关联推广种草帖子
        seed_posts = [
            (
                "POST-001",
                "PROD-TB-001",
                "xiaohongshu",
                "干皮换季自救！这款草本精华补水太润了",
                "最近换季脸颊泛红起皮，试用了这瓶积雪草精华一周，上脸温和水润，吸收很快不黏腻，皮肤状态稳定多了，成分党真心推荐！",
                json.dumps(["换季护肤", "干皮精华", "护肤日常"]),
                "COMPLIANT",
                0.0,
                json.dumps([]),
                "USR-CUST-001",
                now_str,
                now_str,
            ),
            (
                "POST-002",
                "PROD-TB-001",
                "xiaohongshu",
                "全网第一神仙精华！一秒见效彻底消斑",
                "姐妹们一定要买！全网第一顶级精华，一秒见效，三天彻底治愈所有色斑，原价999现价9.9，绝无副作用！",
                json.dumps(["美白神仙水", "一秒见效", "祛斑神器"]),
                "FLAGGED",
                0.95,
                json.dumps([
                    {"category": "absolute_claim", "severity": "BLOCK", "matched_text": "全网第一"},
                    {"category": "false_efficacy", "severity": "BLOCK", "matched_text": "彻底治愈"},
                    {"category": "absolute_claim", "severity": "BLOCK", "matched_text": "一秒见效"},
                    {"category": "price_fraud", "severity": "BLOCK", "matched_text": "原价999现价9.9"}
                ]),
                "USR-CUST-001",
                now_str,
                now_str,
            ),
            (
                "POST-003",
                "PROD-PDD-001",
                "guangguang",
                "减脂期打工人早餐！0蔗糖纯燕麦饱腹感绝了",
                "每天早上热水一冲或者泡热牛奶，口感很有嚼劲。无添加蔗糖配方，饱腹感持续一整个上午，控卡减脂期必备主食！",
                json.dumps(["低卡饮食", "纯燕麦", "减脂早餐"]),
                "COMPLIANT",
                0.0,
                json.dumps([]),
                "USR-CUST-001",
                now_str,
                now_str,
            ),
            (
                "POST-004",
                "PROD-PDD-001",
                "weibo",
                "吃完3天降三高！亏本甩卖原价999现价9.9",
                "神奇燕麦神粮！药效显著三天降血压降血糖降三高，倒闭清仓亏本大甩卖，数量有限速抢！",
                json.dumps(["降三高神粮", "亏本甩卖", "限时抢购"]),
                "FLAGGED",
                0.92,
                json.dumps([
                    {"category": "false_efficacy", "severity": "BLOCK", "matched_text": "降三高"},
                    {"category": "false_efficacy", "severity": "BLOCK", "matched_text": "药效"},
                    {"category": "price_fraud", "severity": "BLOCK", "matched_text": "原价999现价9.9"}
                ]),
                "USR-CUST-001",
                now_str,
                now_str,
            ),
            (
                "POST-005",
                "PROD-EBAY-001",
                "instagram",
                "Hands-on review: Classic automatic dive watch craftsmanship",
                "Checking out this 200m diver today. Robust 316L stainless steel build, smooth bezel action, and luminous markers make it a reliable daily beater for watch enthusiasts.",
                json.dumps(["watches", "diverwatch", "wristcheck", "horology"]),
                "COMPLIANT",
                0.0,
                json.dumps([]),
                "USR-CUST-001",
                now_str,
                now_str,
            ),
        ]
        cur.executemany(
            "INSERT OR IGNORE INTO posts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            seed_posts
        )

        conn.commit()
        if should_close:
            conn.close()

    # ==================== User CRUD ====================

    def get_user(self, user_id: str) -> Optional[User]:
        """按 ID 查询用户。"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if self.db_path != ":memory:":
            conn.close()
        if not row:
            return None
        return User(
            user_id=row["user_id"],
            username=row["username"],
            role=UserRole(row["role"]),
            display_name=row["display_name"] or "",
            email=row["email"] or "",
            created_at=row["created_at"],
        )

    def list_users(self) -> List[User]:
        """获取所有系统用户。"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users ORDER BY created_at ASC")
        rows = cur.fetchall()
        if self.db_path != ":memory:":
            conn.close()
        return [
            User(
                user_id=r["user_id"],
                username=r["username"],
                role=UserRole(r["role"]),
                display_name=r["display_name"] or "",
                email=r["email"] or "",
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # ==================== Product CRUD ====================

    def get_product(self, product_id: str) -> Optional[Product]:
        """获取单个商品信息。"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
        row = cur.fetchone()
        if self.db_path != ":memory:":
            conn.close()
        if not row:
            return None
        return Product(
            product_id=row["product_id"],
            platform=Platform(row["platform"]),
            title=row["title"],
            description=row["description"] or "",
            category=row["category"],
            price=row["price"],
            original_price=row["original_price"],
            stock=row["stock"],
            status=ProductStatus(row["status"]),
            attributes=json.loads(row["attributes"] or "{}"),
            images=json.loads(row["images"] or "[]"),
            created_by=row["created_by"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_products(
        self,
        category: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Product]:
        """多条件筛选查询商品。"""
        conn = self.get_connection()
        cur = conn.cursor()
        query = "SELECT * FROM products WHERE 1=1"
        params: List[Any] = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        if self.db_path != ":memory:":
            conn.close()

        return [
            Product(
                product_id=r["product_id"],
                platform=Platform(r["platform"]),
                title=r["title"],
                description=r["description"] or "",
                category=r["category"],
                price=r["price"],
                original_price=r["original_price"],
                stock=r["stock"],
                status=ProductStatus(r["status"]),
                attributes=json.loads(r["attributes"] or "{}"),
                images=json.loads(r["images"] or "[]"),
                created_by=r["created_by"] or "",
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def create_product(self, product: Product) -> Product:
        """新增商品。"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO products (
                product_id, platform, title, description, category,
                price, original_price, stock, status, attributes,
                images, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product.product_id,
                product.platform.value,
                product.title,
                product.description,
                product.category,
                product.price,
                product.original_price,
                product.stock,
                product.status.value,
                json.dumps(product.attributes, ensure_ascii=False),
                json.dumps(product.images, ensure_ascii=False),
                product.created_by,
                product.created_at,
                product.updated_at,
            ),
        )
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()
        return product

    def update_product(self, product_id: str, updates: Dict[str, Any]) -> Optional[Product]:
        """更新商品信息。"""
        prod = self.get_product(product_id)
        if not prod:
            return None

        allowed_fields = [
            "title", "description", "category", "price", "original_price",
            "stock", "status", "attributes", "images"
        ]
        set_clauses = []
        params = []
        for k, v in updates.items():
            if k in allowed_fields:
                set_clauses.append(f"{k} = ?")
                if k in ("attributes", "images") and isinstance(v, (dict, list)):
                    params.append(json.dumps(v, ensure_ascii=False))
                elif k == "status" and hasattr(v, "value"):
                    params.append(v.value)
                else:
                    params.append(v)

        if not set_clauses:
            return prod

        now_str = datetime.now().isoformat()
        set_clauses.append("updated_at = ?")
        params.append(now_str)
        params.append(product_id)

        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(f"UPDATE products SET {', '.join(set_clauses)} WHERE product_id = ?", params)
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

        return self.get_product(product_id)

    def delete_product(self, product_id: str) -> bool:
        """物理删除商品（将级联删除其关联的所有营销帖子）。"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE product_id = ?", (product_id,))
        affected = cur.rowcount
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()
        return affected > 0

    # ==================== Post CRUD ====================

    def get_post(self, post_id: str) -> Optional[Post]:
        """获取单个帖子信息。"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,))
        row = cur.fetchone()
        if self.db_path != ":memory:":
            conn.close()
        if not row:
            return None
        return Post(
            post_id=row["post_id"],
            product_id=row["product_id"],
            channel=row["channel"],
            title=row["title"],
            content=row["content"] or "",
            tags=json.loads(row["tags"] or "[]"),
            compliance_status=PostStatus(row["compliance_status"]),
            risk_score=row["risk_score"] or 0.0,
            flagged_violations=json.loads(row["flagged_violations"] or "[]"),
            author_id=row["author_id"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_posts(
        self,
        product_id: Optional[str] = None,
        channel: Optional[str] = None,
        compliance_status: Optional[str] = None,
    ) -> List[Post]:
        """多条件筛选查询营销帖子。"""
        conn = self.get_connection()
        cur = conn.cursor()
        query = "SELECT * FROM posts WHERE 1=1"
        params: List[Any] = []

        if product_id:
            query += " AND product_id = ?"
            params.append(product_id)
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        if compliance_status:
            query += " AND compliance_status = ?"
            params.append(compliance_status)

        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        if self.db_path != ":memory:":
            conn.close()

        return [
            Post(
                post_id=r["post_id"],
                product_id=r["product_id"],
                channel=r["channel"],
                title=r["title"],
                content=r["content"] or "",
                tags=json.loads(r["tags"] or "[]"),
                compliance_status=PostStatus(r["compliance_status"]),
                risk_score=r["risk_score"] or 0.0,
                flagged_violations=json.loads(r["flagged_violations"] or "[]"),
                author_id=r["author_id"] or "",
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def create_post(self, post: Post) -> Post:
        """新增商品关联帖子。"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO posts (
                post_id, product_id, channel, title, content,
                tags, compliance_status, risk_score, flagged_violations,
                author_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post.post_id,
                post.product_id,
                post.channel,
                post.title,
                post.content,
                json.dumps(post.tags, ensure_ascii=False),
                post.compliance_status.value,
                post.risk_score,
                json.dumps(post.flagged_violations, ensure_ascii=False),
                post.author_id,
                post.created_at,
                post.updated_at,
            ),
        )
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()
        return post

    def update_post(self, post_id: str, updates: Dict[str, Any]) -> Optional[Post]:
        """更新帖子信息。"""
        post = self.get_post(post_id)
        if not post:
            return None

        allowed_fields = [
            "title", "content", "tags", "channel",
            "compliance_status", "risk_score", "flagged_violations"
        ]
        set_clauses = []
        params = []
        for k, v in updates.items():
            if k in allowed_fields:
                set_clauses.append(f"{k} = ?")
                if k in ("tags", "flagged_violations") and isinstance(v, (list, dict)):
                    params.append(json.dumps(v, ensure_ascii=False))
                elif k == "compliance_status" and hasattr(v, "value"):
                    params.append(v.value)
                else:
                    params.append(v)

        if not set_clauses:
            return post

        now_str = datetime.now().isoformat()
        set_clauses.append("updated_at = ?")
        params.append(now_str)
        params.append(post_id)

        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(f"UPDATE posts SET {', '.join(set_clauses)} WHERE post_id = ?", params)
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

        return self.get_post(post_id)

    def delete_post(self, post_id: str) -> bool:
        """物理删除帖子。"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))
        affected = cur.rowcount
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()
        return affected > 0

    # ==================== Audit Log CRUD ====================

    def log_action(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        operator_id: str,
        operator_role: UserRole | str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """记录审计日志。"""
        role_str = operator_role.value if hasattr(operator_role, "value") else str(operator_role)
        now_str = datetime.now().isoformat()
        log_id = f"LOG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"

        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_logs (log_id, entity_type, entity_id, action, operator_id, operator_role, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                entity_type,
                entity_id,
                action,
                operator_id,
                role_str,
                json.dumps(details or {}, ensure_ascii=False),
                now_str,
            ),
        )
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

        return AuditLog(
            log_id=log_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            operator_id=operator_id,
            operator_role=UserRole(role_str),
            details=details or {},
            created_at=now_str,
        )

    def get_audit_logs(self, entity_id: Optional[str] = None, limit: int = 50) -> List[AuditLog]:
        """获取审计操作记录。"""
        conn = self.get_connection()
        cur = conn.cursor()
        query = "SELECT * FROM audit_logs"
        params: List[Any] = []
        if entity_id:
            query += " WHERE entity_id = ?"
            params.append(entity_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()
        if self.db_path != ":memory:":
            conn.close()

        return [
            AuditLog(
                log_id=r["log_id"],
                entity_type=r["entity_type"],
                entity_id=r["entity_id"],
                action=r["action"],
                operator_id=r["operator_id"],
                operator_role=UserRole(r["operator_role"]),
                details=json.loads(r["details"] or "{}"),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # ==================== Confirmation Token Management ====================

    def create_confirmation_request(
        self,
        action_type: str,
        target_id: str,
        requested_by: str,
        ttl_seconds: int = 300,
    ) -> ConfirmationRequest:
        """生成管理员高危删除操作二次确认防伪凭证。

        Args:
            action_type (str): 如 delete_product / delete_post
            target_id (str): 目标删除实体 ID
            requested_by (str): 申请操作的用户 ID
            ttl_seconds (int): 凭证有效时长（秒），默认 300 秒（5分钟）

        Returns:
            ConfirmationRequest: 生成的确认申请单
        """
        token = f"CONFIRM_{action_type.upper()}_{target_id}_{secrets.token_hex(6)}"
        now = datetime.now()
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        created_at = now.isoformat()

        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO confirmation_requests (token, action_type, target_id, requested_by, status, expires_at, created_at)
            VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (token, action_type, target_id, requested_by, expires_at, created_at),
        )
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

        return ConfirmationRequest(
            token=token,
            action_type=action_type,
            target_id=target_id,
            requested_by=requested_by,
            status="PENDING",
            expires_at=expires_at,
            created_at=created_at,
        )

    def verify_and_consume_token(
        self,
        token: str,
        action_type: str,
        target_id: str,
    ) -> Tuple[bool, str]:
        """核验并立即作废二次确认令牌。

        Args:
            token (str): 提交的二次确认凭据
            action_type (str): 操作类型
            target_id (str): 目标删除实体 ID

        Returns:
            Tuple[bool, str]: (是否核验通过, 失败原因或成功提示)
        """
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM confirmation_requests WHERE token = ?", (token,))
        row = cur.fetchone()

        if not row:
            if self.db_path != ":memory:":
                conn.close()
            return False, "无效的二次确认令牌 (Token不存在)"

        if row["status"] != "PENDING":
            if self.db_path != ":memory:":
                conn.close()
            return False, f"二次确认令牌状态异常: 已被使用或已作废 (当前状态: {row['status']})"

        if row["action_type"] != action_type or row["target_id"] != target_id:
            if self.db_path != ":memory:":
                conn.close()
            return False, f"二次确认令牌与目标操作不匹配 (期望: {action_type} on {target_id})"

        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires_at:
            cur.execute("UPDATE confirmation_requests SET status = 'EXPIRED' WHERE token = ?", (token,))
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()
            return False, "二次确认令牌已超过有效期，请重新发起删除申请"

        # 标记为已核验
        cur.execute("UPDATE confirmation_requests SET status = 'CONFIRMED' WHERE token = ?", (token,))
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

        return True, "二次确认验证通过"

    def get_confirmation(self, token: str) -> Optional[ConfirmationRequest]:
        """获取凭证信息。"""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM confirmation_requests WHERE token = ?", (token,))
        row = cur.fetchone()
        if self.db_path != ":memory:":
            conn.close()
        if not row:
            return None
        return ConfirmationRequest(
            token=row["token"],
            action_type=row["action_type"],
            target_id=row["target_id"],
            requested_by=row["requested_by"],
            status=row["status"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
        )
