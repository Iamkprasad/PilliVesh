import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "state.db"


def connect():
    return sqlite3.connect(DB)


def add_task(project, title, priority=5, notes=""):
    with connect() as db:
        db.execute(
            """
            INSERT INTO tasks (project, title, priority, notes)
            VALUES (?, ?, ?, ?)
            """,
            (project, title, priority, notes),
        )
        db.commit()


def active_tasks(project=None):
    with connect() as db:
        if project:
            return db.execute(
                """
                SELECT id, title, status, priority, notes
                FROM tasks
                WHERE project = ? AND status = 'active'
                ORDER BY priority DESC, updated_at DESC
                """,
                (project,),
            ).fetchall()

        return db.execute(
            """
            SELECT id, project, title, status, priority, notes
            FROM tasks
            WHERE status = 'active'
            ORDER BY priority DESC, updated_at DESC
            """
        ).fetchall()


if __name__ == "__main__":
    print("Task manager ready.")
