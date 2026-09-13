"""Add SMS activation tables and seed popular services and regions."""
from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "c9d8e7f6a5b4"
branch_labels = None
depends_on = None


def upgrade():
    # 1. sms_service_configs
    sms_services_table = op.create_table(
        "sms_service_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_code", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("name_en", sa.String(128), nullable=False),
        sa.Column("name_ar", sa.String(128), nullable=False),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # 2. sms_country_configs
    sms_countries_table = op.create_table(
        "sms_country_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("country_code", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("name_en", sa.String(128), nullable=False),
        sa.Column("name_ar", sa.String(128), nullable=False),
        sa.Column("flag_emoji", sa.String(16), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # 3. sms_activations
    op.create_table(
        "sms_activations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("batstore_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("activation_id", sa.String(64), nullable=False, index=True),
        sa.Column("service", sa.String(64), nullable=False),
        sa.Column("country", sa.String(64), nullable=False),
        sa.Column("operator", sa.String(64), nullable=False, server_default="any"),
        sa.Column("phone", sa.String(64), nullable=False),
        sa.Column("sms_code", sa.String(32), nullable=True),
        sa.Column("sms_text", sa.Text(), nullable=True),
        sa.Column("cost_rub", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sell_price_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_sms_act_tg_status", "sms_activations", ["telegram_id", "status"])
    op.create_index("idx_sms_act_order", "sms_activations", ["order_id"])
    op.create_index("idx_sms_act_upstream", "sms_activations", ["activation_id"])

    # Seed popular services
    op.bulk_insert(
        sms_services_table,
        [
            {"service_code": "telegram", "name_en": "Telegram", "name_ar": "تيليجرام", "icon": "fa-brands fa-telegram", "is_enabled": True, "sort_order": 1},
            {"service_code": "whatsapp", "name_en": "WhatsApp", "name_ar": "واتساب", "icon": "fa-brands fa-whatsapp", "is_enabled": True, "sort_order": 2},
            {"service_code": "openai", "name_en": "ChatGPT / OpenAI", "name_ar": "شات جي بي تي", "icon": "fa-solid fa-robot", "is_enabled": True, "sort_order": 3},
            {"service_code": "google", "name_en": "Google / Gmail", "name_ar": "جوجل / جيميل", "icon": "fa-brands fa-google", "is_enabled": True, "sort_order": 4},
            {"service_code": "instagram", "name_en": "Instagram", "name_ar": "إنستغرام", "icon": "fa-brands fa-instagram", "is_enabled": True, "sort_order": 5},
            {"service_code": "tiktok", "name_en": "TikTok", "name_ar": "تيك توك", "icon": "fa-brands fa-tiktok", "is_enabled": True, "sort_order": 6},
            {"service_code": "discord", "name_en": "Discord", "name_ar": "ديسكورد", "icon": "fa-brands fa-discord", "is_enabled": True, "sort_order": 7},
            {"service_code": "steam", "name_en": "Steam", "name_ar": "ستيم", "icon": "fa-brands fa-steam", "is_enabled": True, "sort_order": 8},
            {"service_code": "twitter", "name_en": "X / Twitter", "name_ar": "إكس / تويتر", "icon": "fa-brands fa-x-twitter", "is_enabled": True, "sort_order": 9},
            {"service_code": "microsoft", "name_en": "Microsoft", "name_ar": "مايكروسوفت", "icon": "fa-brands fa-microsoft", "is_enabled": True, "sort_order": 10},
        ],
    )

    # Seed good-rate regions
    op.bulk_insert(
        sms_countries_table,
        [
            {"country_code": "usa", "name_en": "United States", "name_ar": "الولايات المتحدة", "flag_emoji": "🇺🇸", "is_enabled": True, "sort_order": 1},
            {"country_code": "england", "name_en": "United Kingdom", "name_ar": "المملكة المتحدة", "flag_emoji": "🇬🇧", "is_enabled": True, "sort_order": 2},
            {"country_code": "netherlands", "name_en": "Netherlands", "name_ar": "هولندا", "flag_emoji": "🇳🇱", "is_enabled": True, "sort_order": 3},
            {"country_code": "germany", "name_en": "Germany", "name_ar": "ألمانيا", "flag_emoji": "🇩🇪", "is_enabled": True, "sort_order": 4},
            {"country_code": "poland", "name_en": "Poland", "name_ar": "بولندا", "flag_emoji": "🇵🇱", "is_enabled": True, "sort_order": 5},
            {"country_code": "sweden", "name_en": "Sweden", "name_ar": "السويد", "flag_emoji": "🇸🇪", "is_enabled": True, "sort_order": 6},
            {"country_code": "france", "name_en": "France", "name_ar": "فرنسا", "flag_emoji": "🇫🇷", "is_enabled": True, "sort_order": 7},
            {"country_code": "canada", "name_en": "Canada", "name_ar": "كندا", "flag_emoji": "🇨🇦", "is_enabled": True, "sort_order": 8},
            {"country_code": "indonesia", "name_en": "Indonesia", "name_ar": "إندونيسيا", "flag_emoji": "🇮🇩", "is_enabled": True, "sort_order": 9},
            {"country_code": "malaysia", "name_en": "Malaysia", "name_ar": "ماليزيا", "flag_emoji": "🇲🇾", "is_enabled": True, "sort_order": 10},
            {"country_code": "turkey", "name_en": "Turkey", "name_ar": "تركيا", "flag_emoji": "🇹🇷", "is_enabled": True, "sort_order": 11},
            {"country_code": "brazil", "name_en": "Brazil", "name_ar": "البرازيل", "flag_emoji": "🇧🇷", "is_enabled": True, "sort_order": 12},
            {"country_code": "kazakhstan", "name_en": "Kazakhstan", "name_ar": "كازاخستان", "flag_emoji": "🇰🇿", "is_enabled": True, "sort_order": 13},
        ],
    )


def downgrade():
    op.drop_table("sms_activations")
    op.drop_table("sms_country_configs")
    op.drop_table("sms_service_configs")
