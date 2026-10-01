"""Bind Tier* alerts to their source (they were one-shot)

Revision ID: b7d4e91c53aa
Revises: 9c31be47d5a2
Create Date: 2026-08-24 12:00:00.000000+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b7d4e91c53aa'
down_revision = '9c31be47d5a2'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE system_alert SET source = 'TierJob' WHERE klass IN "
        "('TierJobError', 'TierJobComplete', 'TierSpecialVdevWarning', 'TierSpecialVdevCritical')"
    )


def downgrade():
    pass
