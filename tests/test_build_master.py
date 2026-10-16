import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_master import build, handle, normalize, number


class MasterTests(unittest.TestCase):
    def test_identity_normalization(self):
        for value in ['@Some_Dev', 'https://twitter.com/Some_Dev?x=1', 'x.com/Some_Dev/status/123']:
            self.assertEqual(handle(value), 'some_dev')
        self.assertIsNone(handle('https://example.com/dev'))
        self.assertIsNone(handle('https://x.com/intent/follow'))
        self.assertNotEqual(normalize({'name': 'dev'})[1], ['dev'])

    def test_numbers(self):
        self.assertEqual(number('+$77,624.21'), 77624.21)
        self.assertEqual(number('$13.7K'), 13700)
        self.assertEqual(number('1.12%'), 1.12)
        self.assertIsNone(number('—'))
        self.assertEqual(normalize({'profile_name': 'user123', 'followers': 'user123201K followers'})[0]['followers'], 201000)

    def test_transitive_merge_conflicts_and_missing_identities(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            rows = [
                {'handle': '@Dev', 'profileUrl': 'https://example.com/a', 'accountBasedIn': 'US', 'checkedAt': '2026-01-01'},
                {'handle': 'DEV', 'accountBasedIn': 'UK', 'checkedAt': '2026-02-01'},
                {'profileUrl': 'https://example.com/a?tracking=1', 'name': 'Developer'},
                {'name': 'Developer'}, {'name': 'Developer'}]
            (path / 'scout.json').write_text(json.dumps({'records': rows}))
            result = build(path)
            self.assertEqual(len(result['profiles']), 3)
            merged = next(p for p in result['profiles'] if p['x_handle'])
            self.assertEqual(len(merged['observations']), 3)
            self.assertEqual(merged['fields']['account_based_in'], 'UK')
            self.assertEqual(merged['conflicts']['account_based_in'], ['US', 'UK'])
            self.assertEqual(result, build(path))

    def test_duplicate_holdings_and_ambiguous_handles(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            wallet = 'A' * 32
            row = {'wallet': wallet, 'x': 'https://x.com/old', 'value': '$1K', 'name': 'Dev'}
            snapshot = {'mint': 'token', 'time': '2026-01-01', 'rows': [row, row]}
            (path / 'holders.json').write_text(json.dumps({'snapshots': [snapshot]}))
            (path / 'scout.json').write_text(json.dumps({'records': [{'wallet': wallet, 'handle': 'new'}]}))
            result = build(path)
            self.assertEqual(len(result['profiles']), 1)
            self.assertIsNone(result['profiles'][0]['x_handle'])
            self.assertEqual(result['profiles'][0]['conflicts']['x_handle'], ['new', 'old'])
            self.assertEqual(len(result['holdings']), 1)
            self.assertEqual(len(result['holdings'][0]['origins']), 2)
            self.assertEqual(result['holdings'][0]['metrics']['value'], 1000)

    def test_unknown_schema_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'unknown.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'unsupported JSON'):
                build(path)

    def test_latest_value_can_return_to_previous_value(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            rows = [{'handle': 'dev', 'accountBasedIn': country, 'checkedAt': date}
                    for country, date in [('US', '2026-01-01'), ('UK', '2026-02-01'), ('US', '2026-03-01')]]
            (path / 'scout.json').write_text(json.dumps({'records': rows}))
            self.assertEqual(build(path)['profiles'][0]['fields']['account_based_in'], 'US')


if __name__ == '__main__':
    unittest.main()
