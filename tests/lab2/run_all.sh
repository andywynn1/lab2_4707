#!/usr/bin/env bash
# Build and test only in a new directory supplied by the caller.
set -euo pipefail
SOURCE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 NEW_RUN_DIRECTORY [DATASET_DIRECTORY]" >&2
    exit 2
fi
if [[ -e "$1" ]]; then
    echo "Refusing to overwrite an existing run directory: $1" >&2
    exit 2
fi
mkdir -p "$1"
RUN_ROOT=$(cd "$1" && pwd)
DATASET_ROOT=${2:-"$SOURCE_ROOT/tests/lab2/dataset"}
mkdir "$RUN_ROOT/build" "$RUN_ROOT/install" "$RUN_ROOT/logs"
(
    cd "$RUN_ROOT/build"
    # The repository omits bundled tzdata; use the host's installed database.
    # PostgreSQL 16.0 predates GCC 15's default C23 mode.
    CFLAGS="${CFLAGS:--O2} -std=gnu99" "$SOURCE_ROOT/configure" --prefix="$RUN_ROOT/install" \
        --without-icu --without-readline --enable-cassert \
        --with-system-tzdata=/usr/share/zoneinfo || exit $?
    make clean || exit $?
    make -j "${JOBS:-4}" || exit $?
    make install
) > "$RUN_ROOT/logs/build.log" 2>&1 || {
    tail -60 "$RUN_ROOT/logs/build.log" >&2
    exit 1
}
python3 "$SOURCE_ROOT/tests/lab2/run_unit.py" | tee "$RUN_ROOT/logs/unit.log"
python3 -m unittest discover -s "$SOURCE_ROOT/tests/lab2" -p 'test_*.py' -v \
    2>&1 | tee "$RUN_ROOT/logs/log-validator.log"
python3 "$SOURCE_ROOT/tests/lab2/run_integration.py" \
    --pg-bin "$RUN_ROOT/install/bin" --dataset "$DATASET_ROOT" \
    --work-dir "$RUN_ROOT/integration" | tee "$RUN_ROOT/logs/integration.log"
echo "PASS: results and logs are in $RUN_ROOT"
