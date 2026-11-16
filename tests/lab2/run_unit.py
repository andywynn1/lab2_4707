#!/usr/bin/env python3
"""Compile actual selector, logger and pin functions against deterministic shims."""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def function(source, name):
    # PostgreSQL function definitions end with a brace in column one.
    match = re.search(r'^(?:static )?[\w *]+\n' + name + r'\(', source, re.M)
    if not match:
        raise ValueError(f'Missing production function: {name}')
    end = source.index('\n}', match.end()) + 2
    return source[match.start():end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    header = (ROOT / 'src/include/storage/buf_internals.h').read_text()
    freelist = (ROOT / 'src/backend/storage/buffer/freelist.c').read_text()
    bufmgr = (ROOT / 'src/backend/storage/buffer/bufmgr.c').read_text()
    chunks = []
    for name in ('CandidateBuf', 'BufferSelectionSnapshot'):
        chunks.append(re.search(r'typedef struct ' + name + r'\b.*?\} ' + name + ';', header, re.S)[0])
    chunks += [function(freelist, name) for name in ('candidate_cmp', 'StrategyGetBuffer', 'StrategyLogSelection')]
    chunks += [function(bufmgr, name) for name in ('PinBuffer', 'PinBuffer_Locked')]
    harness = (Path(__file__).with_name('unit_harness.c')).read_text()
    with tempfile.TemporaryDirectory(prefix='lab2-unit-') as temp:
        source, binary = Path(temp) / 'unit.c', Path(temp) / 'unit'
        source.write_text(harness.replace('/* PRODUCTION_CODE */', '\n\n'.join(chunks)))
        command = shlex.split(os.environ.get('CC', 'cc'))
        command += ['-std=gnu99', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    '-Wno-unused-function', '-Wno-unused-variable', '-O1', '-g']
        if args.sanitize:
            command += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        subprocess.run(command + [str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=30)


if __name__ == '__main__':
    main()
