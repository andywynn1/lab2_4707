"""Exercise the validator with good logs and deliberately wrong output."""
import tempfile
import unittest
from pathlib import Path
from check_log import check_log

GOOD = '''[12] LOG:  Candidate buffers: 47:560, 8:599, 2:605
\tReplaced buffer: 8:599
\tAvailable Page Space: 8100 at character 14
'''


class LogChecks(unittest.TestCase):
    def validate(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'server.log'
            path.write_text(text)
            return check_log(path)

    def test_good(self):
        self.assertEqual(self.validate(GOOD)['records'], 1)

    def test_only_candidate(self):
        log = GOOD.replace('47:560, 8:599, 2:605', '8:599')
        self.assertEqual(self.validate(log)['single_candidate_records'], 1)

    def test_bad_logs(self):
        for bad in [
            '',
            GOOD.replace('Replaced buffer: 8:599', 'Replaced buffer: 47:560'),
            GOOD.replace('47:560, 8:599, 2:605', '8:599, 47:560, 2:605'),
            GOOD.replace('47:560', '46:560'),
            GOOD.replace('8100', '9000'),
            GOOD.replace('8100 at character 14', 'garbage'),
            GOOD.split('Available Page Space:')[0],
            GOOD + '[12] PANIC: test failure\n',
        ]:
            with self.subTest(log=bad):
                with self.assertRaises(AssertionError):
                    self.validate(bad)


if __name__ == '__main__':
    unittest.main()
