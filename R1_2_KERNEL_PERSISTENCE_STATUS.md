# R1.2 Kernel Persistence Status

Implemented:

- `KernelStore` persistence contract;
- process-local `InMemoryKernelStore`;
- versioned `SQLiteKernelStore` schema and migration to version 1;
- atomic goal and execution upserts;
- durable load-on-start;
- conservative restart recovery to `interrupted` executions and `paused` goals;
- explicit terminal-record deletion;
- consistent SQLite backup;
- runtime configuration through `kernel_store_path` or `GAIA_KERNEL_DB`;
- storage status surfaced through `KernelStatus`;
- unit and integration tests.

The Cognitive Kernel remains `PARTIAL`. R2 must implement signed checkpoints and true task resumption rather than only interruption detection.
