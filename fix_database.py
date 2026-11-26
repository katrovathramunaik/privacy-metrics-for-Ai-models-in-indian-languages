with open('src/privacy_metrics/database.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix get_latest_run to also look for completed runs
old = '''    def get_latest_run(self, command: str) -> Optional[str]:
        """Get the latest incomplete run for a command."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT run_id FROM runs 
                WHERE command = ? AND status IN ('running', 'cancelled')
                ORDER BY started_at DESC LIMIT 1""",
                (command,)
            ).fetchone()
            return row["run_id"] if row else None'''

new = '''    def get_latest_run(self, command: str) -> Optional[str]:
        """Get the latest run for a command (including completed)."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT run_id FROM runs 
                WHERE command = ? 
                ORDER BY started_at DESC LIMIT 1""",
                (command,)
            ).fetchone()
            return row["run_id"] if row else None'''

if old in content:
    content = content.replace(old, new)
    with open('src/privacy_metrics/database.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed get_latest_run')
else:
    print('Could not find the method to replace')

print('Done')