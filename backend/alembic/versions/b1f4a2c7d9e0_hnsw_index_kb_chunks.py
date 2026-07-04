"""hnsw index on kb_chunks.embedding (issue #14 / TASK-0302)

Индекс HNSW под косинусную метрику: убирает полный последовательный скан
kb_chunks на каждый RAG-запрос. Строится после наличия данных, но создание
на пустой таблице дёшево.

Revision ID: b1f4a2c7d9e0
Revises: 269fa6357103
Create Date: 2026-07-04 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b1f4a2c7d9e0'
down_revision: Union[str, None] = '269fa6357103'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_kb_chunks_embedding_hnsw"


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {_INDEX} ON kb_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_INDEX}")
