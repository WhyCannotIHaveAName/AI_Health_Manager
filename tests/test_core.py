import copy
import io
import json
import math
import tempfile
import unittest
import urllib.error
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from health_manager import ai
from health_manager.domain import validate_record, totals, number
from health_manager.nutrition import Catalog
from health_manager.store import Store
from health_manager.secrets import save_key, load_key

ROOT = Path(__file__).resolve().parents[1]


class NutritionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT / 'data')

    def test_usda_values_and_scaling(self):
        rice = self.catalog.item('168878', 150, low=100, high=200)
        self.assertEqual(rice['per100']['kcal'], 130)
        self.assertEqual(totals([rice])['kcal'], {'value': 195, 'low': 130, 'high': 260, 'missing': 0})
        self.assertAlmostEqual(totals([rice])['protein']['value'], rice['per100']['protein'] * 1.5)

    def test_aliases_resolve_and_food_states_visible(self):
        self.assertGreater(len(self.catalog.foods), 7000)
        for alias, fid in self.catalog.aliases.items():
            self.assertIn(fid, self.catalog.foods, alias)
        self.assertIn('cooked', self.catalog.search('米饭')[0]['name'])
        self.assertIn('raw', self.catalog.search('三文鱼（生）')[0]['name'])

    def test_unknown_id_never_trusts_ai_nutrients(self):
        rows, note = self.catalog.parse_ai({'items': [{'name': '奶茶', 'food_id': 'fake', 'grams': 400, 'per100': {'kcal': 1}}]})
        self.assertIsNone(rows[0]['per100'])
        t = totals(rows)
        self.assertEqual(t['kcal']['missing'], 1)
        self.assertEqual(t['kcal']['value'], 0)

    def test_partial_nutrients_remain_unknown(self):
        row = self.catalog.item('168878', 100)
        row['per100']['fiber'] = None
        self.assertEqual(totals([row])['fiber']['missing'], 1)

    def test_invalid_ai_bounds_and_shapes(self):
        for payload in [[], {'items': []}, {'items': ['bad']}, {'items': [{'name': '饭', 'grams': 100, 'grams_low': 200}]}, {'items': [{'name': '饭', 'grams': float('nan')}]}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.catalog.parse_ai(payload)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'health.db')
        self.row = {'day': date.today().isoformat(), 'kind': 'sleep', 'value': 7.5, 'note': 'test'}

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_save_edit_reopen_delete(self):
        rid = self.store.save(self.row)
        self.store.save(dict(self.row, value=8), rid)
        self.store.close()
        self.store = Store(Path(self.temp.name) / 'health.db')
        self.assertEqual(len(self.store.records()), 1)
        self.assertEqual(self.store.records()[0]['value'], 8)
        self.store.delete(rid)
        self.assertEqual(self.store.records(), [])

    def test_export_import_idempotent_no_secrets(self):
        self.store.save(self.row)
        data = self.store.export_data()
        self.assertNotIn('key', json.dumps(data))
        self.assertEqual(self.store.import_data(data), 0)
        data['records'][0]['id'] = 'a' * 32
        self.assertEqual(self.store.import_data(data), 1)

    def test_invalid_import_is_atomic(self):
        self.store.save(self.row)
        good = dict(self.row, id='a'*32)
        bad = dict(self.row, id='b'*32, value=-1)
        with self.assertRaises(ValueError):
            self.store.import_data({'format': 'ai-health-manager', 'version': 1, 'records': [good, bad]})
        self.assertEqual(len(self.store.records()), 1)

    def test_recent_window(self):
        self.store.save(self.row)
        self.store.save(dict(self.row, day=(date.today()-timedelta(days=14)).isoformat()))
        self.assertEqual(len(self.store.recent()), 1)

    def test_range_nan_infinity_date_and_bool(self):
        for val in [-1, 25, math.nan, math.inf, True, 'x']:
            with self.subTest(val=val), self.assertRaises(ValueError):
                validate_record(dict(self.row, value=val))
        with self.assertRaises(ValueError):
            validate_record(dict(self.row, day=(date.today()+timedelta(days=1)).isoformat()))


class SecretTests(unittest.TestCase):
    def test_dpapi_roundtrip_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'api.secret'
            key = 'sk-unit-test-not-a-real-key'
            save_key(path, key)
            self.assertNotIn(key.encode(), path.read_bytes())
            self.assertEqual(load_key(path), key)
            save_key(path, '')
            self.assertFalse(path.exists())


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.request = None

    def open(self, request, timeout):
        self.request = request
        if self.error:
            raise self.error
        return io.BytesIO(json.dumps(self.response).encode())


class AITests(unittest.TestCase):
    def test_official_endpoint_json_contract(self):
        opener = FakeOpener({'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ok":true}'}}]})
        self.assertEqual(ai.request_json('sk-unit-test', 'json', 'test', opener), {'ok': True})
        self.assertEqual(opener.request.full_url, 'https://api.deepseek.com/chat/completions')
        payload = json.loads(opener.request.data)
        self.assertEqual(payload['model'], 'deepseek-flash')
        self.assertEqual(payload['thinking']['type'], 'disabled')

    def test_http_errors_do_not_leak_response_or_key(self):
        for code in [400, 401, 402, 403, 429, 500, 302]:
            opener = FakeOpener(error=urllib.error.HTTPError(ai.ENDPOINT, code, 'secret response', {}, None))
            with self.subTest(code=code), self.assertRaises(ai.AIError) as e:
                ai.request_json('sk-unit-test', 'json', 'test', opener)
            self.assertNotIn('secret', str(e.exception))
            self.assertNotIn('sk-unit-test', str(e.exception))

    def test_empty_malformed_truncated_responses(self):
        for content, reason in [(' ', 'stop'), ('{', 'stop'), ('{}', 'length'), ('[]', 'stop')]:
            with self.subTest(content=content), self.assertRaises(ai.AIError):
                ai.request_json('sk-unit-test', 'json', 'test', FakeOpener({'choices': [{'finish_reason': reason, 'message': {'content': content}}]}))

    def test_image_resize_exif_strip_and_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'food.jpg'
            image = Image.new('RGB', (2400, 1800), 'green')
            exif = Image.Exif()
            exif[270] = 'private-test-metadata'
            image.save(path, exif=exif)
            import base64
            result = ai.image_data(path)
            converted = Image.open(io.BytesIO(base64.b64decode(result.split(',')[1])))
            self.assertLessEqual(max(converted.size), 1600)
            self.assertFalse(converted.getexif())
            cat = Catalog(ROOT / 'data')
            with patch.object(ai, 'request_json', return_value={'items': [{'name': '饭', 'food_id': '168878', 'grams': 100}]}) as request:
                rows, _ = ai.analyze_meal('sk-unit-test', '米饭', path, cat)
                self.assertEqual(request.call_args.args[2][1]['type'], 'image_url')
                self.assertEqual(rows[0]['per100']['kcal'], 130)

    def test_advice_schema(self):
        with patch.object(ai, 'request_json', return_value={'summary': '记录不足', 'suggestions': ['规律吃饭'], 'encouragement': '继续记录'}):
            self.assertEqual(ai.advice('sk-unit-test', {})['suggestions'], ['规律吃饭'])
        with patch.object(ai, 'request_json', return_value={'suggestions': 'wrong'}), self.assertRaises(ai.AIError):
            ai.advice('sk-unit-test', {})


if __name__ == '__main__':
    unittest.main()
