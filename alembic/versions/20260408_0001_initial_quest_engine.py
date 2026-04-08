"""initial quest engine schema

Revision ID: 20260408_0001
Revises:
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260408_0001"
down_revision = None
branch_labels = None
depends_on = None

role_enum = sa.Enum("PARTICIPANT", "PARTNER_ADMIN", "SYSTEM_ADMIN", name="rolename")
checkin_enum = sa.Enum("QR", name="checkintype")


def upgrade() -> None:
    role_enum.create(op.get_bind(), checkfirst=True)
    checkin_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("system_role", role_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "participant_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_participant_profiles_user_id", "participant_profiles", ["user_id"], unique=False)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=False)

    op.create_table(
        "org_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_member"),
    )
    op.create_index("ix_org_memberships_org_id", "org_memberships", ["org_id"], unique=False)
    op.create_index("ix_org_memberships_user_id", "org_memberships", ["user_id"], unique=False)

    op.create_table(
        "quests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("enforce_order", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("points_total", sa.Integer(), nullable=False),
    )
    op.create_index("ix_quests_org_id", "quests", ["org_id"], unique=False)

    op.create_table(
        "quest_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("qr_code", sa.String(length=180), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.UniqueConstraint("quest_id", "position", name="uq_quest_checkpoint_position"),
    )
    op.create_index("ix_quest_checkpoints_quest_id", "quest_checkpoints", ["quest_id"], unique=False)
    op.create_index("ix_quest_checkpoints_qr_code", "quest_checkpoints", ["qr_code"], unique=False)

    op.create_table(
        "quest_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("quest_id", "user_id", name="uq_quest_participant"),
    )
    op.create_index("ix_quest_participants_quest_id", "quest_participants", ["quest_id"], unique=False)
    op.create_index("ix_quest_participants_user_id", "quest_participants", ["user_id"], unique=False)

    op.create_table(
        "checkin_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("checkpoint_id", sa.Integer(), sa.ForeignKey("quest_checkpoints.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("checkin_type", checkin_enum, nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_checkin_events_quest_id", "checkin_events", ["quest_id"], unique=False)
    op.create_index("ix_checkin_events_checkpoint_id", "checkin_events", ["checkpoint_id"], unique=False)
    op.create_index("ix_checkin_events_user_id", "checkin_events", ["user_id"], unique=False)

    op.create_table(
        "progress_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False),
        sa.Column("total_points", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("quest_id", "user_id", name="uq_quest_progress"),
    )
    op.create_index("ix_progress_records_quest_id", "progress_records", ["quest_id"], unique=False)
    op.create_index("ix_progress_records_user_id", "progress_records", ["user_id"], unique=False)

    op.create_table(
        "rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("points_cost", sa.Integer(), nullable=False),
    )
    op.create_index("ix_rewards_org_id", "rewards", ["org_id"], unique=False)

    op.create_table(
        "reward_redemptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reward_id", sa.Integer(), sa.ForeignKey("rewards.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_reward_redemptions_reward_id", "reward_redemptions", ["reward_id"], unique=False)
    op.create_index("ix_reward_redemptions_user_id", "reward_redemptions", ["user_id"], unique=False)

    op.create_table(
        "leaderboard_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_leaderboard_snapshots_quest_id", "leaderboard_snapshots", ["quest_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("leaderboard_snapshots")
    op.drop_table("reward_redemptions")
    op.drop_table("rewards")
    op.drop_table("progress_records")
    op.drop_table("checkin_events")
    op.drop_table("quest_participants")
    op.drop_table("quest_checkpoints")
    op.drop_table("quests")
    op.drop_table("org_memberships")
    op.drop_table("organizations")
    op.drop_table("participant_profiles")
    op.drop_table("users")
    checkin_enum.drop(op.get_bind(), checkfirst=True)
    role_enum.drop(op.get_bind(), checkfirst=True)
