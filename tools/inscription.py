"""rev. 0.12: the inscription of the case, transcribed by the page's own transcriber (tools/web/transcribe.js, run in
node) into the signs of the layout; written to data/inscription.json, read by tools/model/case.py.
Usage: python3 -I tools/inscription.py data/inscription.json"""
import sys, os, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = 'si na níretequa: tecuvalye, málonya, aima i níralye!'
TRANS = 'Это силовая кисть: пиши, друг мой, что угодно, что пожелаешь!'
JS = ("const fs=require('fs');eval(fs.readFileSync(process.argv[1],'utf8')+';global.TPM2_TR=TPM2_TR;');"
      "console.log(JSON.stringify(TPM2_TR.transcribe(process.argv[2],'quenya')));")
r = json.loads(subprocess.run(['node', '-e', JS, os.path.join(HERE, 'web', 'transcribe.js'), TEXT], check=True,
                              capture_output=True, text=True).stdout)
assert not r['warnings'], r['warnings']
json.dump(dict(text=TEXT, translation=TRANS, mode='quenya', items=[x['k'] for x in r['items']]), open(sys.argv[1], 'w'),
          ensure_ascii=False, indent=1)
print(len(r['items']), 'signs')
