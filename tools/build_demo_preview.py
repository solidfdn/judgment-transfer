"""Build an offline, read-only demo from the same assets served by Flask."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'app/web/demo'

def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'deliverables/Judgment_Transfer_Demo.html'
    evidence = (DEMO / 'evidence.js').read_text()
    data = json.loads(evidence.removeprefix('window.JT_DEMO_EVIDENCE=').strip().removesuffix(';'))
    review = ROOT / 'app/web/review'
    for arm, expected in data['exports'].items():
        raw = (review / ('support_triage-' + arm + '.json')).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected, 'Evidence export changed: ' + arm
        run = json.loads(raw)
        assert run['run']['mode'] == 'LIVE' and run['metrics']['complete']
        arm_index = ['A_SOURCE_ONLY', 'B_TEXT_ADDED', 'C_JT_RULES'].index(arm)
        for case in data['cases']:
            task = next(t for t in run['tasks'] if t['case_id'] == case['id'] and t['repeat'] == 1)
            receipt = next(r for r in run['receipts'] if r['receipt_id'] in task['receipt_ids'])
            saved = case['arms'][arm_index]
            assert task['decision'] == saved['decision'] and receipt == saved['receipt']
            trace = next(t for t in run['traces'] if t['trace_id'] in task['trace_ids'])
            assert case['facts'] == trace['payload']['case']['facts']
    assert hashlib.sha256(data['human'].encode()).hexdigest() == data['human_hash']
    assert data['source'] == (review / 'support_triage-sop.txt').read_text()
    css = (DEMO / 'demo.css').read_text()
    js = (DEMO / 'demo.js').read_text().replace(
        "const origin=location.protocol==='file:'?'https://judgment-transfer-unql76xapq-an.a.run.app':'';",
        "const origin='https://judgment-transfer-unql76xapq-an.a.run.app';")
    html = (DEMO / 'index.html').read_text()
    html = html.replace('<link rel="stylesheet" href="demo.css">', '<style>' + css + '</style>')
    html = html.replace('<script src="evidence.js"></script>', '<script>' + evidence.replace('</script', '<\\/script') + '</script>')
    html = html.replace('<script src="demo.js"></script>', '<script>' + js.replace('</script', '<\\/script') + '</script>')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)
    print(json.dumps({'output': str(output.resolve()), 'verified_saved_tasks': 9, 'verified_approved_source': True, 'new_model_calls': 0}))

if __name__ == '__main__':
    main()
