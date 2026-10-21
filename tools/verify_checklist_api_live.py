"""Real-model API generation checks against a SQLite snapshot; never writes source DB."""
import json,sqlite3,time,uuid,logging,argparse
from pathlib import Path
from contextlib import closing
from fastapi.testclient import TestClient
from backend import app,rag

logging.basicConfig(level=logging.INFO)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runs',type=int,choices=(1,2),default=2)
    runs=parser.parse_args().runs
    source=app.DB
    with closing(sqlite3.connect(source)) as db:
        rows=db.execute('select id,payload from handovers').fetchall()
        handover_id,raw=next((i,p) for i,p in rows if (s:=json.loads(p))['documents'] and all(d.get('rag',{}).get('version')==rag.VERSION for d in s['documents']))
    initial=json.loads(raw)
    run_id=uuid.uuid4().hex[:12]
    copied=source.with_name('checklist-verification-'+run_id+'.sqlite3')
    out=app.ROOT/'.artifact-build'/('verification-'+run_id);out.mkdir()
    with closing(sqlite3.connect(source)) as src,closing(sqlite3.connect(copied)) as dest:src.backup(dest)
    app.DB=copied
    original=app.generate
    started=time.monotonic()
    async def observed(documents,report=None):
        def progress(stage,detail):
            print(f'{time.monotonic()-started:.1f}s {stage}: {detail}',flush=True)
            if report:report(stage,detail)
        return await original(documents,progress)
    app.generate=observed
    summary=[]
    try:
        with TestClient(app.app) as client:
            client.post('/api/demo/session',json={'user_id':initial['handover']['owner_id']}).raise_for_status()
            prefix='/api/handovers/'+handover_id
            for number in range(1,runs+1):
                state=client.get(prefix+'/workspace').json()
                print(f'RUN {number}/{runs} START revision={state["revision"]}',flush=True)
                tick=time.monotonic()
                response=client.post(prefix+'/generate/stream',json={'revision':state['revision']})
                response.raise_for_status()
                events=[json.loads(line) for line in response.text.splitlines() if line.strip()]
                (out/f'events-{number}.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
                assert events[-1]['stage']=='done',events[-1]
                saved=client.get(prefix+'/workspace').json()
                assert saved['revision']==state['revision']+1
                assert saved['documents']==state['documents']
                assert saved['items'] and saved['source']=='ai'
                app.validate_evidence([app.Item(**i) for i in saved['items']],saved['documents'],True)
                (out/f'result-{number}.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
                summary.append({'run':number,'seconds':round(time.monotonic()-tick,1),'items':len(saved['items']),'revision':saved['revision']})
                print('PASS',summary[-1],flush=True)
        with closing(sqlite3.connect(source)) as db:unchanged=db.execute('select payload from handovers where id=?',(handover_id,)).fetchone()[0]==raw
        assert unchanged,'Source workspace changed during verification; investigate external edits'
        (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print('ALL PASS; source unchanged; evidence:',out,flush=True)
    finally:
        app.generate=original;app.DB=source
        copied.unlink(missing_ok=True)

if __name__=='__main__':main()
