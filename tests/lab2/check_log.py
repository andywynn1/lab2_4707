#!/usr/bin/env python3
"""Validate complete Second-LRU records from a PostgreSQL stderr log."""
import argparse
import json
import re
from pathlib import Path


def check_log(path, max_buffers=16, block_size=8192):
    records = 0
    positive_space = 0
    single_candidate = 0
    candidates = None
    replaced = False
    previous_now = {}
    pid = None
    for number, line in enumerate(Path(path).read_text(errors='replace').splitlines(), 1):
        if re.search(r'\b(?:ERROR|FATAL|PANIC):', line):
            raise AssertionError(f'line {number}: server error: {line}')
        if 'Candidate buffers:' in line:
            assert candidates is None, f'line {number}: incomplete previous record'
            prefix, payload = line.split('Candidate buffers:', 1)
            match = re.search(r'\[(\d+)\]', prefix)
            pid = match.group(1) if match else 'unknown'
            assert re.fullmatch(r'\s*\d+:\d+(?:, \d+:\d+)*\s*', payload), (number, payload)
            candidates = [tuple(map(int, pair.strip().split(':'))) for pair in payload.split(',')]
            assert 1 <= len(candidates) <= max_buffers, (number, len(candidates))
            stamps = [stamp for _, stamp in candidates]
            assert stamps == sorted(stamps), f'line {number}: timestamps not sorted'
            counters = {age + stamp for age, stamp in candidates}
            assert len(counters) == 1, f'line {number}: inconsistent global timestamp'
            now = counters.pop()
            assert now >= previous_now.get(pid, 0), f'line {number}: counter moved backwards'
            previous_now[pid] = now
            replaced = False
        elif 'Replaced buffer:' in line:
            assert candidates is not None and not replaced, f'line {number}: unexpected victim'
            payload = line.split('Replaced buffer:', 1)[1].strip()
            victim = tuple(map(int, payload.split(':')))
            expected = candidates[1 if len(candidates) > 1 else 0]
            assert victim == expected, f'line {number}: victim {victim} != {expected}'
            replaced = True
        elif 'Available Page Space:' in line:
            assert candidates is not None and replaced, f'line {number}: unexpected page space'
            payload = line.split('Available Page Space:', 1)[1].strip()
            # PostgreSQL may append parser position metadata to a LOG message.
            match = re.fullmatch(r'(\d+)(?: at character \d+)?', payload)
            assert match, f'line {number}: malformed page space: {payload}'
            space = int(match.group(1))
            assert 0 <= space <= block_size, f'line {number}: invalid page space {space}'
            positive_space += space > 0
            single_candidate += len(candidates) == 1
            records += 1
            candidates = None
    assert candidates is None, 'incomplete final record'
    assert records > 0, 'no replacement records found'
    return {'records': records, 'positive_page_space_records': positive_space,
            'single_candidate_records': single_candidate, 'backend_pids': len(previous_now)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--max-buffers', type=int, default=16)
    args = parser.parse_args()
    print(json.dumps(check_log(args.log, args.max_buffers), indent=2))
