import subprocess, pathlib, json, os, concurrent.futures, time
root=pathlib.Path('/workspace/scratch/7fd119be064d');repo=root/'sv-review-2c825b8';out=root/'sv-review-2c825b8-results';py=str(root/'sv-test-env/bin/python')
env=dict(os.environ,PYTHONPATH=str(repo),PYTHONDONTWRITEBYTECODE='1')
def run(name,args):
 t=time.monotonic();r=subprocess.run(args,cwd=repo,env=env,capture_output=True,text=True,timeout=300)
 (out/(name+'.log')).write_text(r.stdout+'\nSTDERR\n'+r.stderr)
 v={'name':name,'command':args,'exit':r.returncode,'seconds':round(time.monotonic()-t,2)}
 print(json.dumps(v),flush=True);return v
jobs=[('pytest',[py,'-m','pytest','-q','-ra']),('attacks',[py,'tools/attack_harness.py','--round2','--round3']),('kernel',[py,'tools/gate_contract.py','--check','kernel']),('verifier',[py,'tools/gate_contract.py','--check','verifier']),('signature-mutant',[py,'-u','tools/verifier_mutants.py','--only','signature'])]
for p in sorted((repo/'evidence').glob('sv_package_*.json')):
 rel=str(p.relative_to(repo));jobs.append((p.stem,[py,'tools/verify_package.py',rel,'--signature',rel+'.sig','--allowed-signers','keys/allowed_signers','--identity','holland202','--witness-log','witness/packages.log']))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex: results=list(ex.map(lambda a:run(*a),jobs))
(out/'commands.json').write_text(json.dumps(results,indent=2))
