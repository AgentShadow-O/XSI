# XSI v2 Phase 2 Rollback Guide

Generated: 2026-06-11

## Backup Location

The Phase 2 rollback backup is stored at:

```text
migration-backups/phase2-current/
```

Contents:

- `data/xsi.db`
- `config/config.yaml`
- `exports/user_settings_backup.json`
- `exports/existing_rules_backup.json`
- `exports/users_backup.json`
- `exports/sqlite_schema_snapshot.json`
- `BACKUP_MANIFEST.json`
- `restore_phase2_backup.ps1`

At backup time, no `data/xsi.db-wal` or `data/xsi.db-shm` files were present.

## Backup Snapshot

Database counts captured in the manifest:

```text
devices 1
events 3550862
alerts 3528076
processes 1
network_activity 1
actions 2969
rules 0
users 0
settings 1
```

## Before Rollback

1. Stop the backend server, frontend preview server, agents, and any process that may write to `data/xsi.db`.
2. Confirm no Python, Uvicorn, Gunicorn, or agent process is actively using the database.
3. If preserving the failed state is useful, copy current `data/` and `config.yaml` elsewhere before restoring.

## Dry Run

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\migration-backups\phase2-current\restore_phase2_backup.ps1
```

This prints the files that would be restored without overwriting anything.

## Apply Rollback

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\migration-backups\phase2-current\restore_phase2_backup.ps1 -Apply
```

This restores:

- `migration-backups/phase2-current/data/xsi.db` to `data/xsi.db`
- optional WAL/SHM sidecars if present in the backup
- `migration-backups/phase2-current/config/config.yaml` to `config.yaml`

## Verify Rollback

After rollback, verify the database opens and table counts match the backup snapshot:

```powershell
python - <<'PY'
import sqlite3
conn = sqlite3.connect('data/xsi.db')
for table in ['devices','events','alerts','processes','network_activity','actions','rules','users','settings']:
    print(table, conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
conn.close()
PY
```

Then run:

```powershell
python -m unittest discover -s tests -v
npm.cmd run build
```

## Manifest Verification

Backup hashes are recorded in:

```text
migration-backups/phase2-current/BACKUP_MANIFEST.json
```

Use the manifest to confirm backup file sizes and SHA-256 hashes before restoring after any suspected disk or copy issue.

## Rollback Boundary

This rollback guide covers Phase 2 backup state only. It restores database and config files captured before v2 migration work. It does not roll back future source-code changes unless those changes are separately tracked or backed up.
