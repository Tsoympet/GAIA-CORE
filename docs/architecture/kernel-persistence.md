# Cognitive Kernel Persistence

## Status

R1.2 implements versioned, durable Cognitive Kernel state using SQLite while preserving an in-memory mode for isolated and test runtimes.

## Stored state

- kernel goals, including lifecycle, project binding, priorities, metadata, and failure or pause reasons;
- kernel executions, including status, budgets, measured usage, verification reports, timestamps, and errors;
- a singleton schema-version record used for explicit migrations.

## Durability behavior

`SQLiteKernelStore` uses atomic upserts, WAL mode, full synchronous writes, stable JSON payloads, indexed execution lookup fields, explicit deletion methods, and the SQLite online-backup API.

A runtime can enable durable kernel state through:

```python
create_runtime(kernel_store_path=".gaia/kernel.sqlite3")
```

or the `GAIA_KERNEL_DB` environment variable.

## Restart recovery

On startup, the Cognitive Kernel loads persisted goals and executions. Any execution left in `pending` or `running` state is changed to `interrupted`, its error records that a runtime restart occurred, and its active goal is changed to `paused`.

This recovery is intentionally conservative. It does not silently repeat work or claim that an interrupted task completed. Full checkpoint-based resumption belongs to Cognitive Continuity in R2.

## Backup and deletion

- durable stores can create consistent SQLite backups through `backup_to`;
- terminal execution records can be deleted explicitly;
- completed, failed, or cancelled goals can be deleted explicitly;
- active or paused goals and active executions cannot be deleted.

## Remaining work

- signed Cognitive Continuity checkpoints;
- selective restore and retention policy;
- encrypted backup packaging;
- migration CLI and release automation;
- evidence-ledger linkage;
- project-level backup orchestration;
- desktop backup and recovery controls.
