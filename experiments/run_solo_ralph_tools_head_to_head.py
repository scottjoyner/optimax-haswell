#!/usr/bin/env python3
"""Minimal real tool-enabled solo Ralph A/B on a disposable bug fixture."""
from __future__ import annotations
import asyncio, json, re, subprocess, tempfile, time
from pathlib import Path
import httpx

ENDPOINTS={"lfm":("http://100.105.137.98:1234/v1","lenovo-lfm-cpu"),"ling":("http://100.105.137.98:1236/v1","lenovo-ling-specialist")}
TOOLS='''Available tools. Return exactly one JSON object, no markdown: {"tool":"list_files|read_file|replace_file|run_tests|finish","path":"...","old":"...","new":"..."}. list_files has no path. read_file requires a workspace-relative path. replace_file requires a workspace-relative path, exact old text, and new text. run_tests has no path. finish has no path. Never claim success before run_tests passes.'''

async def ask(model,messages,timeout=60):
 base,mid=ENDPOINTS[model]; started=time.monotonic()
 try:
  async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10,read=timeout,write=20,pool=20)) as c:
   r=await c.post(base+'/chat/completions',json={"model":mid,"messages":messages,"temperature":0.1,"max_tokens":512 if model=='lfm' else 768})
   r.raise_for_status(); b=r.json(); m=(b.get('choices') or [{}])[0].get('message') or {}
   return {"ok":True,"text":m.get('content') or '',"elapsed_s":time.monotonic()-started,"finish_reason":(b.get('choices') or [{}])[0].get('finish_reason')}
 except Exception as e:return {"ok":False,"text":"","error":f'{type(e).__name__}: {e}',"elapsed_s":time.monotonic()-started}

def parse(text):
 m=re.search(r'\{.*\}',text,re.S)
 if m:
  try:return json.loads(m.group())
  except json.JSONDecodeError:pass
 m=re.search(r'\[(\w+)\((.*?)\)\]',text,re.S)
 if m:
  name,args=m.groups(); out={'tool':name}
  for match in re.finditer(r'(\w+)=(?:"([^"]*)"|([^,)]*))',args):
   out[match.group(1)]=(match.group(2) or match.group(3) or '').strip()
  return out
 return None

def tool(action,root):
 name=action.get('tool')
 path_value=action.get('path')
 if isinstance(path_value,str) and path_value.startswith('/workspace/'):
  action={**action,'path':path_value[len('/workspace/'): ]}
 if name=='list_files':
  return '\n'.join(sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()))
 if name=='read_file':
  if not isinstance(action.get('path'),str): return 'ERROR: read_file requires a string path'
  p=(root/action['path']).resolve()
  if root not in p.parents and p!=root: return 'ERROR: path outside workspace'
  try:return p.read_text()
  except OSError as exc:return f'ERROR: cannot read file: {exc}'
 if name=='replace_file':
  if not isinstance(action.get('path'),str): return 'ERROR: replace_file requires a string path'
  p=(root/action['path']).resolve()
  if root not in p.parents and p!=root:return 'ERROR: path outside workspace'
  if not p.is_file():return 'ERROR: missing file'
  old=action.get('old',''); new=action.get('new','')
  try:text=p.read_text()
  except OSError as exc:return f'ERROR: cannot read file: {exc}'
  if text.count(old)!=1:return 'ERROR: old text must match exactly once'
  p.write_text(text.replace(old,new)); return 'OK: replacement applied'
 if name=='run_tests':
  p=subprocess.run(['python3','-m','pytest','-q'],cwd=root,text=True,capture_output=True,timeout=20)
  return f'EXIT {p.returncode}\n{p.stdout}\n{p.stderr}'
 if name=='finish':return 'FINISH_REQUESTED'
 return 'ERROR: unknown tool'

async def run(model):
 with tempfile.TemporaryDirectory(prefix=f'ralph-tools-{model}-') as d:
  root=Path(d); (root/'calc.py').write_text('def add(a, b):\n    return a - b\n'); (root/'test_calc.py').write_text('from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n')
  messages=[{"role":"system","content":f'You are a coding worker in a bounded solo Ralph loop. {TOOLS}'},{"role":"user","content":"Fix the bug in this workspace so the tests pass. Start by inspecting files."}]
  trace=[]; started=time.monotonic()
  for i in range(1,5):
   res=await ask(model,messages); row={"iteration":i,**res}; action=parse(res['text']) if res['ok'] else None; row['action']=action
   if not action: row['tool_result']='ERROR: malformed tool JSON'; trace.append(row); messages += [{"role":"assistant","content":res['text']},{"role":"user","content":row['tool_result']}]; continue
   out=tool(action,root); row['tool_result']=out; trace.append(row)
   if action.get('tool')=='run_tests' and out.startswith('EXIT 0'):
    return {"model":model,"complete":True,"iterations":i,"elapsed_s":time.monotonic()-started,"trace":trace}
   messages += [{"role":"assistant","content":res['text']},{"role":"user","content":f'Tool result:\n{out}\nContinue with exactly one JSON tool action.'}]
  return {"model":model,"complete":False,"iterations":4,"elapsed_s":time.monotonic()-started,"trace":trace}

async def main():
 results=[]
 for m in ('lfm','ling'): results.append(await run(m))
 out={"results":results,"elapsed_s":sum(r['elapsed_s'] for r in results)}
 p=Path('/tmp/lenovo-solo-ralph-tools-20260828.json');p.write_text(json.dumps(out,indent=2));print(json.dumps({"summary":[{k:r[k] for k in ('model','complete','iterations','elapsed_s')} for r in results]},indent=2));print(f'wrote {p}')
asyncio.run(main())
