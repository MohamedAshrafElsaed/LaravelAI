"""
Add processing_data column to messages table.

This column stores the full processing history (intent, plan, steps, validation)
for assistant messages, enabling complete history replay.
"""
import asyncio
from sqlalchemy import text
from app.core.database import async_engine


async def run_migration():
    """Add processing_data column to messages table if it doesn't exist."""
    async with async_engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'messages' AND column_name = 'processing_data'
        """))
        exists = result.fetchone() is not None

        if not exists:
            print("Adding processing_data column to messages table...")
            await conn.execute(text("""
                ALTER TABLE messages
                ADD COLUMN processing_data JSONB
            """))
            print("Migration completed successfully!")
        else:
            print("Column processing_data already exists, skipping.")


if __name__ == "__main__":
    asyncio.run(run_migration())
