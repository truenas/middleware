"""Name the S3 service s3 rather than truenas_s3

Revision ID: 98358f332844
Revises: b7e3f1a92c48
Create Date: 2026-09-09 21:00:00.000000+00:00

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '98358f332844'
down_revision = 'b7e3f1a92c48'
branch_labels = None
depends_on = None


def upgrade():
    # The row is what service.query reports and what every service name
    # is looked up against, so it has to move with ServiceInterface.name.
    # A row left under the old name matches no registered service:
    # service.systemd_units raises MatchNotFound for it, which drops the
    # service out of the systemd etc render and out of a configuration
    # upload's enable/disable pass without an error either place.
    #
    # The daemon keeps the old name. Its systemd unit, its /etc directory
    # and the services_truenas_s3 table are the truenas_s3 package's, not
    # the API's, and none of them is what a caller names.
    op.execute(text("UPDATE services_services SET srv_service = 's3' WHERE srv_service = 'truenas_s3'"))


def downgrade():
    pass
