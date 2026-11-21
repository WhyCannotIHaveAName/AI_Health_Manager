"""Synthetic text benchmark. --live explicitly opts in to billed API requests."""
import argparse
import getpass
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from health_manager.ai import analyze_meal
from health_manager.nutrition import Catalog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Call DeepSeek with synthetic test cases (billed)')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cat = Catalog(root / 'data')
    cases = json.loads((root / 'tests/meal_cases.json').read_text(encoding='utf-8'))
    for case in cases:
        for expected in case['expected']:
            assert expected['food_id'] in cat.foods
    if not args.live:
        print(f'{len(cases)} synthetic cases validated. Use --live to measure model performance.')
        return
    key = getpass.getpass('DeepSeek test API key (hidden): ').strip()
    for case in cases:
        items, _ = analyze_meal(key, case['text'], None, cat)
        expected = {i['food_id']: i['grams'] for i in case['expected']}
        actual = {}
        for item in items:
            fid = item['food_id']
            actual[fid] = actual.get(fid, 0) + item['grams']
        matched = expected.keys() & actual.keys()
        print(json.dumps({'case': case['name'], 'id_recall': len(matched) / len(expected),
                          'id_precision': len(matched) / len(actual) if actual else 0,
                          'weight_mape_on_matched': sum(abs(actual[f]-expected[f])/expected[f] for f in matched)/len(matched) if matched else None}, ensure_ascii=False))


if __name__ == '__main__':
    main()
