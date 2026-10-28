"""Real-model HR/development regression using a database snapshot only.

Run: python -m tools.verify_hr_dev_generation
The configured model receives the existing synthetic documents. Production
checklists, schedules and documents are never overwritten by this test.
"""
import json
import sqlite3
import time
import uuid
import argparse
from contextlib import closing
from fastapi.testclient import TestClient
from backend import app, rag, dependencies


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=('hr','dev','all'),default='all')
    selected=parser.parse_args().case
    source=app.DB
    run_id=uuid.uuid4().hex[:10]
    copied=source.with_name(f'regression-{run_id}.sqlite3')
    out=app.ROOT/'.artifact-build'/f'hr-dev-regression-{run_id}'
    out.mkdir(parents=True)
    with closing(sqlite3.connect(source)) as src,closing(sqlite3.connect(copied)) as dest:
        src.backup(dest)
        originals=dict(src.execute('select id,payload from handovers').fetchall())
    cases=[('hr','eedf12f8-718b-5c85-8de2-4aec32399d27'),('dev','5799e18c-8f6f-41e7-a32a-3810496aa09d')]
    cases=[case for case in cases if selected=='all' or case[0]==selected]
    app.DB=copied
    original_generate=app.generate
    started=time.monotonic()
    async def observed(documents,report=None):
        def progress(stage,detail):
            print(f'{time.monotonic()-started:.1f}s {stage}: {detail}',flush=True)
            if report:report(stage,detail)
        return await original_generate(documents,progress)
    app.generate=observed
    results=[]
    try:
        with TestClient(app.app) as client:
            for label,handover_id in cases:
                initial=json.loads(originals[handover_id])
                assert len(initial['documents'])==7
                assert all(d.get('rag',{}).get('version')==rag.VERSION for d in initial['documents'])
                initial['status']='review'
                initial['approved_at']=None
                with closing(sqlite3.connect(copied)) as db:
                    db.execute('update handovers set payload=? where id=?',(json.dumps(initial,ensure_ascii=False),handover_id));db.commit()
                client.post('/api/demo/session',json={'user_id':initial['handover']['owner_id']}).raise_for_status()
                prefix='/api/handovers/'+handover_id
                tick=time.monotonic()
                print(f'CASE {label} START output={out}',flush=True)
                response=client.post(prefix+'/generate/stream',json={'revision':initial['revision']})
                response.raise_for_status()
                events=[json.loads(line) for line in response.text.splitlines() if line.strip()]
                (out/f'{label}-events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
                if events[-1]['stage']!='done':
                    results.append({'case':label,'success':False,'error':events[-1],'seconds':round(time.monotonic()-tick,1)})
                    print('CASE FAILED',json.dumps(results[-1],ensure_ascii=False),flush=True)
                    continue
                saved=client.get(prefix+'/workspace').json()
                assert saved['revision']==initial['revision']+1
                assert saved['generated_at']!=initial['generated_at']
                assert saved['status']=='review' and saved['items']
                assert saved['documents']==initial['documents']
                typed=[app.Item(**item) for item in saved['items']]
                app.validate_evidence(typed,saved['documents'],True)
                app.validate_readability(typed);app.validate_output_language(typed)
                dependencies.validate(saved['items'])
                by_id={i['id']:i for i in saved['items']}
                relations=[{'before':by_id[d]['title'],'after':i['title'],**i['dependency_notes'][d]} for i in saved['items'] for d in i['dependencies']]
                (out/f'{label}-result.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
                results.append({'case':label,'success':True,'seconds':round(time.monotonic()-tick,1),'items':len(typed),'relations':relations})
                print('CASE PASS',json.dumps(results[-1],ensure_ascii=False),flush=True)
        with closing(sqlite3.connect(source)) as db:
            unchanged=dict(db.execute('select id,payload from handovers').fetchall())==originals
        report={'cases':results,'source_unchanged':unchanged,'output':str(out)}
        (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('FINAL',json.dumps(report,ensure_ascii=False),flush=True)
        assert unchanged,'Live data changed during verification; check concurrent user actions.'
        assert all(r['success'] for r in results),'A generation case failed; see saved events.'
    finally:
        app.generate=original_generate
        app.DB=source
        # Snapshot is retained for failure diagnosis; it is under ignored data/.


if __name__=='__main__':main()
