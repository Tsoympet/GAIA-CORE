# ADR 0003: AES-GCM field encryption for local stores

## Status

Accepted for the local continuity, evidence, and organism stores. Those
capabilities remain partial. The light client is out of scope for this
decision.

## Context

The SQLite files can contain objectives, working context, evidence bodies, and
memory text. The hash chains detect corruption. They do not hide those fields
from someone who can read the file.

Python's standard library has no AES-GCM implementation. A local cipher needs
a maintained library.

## Decision

Add `cryptography` and seal individual text fields with AES-GCM when the
caller supplies a 32-byte key.

- The on-disk value is prefixed with `gaia-enc-v1:` so older plaintext rows
  remain readable.
- Opening a store with a key seals plaintext rows that are still present.
- Digests stored in headers and checkpoint rows stay hashes of the plaintext.
  Verification decrypts first, then hashes.
- A missing or wrong key raises `DataKeyError` or reports the store as
  degraded. It does not return ciphertext as if it were content, and it does
  not quarantine checkpoints, because a bad key and a tampered ciphertext
  cannot be distinguished.
- `gaia data-key` writes a new key file with mode `0600` and refuses to
  overwrite an existing file. The key is not stored in the SQLite file and is
  not printed.
- Unconfigured runtimes keep writing plaintext. Existing tests and default
  `create_runtime()` stay on that path.

## Consequences

- Operators who configure a data key can restart and read their stores.
- Losing the key loses the sealed text. Copy the key file with the database.
- The hash chain is still not cryptographic immutability.
- This is not whole-file encryption. SQLite page headers, ids, and unsealed
  columns remain readable.
- `cryptography` is Apache-2.0 OR BSD-3-Clause. It brings `cffi` (MIT) and
  `pycparser` (BSD). The project license stays MIT.

## Rollback

Stop the runtime. Restore a copy of the SQLite file taken before sealing, or
keep the data key and leave the sealed file in place. Removing the
`cryptography` dependency requires reverting this milestone. Older runtimes
that do not understand `gaia-enc-v1:` cannot read sealed fields.
