import copy
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from health_manager import ai
from health_manager.domain import totals, validate_item
from health_manager.meal_analysis import analyze, enrich, fill_saved
from health_manager.nutrition import Catalog
from health_manager.products import Products, product_data, valid_barcode
from health_manager.store import Store

ROOT = Path(__file__).resolve().parents[1]
ESTIMATE = {"kcal": 180, "protein": 8, "fat": 6, "carbs": 24, "fiber": 2, "sodium": 300}
PRODUCT = {"code": "3017620422003", "product_name": "Nutella", "brands": "Ferrero", "quantity": "400g", "product_quantity_unit": "g",
           "nutriments": {"energy-kcal_100g": 539, "proteins_100g": 6.3, "fat_100g": 30.9, "carbohydrates_100g": 57.5, "sodium_100g": .0428}}


class FakeProducts:
    def __init__(self, product=None, error=None):
        self.product, self.error = product, error

    def barcode(self, code):
        if self.error:
            raise self.error
        return self.product

    def brand(self, brand):
        if self.error:
            raise self.error
        return [self.product] if self.product else []


class ProductTests(unittest.TestCase):
    def test_gtin_validation(self):
        self.assertTrue(valid_barcode('3017620422003'))
        for bad in ['3017620422004', '１２３４５６７８', '123', None, '3017620422003/../secret']:
            self.assertFalse(valid_barcode(bad))

    def test_public_label_conversion_and_missing_fields(self):
        row = product_data(PRODUCT)
        self.assertEqual(row['per100']['kcal'], 539)
        self.assertAlmostEqual(row['per100']['sodium'], 42.8)
        self.assertIsNone(row['per100']['fiber'])
        self.assertEqual(row['source_url'], 'https://world.openfoodfacts.org/product/3017620422003')
        kj = copy.deepcopy(PRODUCT)
        del kj['nutriments']['energy-kcal_100g']
        kj['nutriments']['energy-kj_100g'] = 836.8
        del kj['nutriments']['sodium_100g']
        kj['nutriments']['salt_100g'] = 1
        row = product_data(kj)
        self.assertAlmostEqual(row['per100']['kcal'], 200)
        self.assertAlmostEqual(row['per100']['sodium'], 400)

    def test_invalid_label_ignored(self):
        for field, value in [('fat_100g', 400), ('energy-kcal_100g', float('nan'))]:
            row = copy.deepcopy(PRODUCT)
            row['nutriments'][field] = value
            self.assertIsNone(product_data(row))

    def test_request_user_agent_no_key_and_memory_cache(self):
        class Opener:
            count = 0
            def open(self, request, timeout):
                self.count += 1
                self.request = request
                return io.BytesIO(json.dumps({'product': PRODUCT}).encode())
        opener = Opener()
        products = Products(opener)
        self.assertEqual(products.barcode(PRODUCT['code'])['code'], PRODUCT['code'])
        products.barcode(PRODUCT['code'])
        self.assertEqual(opener.count, 1)
        self.assertIsNone(opener.request.get_header('Authorization'))
        self.assertIn('AIHealthManager', opener.request.get_header('User-agent'))


class MealSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT/'data')

    def row(self, **kw):
        return {'name': '番茄肉酱意面', 'grams': 300, 'grams_low': 250, 'grams_high': 350,
                'unit': 'g', 'search_terms': ['spaghetti meat sauce'], 'per100_estimate': ESTIMATE.copy(),
                'estimate_reason': '按常见配方估算，油量不确定', **kw}

    def test_full_catalog_retrieval_beyond_curated_aliases(self):
        rows = self.catalog.candidates(['spaghetti meat sauce'])
        self.assertTrue(rows)
        self.assertTrue(any('spaghetti' in row['name'].lower() for row in rows))
        self.assertTrue(any(row['id'] not in self.catalog.aliases.values() for row in rows))

    def test_screenshot_meal_gets_estimates_instead_of_all_unknown(self):
        names = ['番茄肉酱意面', '鸡肉小披萨', '烤牛奶', '芒果酸奶']
        initial = {'items': [self.row(name=n, search_terms=[]) for n in names]}
        fallback = {'items': [{'index': i, 'kind': 'estimate', 'per100_estimate': ESTIMATE.copy()} for i in range(4)]}
        with patch.object(ai, 'request_json', side_effect=[initial, fallback]):
            items, _ = analyze('synthetic-key', '合成测试餐食', None, self.catalog, FakeProducts())
        self.assertEqual([i['name'] for i in items], names)
        self.assertTrue(all(i['source_kind'] == 'estimate' and i['per100']['kcal'] for i in items))
        summary = totals(items)['kcal']
        self.assertEqual(summary['value'], 2160)
        self.assertLess(summary['low'], summary['value'])
        self.assertGreater(summary['high'], summary['value'])

    def test_exact_usda_overrides_model_estimate(self):
        rows = [self.row(name='熟米饭', food_id='168878', match='exact')]
        items, _ = enrich('synthetic-key', rows, self.catalog, FakeProducts())
        self.assertEqual(items[0]['per100']['kcal'], 130)
        self.assertEqual(items[0]['source_kind'], 'database')
        self.assertNotIn('kcal', items[0]['estimated_nutrients'])

    def test_actual_product_label_wins_and_estimates_missing_fiber(self):
        product = product_data(PRODUCT)
        items, _ = enrich('synthetic-key', [self.row(barcode=PRODUCT['code'])], self.catalog, FakeProducts(product))
        item = items[0]
        self.assertEqual(item['per100']['kcal'], 539)
        self.assertEqual(item['source_kind'], 'product_label')
        self.assertEqual(item['estimated_nutrients'], ['fiber'])

    def test_offline_product_query_falls_back(self):
        with patch.object(ai, 'request_json', return_value={'items': []}):
            items, note = enrich('synthetic-key', [self.row(barcode=PRODUCT['code'])], self.catalog, FakeProducts(error=OSError()))
        self.assertEqual(items[0]['source_kind'], 'estimate')
        self.assertEqual(items[0]['per100']['kcal'], 180)
        self.assertIn('公开商品库', note)

    def test_hallucinated_reference_cannot_claim_database(self):
        decision = {'items': [{'index': 0, 'kind': 'usda', 'id': 'fake', 'match': 'exact', 'per100_estimate': ESTIMATE}]}
        with patch.object(ai, 'request_json', return_value=decision):
            items, _ = enrich('synthetic-key', [self.row()], self.catalog, FakeProducts())
        self.assertEqual(items[0]['source_kind'], 'estimate')
        self.assertEqual(items[0]['source_url'], '')

    def test_unit_mismatch_does_not_silently_use_ml_as_g(self):
        product = product_data(PRODUCT)
        product['unit'] = 'ml'
        with patch.object(ai, 'request_json', return_value={'items': []}):
            items, _ = enrich('synthetic-key', [self.row(barcode=PRODUCT['code'])], self.catalog, FakeProducts(product))
        self.assertEqual(items[0]['per100']['kcal'], 180)
        self.assertEqual(items[0]['unit'], 'g')
        self.assertEqual(items[0]['source_kind'], 'estimate')

    def test_wrong_brand_cannot_be_presented_as_exact_product(self):
        decision = {'items': [{'index': 0, 'kind': 'product', 'id': PRODUCT['code'], 'match': 'exact'}]}
        with patch.object(ai, 'request_json', return_value=decision):
            items, _ = enrich('synthetic-key', [self.row(brand='OtherBrand')], self.catalog, FakeProducts(product_data(PRODUCT)))
        self.assertEqual(items[0]['source_kind'], 'estimate')
        self.assertEqual(items[0]['source_url'], '')

    def test_partial_existing_label_values_are_not_overwritten(self):
        original = validate_item({'name': '标签酸奶', 'grams': 200, 'per100': {'kcal': 80}, 'source': '用户标签', 'source_kind': 'user_label'})
        response = {'items': [{'index': 0, **self.row(search_terms=[])}]}
        with patch.object(ai, 'request_json', side_effect=[response, {'items': []}]):
            items, _ = fill_saved('synthetic-key', [original], self.catalog, FakeProducts())
        self.assertEqual(items[0]['per100']['kcal'], 80)
        self.assertEqual(items[0]['per100']['protein'], 8)
        self.assertNotIn('kcal', items[0]['estimated_nutrients'])
        self.assertIn('protein', items[0]['estimated_nutrients'])

    def test_existing_unknown_record_can_be_filled_without_quantity_changes(self):
        old = validate_item({'name': '烤牛奶', 'grams': 120, 'grams_low': 110, 'grams_high': 130, 'per100': None})
        known = self.catalog.item('168878', 200)
        response = {'items': [{'index': 0, **self.row(name='模型改名', grams=999)}]}
        with patch.object(ai, 'request_json', side_effect=[response, {'items': []}]):
            items, _ = fill_saved('synthetic-key', [old, known], self.catalog, FakeProducts())
        self.assertEqual(items[0]['name'], '烤牛奶')
        self.assertEqual(items[0]['grams'], 120)
        self.assertEqual(items[0]['grams_low'], 110)
        self.assertEqual(items[1], known)
        self.assertEqual(items[0]['source_kind'], 'estimate')

    def test_source_metadata_and_ranges_survive_backup(self):
        with patch.object(ai, 'request_json', return_value={'items': []}):
            items, _ = enrich('synthetic-key', [self.row(unit='ml', search_terms=[])], self.catalog, FakeProducts())
        with tempfile.TemporaryDirectory() as folder:
            db = Store(Path(folder)/'health.db')
            try:
                db.save({'day': date.today().isoformat(), 'kind': 'meal', 'items': items})
                restored = db.export_data()['records'][0]['items'][0]
                self.assertEqual(restored['unit'], 'ml')
                self.assertEqual(restored['per100_low'], items[0]['per100_low'])
                self.assertEqual(restored['source_kind'], 'estimate')
            finally:
                db.close()


if __name__ == '__main__':
    unittest.main()
