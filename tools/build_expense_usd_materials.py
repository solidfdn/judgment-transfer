#!/usr/bin/env python3
"""Create a separate fictional USD scenario; never convert historical evidence."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    spec = importlib.util.spec_from_file_location('expense_original', ROOT/'tools/build_expense_demo_materials.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.FIXTURE = ROOT/'app/fixtures/expense_review_usd'
    base.DOMAIN_ID = 'expense_review_usd'
    base.POLICY_LINES = [*base.POLICY_LINES, 'Currency: USD. All amounts in this fictional workflow are US dollars; no currency conversion is performed.']
    names = ['Alex Morgan', 'Sam Rivera', 'Jordan Chen', 'Taylor Brooks', 'Casey Lee', 'Jamie Patel']
    for record, name in zip(base.RECORDS, names):
        if record['recipient'] == record['name']:
            record['recipient'] = name
        record['name'] = name
        record['claim'] = record['claim'].replace('EXP-', 'USD-')
        for key in ('amount', 'total', 'company_paid', 'employee_paid'):
            if record[key] is not None:
                record[key] = record[key] / 100
    replacements = {'_jpy': '_usd', 'JPY': 'USD', '34,800': '348.00', '27,600': '276.00', '42,400': '424.00', '26,400': '264.00'}

    def usd(value):
        if isinstance(value, str):
            for old, new in replacements.items():
                value = value.replace(old, new)
            return value
        if isinstance(value, list):
            return [usd(v) for v in value]
        if isinstance(value, dict):
            return {usd(k): usd(v) for k, v in value.items()}
        return value

    base.display = lambda v: 'Not stated' if v is None else f'{v:,.2f}' if isinstance(v, (int, float)) else str(v)
    original_documents, original_domains = base.make_documents, base.make_domains
    base.make_documents = lambda r: tuple(usd(v) for v in original_documents(r))
    base.make_domains = lambda: tuple(usd(v) for v in original_domains())
    original_json = base.write_json
    base.write_json = lambda path, value: original_json(path, usd(value))
    result = base.build(ROOT/'output/Expense_Demo_USD_Data')
    # These are newly authored dummy dollar amounts, not an FX-rate conversion.
    readme = base.FIXTURE/'README.txt'
    readme.write_text(readme.read_text().replace('Build: python3 tools/build_expense_demo_materials.py',
        'Currency: USD. New fictional transactions, not converted historical results.\nBuild: python3 tools/build_expense_usd_materials.py'))
    return result


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
