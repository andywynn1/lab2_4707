# Validation results

Test date: November 15, 2026 (America/Chicago).
Source baseline: `part-b` commit `5a922d4442e155edd36bd5831cf83faf50ac864d`,
with the local Part C changes described in `solution.txt`.

## Completed on macOS

Environment: Darwin arm64, Apple Clang 14.0.3, Python 3.13.1,
PostgreSQL 16.0. Assertions were enabled with `--enable-cassert`.

| Check | Result |
| --- | --- |
| Configure, clean build, install | PASS |
| Final incremental rebuild/install after snapshot retry change | PASS |
| Compiler diagnostics for clean/final builds | No warnings or errors |
| Handout victim sequence | PASS: P3, P2, P5, P6 |
| Initial zero timestamps and deterministic ties | PASS |
| Single unpinned candidate | PASS |
| All buffers pinned | PASS: expected error; no header lock/allocation left held |
| Victim pinned between scan and selection | PASS: rescan |
| Victim timestamp changed between scan and selection | PASS: rescan |
| Another candidate accessed before final selection | PASS: rescan |
| First pin, repeated pin/cache hit, locked pin | PASS |
| Timestamp assignment under header lock | PASS |
| Allocation/logging/freeing outside header locks | PASS in instrumented function tests |
| 2,000 generated candidate sets vs independent rank calculation | PASS |
| AddressSanitizer and UndefinedBehaviorSanitizer for unit harness | PASS |
| Log validator positive/negative cases | PASS: 3 unittest methods, 8 invalid-log subcases |
| Official dataset load and sums | PASS |
| Repeated scans, CHECKPOINT, VACUUM ANALYZE | PASS |
| Four concurrent clients with disjoint updates and scans | PASS |
| Automatic server shutdown | PASS |

Final integration run (`integration-final/result.json`):

```json
{
  "status": "PASS",
  "shared_buffers": "128kB",
  "rows": 10000,
  "clients": 4,
  "single_session_phase": {
    "records": 1783,
    "positive_page_space_records": 1226,
    "single_candidate_records": 0,
    "backend_pids": 4
  },
  "all_phases": {
    "records": 4847,
    "positive_page_space_records": 2887,
    "single_candidate_records": 0,
    "backend_pids": 9
  }
}
```

The one-client phase used several sequential psql processes; backend_pids is a
count of distinct log-producing processes, not the number of simultaneous clients.
The overall run used four concurrent foreground clients. Candidate counts and
log totals vary with scheduling and cache contents; exact totals are not expected
to repeat on another machine.

Data verification:

| Phase | Rows | SUM(value1) | SUM(value2) |
| --- | ---: | ---: | ---: |
| After COPY | 10,000 | 30,241,833 | 18,622,888 |
| After four clients | 10,000 | 30,241,833 | 18,632,888 |

Every row was incremented once, so SUM(value2) increased by exactly 10,000.
Every complete log record was checked for ascending timestamps, a consistent
global timestamp derived from age + timestamp, the second candidate as victim
(or the sole candidate), and a page-space value between 0 and 8192.

The unit tests use actual C function bodies with deterministic shims. The live
server tests exercise the full compiled implementation. Single-candidate and
all-pinned conditions were covered by the unit harness, not observed in the
live integration run. The tests do not constitute an exhaustive concurrency
proof or a full PostgreSQL regression-suite run.

## Environment issues handled

- The GitHub repository does not contain bundled timezone data. Builds use
  `--with-system-tzdata=/usr/share/zoneinfo` and disable optional ICU/readline.
- The first sandboxed initdb attempt was blocked by the host's shared-memory
  restrictions. Successful live tests ran outside that restriction, with only a
  temporary local Unix socket and a fresh test cluster.
- PostgreSQL can append `at character N` to LOG messages while a SQL parser
  context is active. The validator accepts this native suffix.

## Completed on CSE Linux

Host: `csel-remote-lnx-01` (SSH alias `login01.cselabs.umn.edu`).
Platform: Linux x86_64. Compiler: GCC 15.2.0. Python: 3.14.4.
The run was started on November 15, 2026, America/Chicago.

The complete `tests/lab2/run_all.sh` workflow passed: configure, make clean,
make, make install, deterministic C function tests, log-validator tests,
the official 10,000-row dataset, scans, checkpoint, vacuum, and four concurrent
clients. The test cluster was stopped after completion. The run enabled
PostgreSQL assertions and used shared_buffers = 128kB.

GCC 15 defaults to C23, which rejects PostgreSQL 16.0's original bool typedef.
The first default-mode build exposed this upstream compatibility issue. The
build script now explicitly passes `-std=gnu99` and stops immediately on a failed
configure/build step. This successful run used `CFLAGS='-O2 -std=gnu99'`.
No Second-LRU source changes were required for Linux.

Compiler warning lines in the successful complete build: 10.

All 10 warnings are const-qualification diagnostics in unchanged upstream
PostgreSQL files; none comes from the four modified buffer-manager files. The
captured build log retains the exact locations. The build completed without errors.

CSE integration result:

```json
{
  "status": "PASS",
  "shared_buffers": "128kB",
  "rows": 10000,
  "clients": 4,
  "single_session_phase": {
    "records": 1782,
    "positive_page_space_records": 1225,
    "single_candidate_records": 0,
    "backend_pids": 4
  },
  "all_phases": {
    "records": 5118,
    "positive_page_space_records": 3344,
    "single_candidate_records": 0,
    "backend_pids": 9
  }
}
```

The CSE data checks verified the same initial sums as the macOS run and a
10,000 increase in SUM(value2) after the four disjoint updates. Single-candidate
and all-pinned edge cases are covered by the deterministic harness; the live
log counts do not claim that those edge cases necessarily occurred.

Run directory on CSE:
`/export/scratch/wu001664-lab2.sovfHW/run-c99`

A compressed copy of the logs is backed up in:
`/home/wu001664/lab2-cse-results-sovfHW/results-c99.tar.gz`

The integration kit includes the retrieved CSE evidence under `evidence/cse/`.
This validates the lab workload on both macOS and a CSE Linux host; it is not a
claim that the full upstream PostgreSQL regression suite was run.
