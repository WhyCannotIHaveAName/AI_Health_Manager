"""Exercise the actual Tk screens and local CRUD using disposable synthetic data."""
import tempfile
from datetime import date
from unittest.mock import patch
from health_manager.app import App


def run():
    with tempfile.TemporaryDirectory() as folder:
        app = App(data_dir=folder)
        errors = []
        app.report_callback_exception = lambda *args: errors.append(args)
        try:
            for page in ['overview', 'log', 'meal', 'insight', 'history', 'settings']:
                app.show(page)
                app.update()
                assert app.body.winfo_exists(), page
            rid = app.store.save({'day': date.today().isoformat(), 'kind': 'sleep', 'value': 7.5})
            app.store.save({'day': date.today().isoformat(), 'kind': 'weight', 'value': 65})
            app.show('history')
            app.edit_record(app.store.records()[0])
            app.update()
            app.show('meal')
            app.meal_input.insert('1.0', '合成测试：米饭150克')
            app.draft = [app.catalog.item('168878', 150)]
            app.save_meal()
            assert app.page == 'history'
            meal = next(r for r in app.store.records() if r['kind'] == 'meal')
            app.edit_record(meal)
            assert app.draft[0]['grams'] == 150
            assert '合成测试' in app.meal_input.get('1.0', 'end')
            with patch('health_manager.app.messagebox.askyesno', return_value=True):
                app.new_meal()
            assert not app.draft
            assert app.meal_input.get('1.0', 'end').strip() == ''
            assert app.meal_text == ''
            app.item_dialog()
            app.update()
            for win in app.winfo_children():
                if win.winfo_class() == 'Toplevel':
                    win.destroy()
            app.show('overview')
            app.update()
            assert not errors, errors
            print('GUI smoke passed: 6 screens, synthetic CRUD, meal edit/reset, food dialog, trend chart')
        finally:
            app.close()


if __name__ == '__main__':
    run()
