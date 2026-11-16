# CSCI 4707 Lab 2: Second-LRU

This is PostgreSQL 16.0 with a Second-LRU policy for shared buffers. A buffer's
last access is tracked with a global integer counter. Among unpinned buffers,
the second-smallest timestamp is selected; a sole candidate is selected directly.
Equal timestamps are ordered by buffer ID. This is **not LRU-2**.

The integration is based on `part-b` (`5a922d4`), which already contains
`part-a` (`350fa13`). The original `main` is `2f704d1`.

## What changed

Four PostgreSQL source files contain the implementation:

| File under `src/` | Purpose |
| --- | --- |
| `include/storage/buf_internals.h` | Timestamp field and selection snapshot interface |
| `backend/storage/buffer/buf_init.c` | Zero-initialize buffer timestamps |
| `backend/storage/buffer/freelist.c` | Shared counter, candidate selection, output formatting |
| `backend/storage/buffer/bufmgr.c` | Timestamp updates, safe page access and final output |

Part C adds synchronization fixes, tests, documentation, and a submission packager.
See `solution.txt` for the detailed implementation explanation and
`docs/TEST_RESULTS.md` for measured results on macOS and CSE Linux.

The three required output lines are emitted together, for example:

```text
Candidate buffers: 47:560, 8:599, 2:605
Replaced buffer: 8:599
Available Page Space: 128
```

PostgreSQL adds its normal LOG prefix and can append SQL position/context
information. The test parser accepts that metadata. The page-space value uses
`PageGetFreeSpace` on the **old selected page**, reserving one item identifier;
it is zero for an invalid buffer. Only successful claims are logged.

## Build and run everything

Requirements: a C compiler, GNU make, Python 3, and the normal PostgreSQL build
requirements. No third-party Python packages are needed. Run as an ordinary user.
The repository omits `src/timezone/data` (the original broad `data/` ignore rule
also matches that directory), so the build uses `/usr/share/zoneinfo`.

From this source directory, choose a run directory that does not already exist:

```bash
bash tests/lab2/run_all.sh /absolute/path/to/new-lab2-run
```

The script explicitly selects GNU C99 for PostgreSQL 16.0 compatibility with
GCC 15 (whose default C23 mode rejects the original bool typedef). It configures
an out-of-tree assertion-enabled build, runs `make clean`,
`make`, and `make install`, then runs the unit tests and integration test. ICU and
readline are disabled to avoid optional dependencies; this does not change the
buffer policy. Build output is in `logs/build.log` under the run directory.

The integration test creates its own cluster with `shared_buffers = 128kB` (16
8kB buffers), loads the provided data, validates numeric results, runs scans,
checkpoint and vacuum, then runs four clients. Each client increments a disjoint
quarter of the rows and performs scans. Final sums verify that all 10,000 updates
are present. Server logs are checked automatically. The server listens only on a
temporary Unix socket and is stopped in a `finally` block. Existing clusters are
never reused. Do not run against a personal or production database.

The SQL fixture is unchanged. The runner creates a copy with `DROP TABLE IF
EXISTS` and a corrected absolute COPY path, leaving the supplied files intact.
The test cluster disables autovacuum and parallel query to make the small pool
workload repeatable; concurrent foreground clients and checkpoint still run.

To use already-built binaries:

```bash
python3 tests/lab2/run_unit.py --sanitize
python3 -m unittest discover -s tests/lab2 -p 'test_*.py' -v
python3 tests/lab2/run_integration.py \
  --pg-bin /absolute/path/to/install/bin \
  --dataset /absolute/path/to/dataset \
  --work-dir /absolute/path/to/new-integration-run
```

`--sanitize` requires compiler support for AddressSanitizer and UBSan and is
optional. Unit tests extract the actual C function bodies from the source tree;
they do not test a separately reimplemented selector. The shims enforce lock and
allocation discipline but do not emulate a complete PostgreSQL server.

## CSE Linux verification

The complete workflow has passed on `csel-remote-lnx-01` with GCC 15.2.0
in GNU C99 mode. The following commands reproduce that verification.

Log into a CSE lab host using your x500. If copying the integration kit, follow
its `START_HERE.md` to create the updated source tree first. Then run:

```bash
bash tests/lab2/run_all.sh /export/scratch/$USER/lab2-cse-check
```

The target directory must be new. If `/export/scratch/$USER` is not writable,
choose another directory where you have space. This test does not need root.
Inspect `integration/result.json`, `logs/build.log`, and `integration/server.log`.
Record the actual hostname and outcome in `docs/TEST_RESULTS.md`. A macOS pass
is useful evidence but is not a substitute for the handout's CSE Linux check.

## Scope and concurrency

All shared-buffer allocations use Second-LRU; the strategy ring and freelist
cannot bypass it. Shared pin operations update timestamps, including internal
PostgreSQL pins. Local buffers used by temporary tables retain PostgreSQL's
original policy. Dirty victims still go through PostgreSQL's existing flush and
invalidation checks.

Selection retries when access timestamps change during scanning/sorting or the
chosen buffer becomes pinned. Individual headers are locked briefly; the whole
pool is not frozen at once, so the diagnostic list is a scan snapshot, not a
transactional snapshot of every concurrent pin/unpin. The selected victim is
rechecked under its header lock and pinned before that lock is released. The
128kB integration test covers concurrent operation, not exhaustive concurrency
verification. Sorting costs O(N log N) per allocation, and verbose output is
intended for this lab's small buffer pool.

## Submission

```bash
python3 tests/lab2/package_submission.py /absolute/path/to/lab2.zip
```

The archive contains exactly:

```text
solution.txt
changes/buf_init.c
changes/bufmgr.c
changes/freelist.c
changes/buf_internals.h
```

Submit that archive, not the full PostgreSQL repository or the integration kit.
The files in `changes/` are deliberately flattened as required by the handout.
To install them onto a clean PostgreSQL 16.0 tree, restore each file to the
source path listed above and rebuild fully because the buffer descriptor changed.
