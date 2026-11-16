#!/usr/bin/env python3
"""Run the supplied dataset and four clients in a new, isolated test cluster."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from check_log import check_log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    bindir, dataset, work = [p.resolve() for p in (args.pg_bin, args.dataset, args.work_dir)]
    work.mkdir(parents=True, exist_ok=True)
    data = work / 'cluster'
    if data.exists():
        raise SystemExit('Refusing to reuse an existing cluster; choose a new --work-dir.')
    assert (dataset / 'buffer_add.sql').is_file()
    assert (dataset / 'values10k.dat').is_file()
    # Ignore ambient connection settings so this can never hit an existing server.
    env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
    started = False
    with tempfile.TemporaryDirectory(prefix='lab2-socket-') as sock:
        env.update(PGHOST=sock, PGPORT='55472', PGDATABASE='postgres', PGCONNECT_TIMEOUT='10')

        def run(argv, name, input_text=None, timeout=120):
            with (work / name).open('w') as output:
                result = subprocess.run([str(a) for a in argv], input=input_text,
                                        text=True, stdout=output, stderr=subprocess.STDOUT,
                                        env=env, timeout=timeout)
            if result.returncode:
                raise RuntimeError(f'{name} failed ({result.returncode}); see {work / name}')
            return (work / name).read_text()

        def sql(text, name):
            return run([bindir / 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-At'], name, text)

        try:
            run([bindir / 'initdb', '-D', data, '--no-locale', '--encoding=UTF8',
                 '-A', 'trust', '-c', 'shared_buffers=128kB',
                 '-c', 'max_connections=12', '-c', 'max_wal_senders=0',
                 '-c', 'autovacuum=off', '-c', 'log_min_messages=warning'], 'initdb.log')
            with (data / 'postgresql.conf').open('a') as config:
                config.write("\nlisten_addresses = ''\n")
                config.write(f"unix_socket_directories = '{sock.replace(chr(39), chr(39)*2)}'\n")
                config.write("port = 55472\nlog_min_messages = log\nlog_line_prefix = '[%p] '\n")
                config.write("log_statement = 'none'\nmax_parallel_workers_per_gather = 0\n")
            run([bindir / 'pg_ctl', '-D', data, '-l', work / 'server.log', '-w', 'start'], 'start.log')
            started = True
            size = sql('SHOW shared_buffers; SHOW block_size;', 'settings.log').splitlines()
            assert size == ['128kB', '8192'], size
            script = (dataset / 'buffer_add.sql').read_text()
            # Only adapt the initial DROP and the handout's machine-specific COPY path.
            script = re.sub(r'drop table test_table;', 'DROP TABLE IF EXISTS test_table;', script, flags=re.I)
            source_path = str(dataset / 'values10k.dat').replace("'", "''")
            script, substitutions = re.subn(r"(?i)(\bfrom\s+)'[^']*'", lambda m: m[1] + "'" + source_path + "'", script)
            assert substitutions == 1
            (work / 'buffer_add.sql').write_text(script)
            sql(script, 'dataset.log')
            initial = sql('SELECT count(*), sum(value1), sum(value2) FROM test_table;', 'initial.log').strip()
            rows, sum1, sum2 = map(int, initial.split('|'))
            input_rows = [line.split(';') for line in (dataset / 'values10k.dat').read_text().splitlines() if line.strip()]
            assert rows == len(input_rows) == 10000
            assert sum1 == sum(int(row[0]) for row in input_rows)
            assert sum2 == sum(int(row[1]) for row in input_rows)
            # Repeated scans exercise hits as well as replacement, then dirty-page flushing.
            sql('SELECT sum(value1) FROM test_table;\n' * 4 + 'CHECKPOINT;\nVACUUM ANALYZE test_table;', 'scan.log')
            scan_stats = check_log(work / 'server.log')

            def client(index):
                statement = "SET statement_timeout = '60s';\n"
                statement += f'UPDATE test_table SET value2 = value2 + 1 WHERE id % 4 = {index};\n'
                statement += 'SELECT count(*), sum(value1) FROM test_table;\n' * 4
                return sql(statement, f'client-{index}.log')

            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(client, range(4)))
            final = sql('SELECT count(*), sum(value1), sum(value2) FROM test_table; CHECKPOINT;', 'final.log').splitlines()[0]
            assert tuple(map(int, final.split('|'))) == (rows, sum1, sum2 + rows), final
            run([bindir / 'pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop'], 'stop.log')
            started = False
            stats = check_log(work / 'server.log')
            assert stats['positive_page_space_records'] > 0
            assert stats['backend_pids'] >= 4
            result = {'status': 'PASS', 'shared_buffers': '128kB', 'rows': rows,
                      'clients': 4, 'single_session_phase': scan_stats, 'all_phases': stats}
            (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
        finally:
            if started:
                run([bindir / 'pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop'], 'stop.log')


if __name__ == '__main__':
    main()
