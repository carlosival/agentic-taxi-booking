from alembic.operations.ops import (
    DropColumnOp,
    DropTableOp,
    AlterColumnOp,
    DropConstraintOp,
)


DANGEROUS_OPS = (
    DropColumnOp,
    DropTableOp,
    DropConstraintOp,
)


def check_migration_safety(ops_container):
    """
    Recursively inspect Alembic operations for destructive changes.
    Raises RuntimeError if dangerous ops are found.
    """

    # Ensure we can iterate whether it's a single op or an ops container
    for op in getattr(ops_container, "ops", []):
        # 🚨 Destructive schema operations
        if isinstance(op, DANGEROUS_OPS):
            raise RuntimeError(
                f"🚨 Unsafe migration detected: {op.__class__.__name__} — manual review required."
            )

        # ⚠️ Altering nullable -> NOT NULL
        if isinstance(op, AlterColumnOp):
            if op.modify_nullable and op.existing_nullable and not op.nullable:
                raise RuntimeError(
                    f"🚨 Making column '{op.column_name}' NOT NULL — ensure data is clean first."
                )

        # 🔁 Recurse into batch or nested operations
        if hasattr(op, "ops"):
            check_migration_safety(op)
