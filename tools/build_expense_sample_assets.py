"""Package input files for the app. Evaluation labels and reference rules stay private."""
import base64,io,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'output/Expense_Demo_USD_Data'
assets=ROOT/'app/web/samples';assets.mkdir(parents=True,exist_ok=True)
policy=(source/'policy/source_sop.txt').read_bytes()
(assets/'expense_policy.txt').write_bytes(policy)
readme='''Judgment Transfer - fictional USD expense sample

All amounts are USD. These are new fictional transactions, not currency-converted historical records.

1. Choose Try expense example in the app. It adds only the starting policy.
2. Organize the work, read the clarification questions and prepare a practice test.
3. Review and approve the proposed conditions.
4. Read each PDF under case_inputs/dev, check the facts and set starting status NEW.
5. Try the original instructions, add the owner explanation, review and approve the
   proposed guidance, then compare the same cases from NEW.
6. Keep case_inputs/holdout out of the explanation. The evaluation administrator
   can reserve them before running. Ordinary users can use them in a separate
   check with the same reviewed conditions, explicitly recorded as a separate test.

No results are pre-recorded in this pack. An accepted documentary precheck still
requires business approval; it never authorizes a payment. All data is fictional.
Only upload policy and owner explanation as work instructions. Read claim PDFs
with Read a case file. Do not upload all claim documents as shared instructions.
'''
buffer=io.BytesIO()
with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
 def add(name,data):
  info=zipfile.ZipInfo(name,date_time=(2026,10,14,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
 add('README.txt',readme.encode())
 for folder in ['policy','case_inputs','owner_review']:
  for p in sorted((source/folder).rglob('*')):
   if p.is_file():add(p.relative_to(source).as_posix(),p.read_bytes())
raw=buffer.getvalue()
(assets/'expense_files.json').write_text(json.dumps({'filename':'Judgment_Transfer_Expense_USD_Inputs.zip','mime':'application/zip','base64':base64.b64encode(raw).decode()},separators=(',',':'))+'\n')
print(json.dumps({'input_zip_bytes':len(raw),'files':zipfile.ZipFile(io.BytesIO(raw)).namelist(),'model_calls':0}))
