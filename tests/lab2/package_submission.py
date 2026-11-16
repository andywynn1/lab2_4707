#!/usr/bin/env python3
"""Create and verify the exact lab2.zip layout required by the handout."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    'src/backend/storage/buffer/buf_init.c',
    'src/backend/storage/buffer/bufmgr.c',
    'src/backend/storage/buffer/freelist.c',
    'src/include/storage/buf_internals.h',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    solution = ROOT / 'solution.txt'
    text = solution.read_text()
    assert '<Student' not in text and '<Modified File' not in text
    for name in ('wu001664', 'nguy5745', 'erenn001'):
        assert name in text
    expected = ['solution.txt'] + ['changes/' + Path(path).name for path in FILES]
    assert len(set(expected)) == 5
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, 'w', ZIP_DEFLATED) as archive:
        archive.write(solution, 'solution.txt')
        for source in FILES:
            archive.write(ROOT / source, 'changes/' + Path(source).name)
    with ZipFile(args.output) as archive:
        assert sorted(archive.namelist()) == sorted(expected)
        assert archive.testzip() is None
        assert archive.read('solution.txt') == solution.read_bytes()
        for source in FILES:
            assert archive.read('changes/' + Path(source).name) == (ROOT / source).read_bytes()
    print(f'PASS: {args.output} contains solution.txt and exactly four changed source files')


if __name__ == '__main__':
    main()
