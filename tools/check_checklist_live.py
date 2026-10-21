"""Read-only live checklist verification. Does not replace workspace data."""
import asyncio,json,sqlite3,time,sys
from backend import app,rag

async def main():
    with sqlite3.connect(app.DB) as db:
        states=[json.loads(r[0]) for r in db.execute('select payload from handovers')]
    state=next(s for s in states if s['documents'] and all(d.get('rag',{}).get('version')==rag.VERSION for d in s['documents']))
    started=time.monotonic()
    def report(stage,detail):print(f'{time.monotonic()-started:.1f}s {stage}: {detail}',flush=True)
    original=app.generate_section
    from backend import checklist_generation
    original_repair=checklist_generation.repair
    async def tracked_repair(*args):
        items=await original_repair(*args)
        (app.ROOT/'.artifact-build/repaired-checklist.json').write_text(json.dumps([i.model_dump() for i in items],ensure_ascii=False),encoding='utf-8')
        return items
    checklist_generation.repair=tracked_repair
    request=rag.request
    cached=[]
    if '--resume' in sys.argv:
        chunks=await rag.retrieve(state['documents'],app.DB.parent,lambda *args:None)
        for path in (app.ROOT/'.artifact-build').glob('section-*.json'):
            value=json.loads(path.read_text(encoding='utf-8'))
            items=[app.Item(**i) for i in value['items']]
            try:
                app.validate_evidence(items,state['documents'],True);app.validate_retrieved(items,chunks);app.validate_output_language(items)
            except ValueError:continue
            cached.append(value)
        if cached:
            outline=cached[-1]['outline'];cached=[c for c in cached if c['outline']==outline]
            resumed=False
            async def resumed_request(model,route,payload):
                nonlocal resumed
                if not resumed and 'tasks' in payload.get('messages',[{}])[0].get('content',''):
                    resumed=True
                    print('RESUME validated outline and',len(cached),'source-checked sections',flush=True)
                    return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'tasks':outline})}}]}
                return await request(model,route,payload)
            rag.request=resumed_request
    async def section(documents,report,targets=None,outline=None,feedback=''):
        hit=next((c for c in cached if c['targets']==targets and c['outline']==outline),None)
        if hit and not feedback:
            return [app.Item(**i) for i in hit['items']]
        items=await original(documents,report,targets,outline,feedback)
        if targets:
            import hashlib
            key=hashlib.sha256(json.dumps(targets,ensure_ascii=False).encode()).hexdigest()[:12]
            (app.ROOT/f'.artifact-build/section-{key}.json').write_text(json.dumps({'outline':outline,'targets':targets,'items':[i.model_dump() for i in items]},ensure_ascii=False),encoding='utf-8')
        return items
    app.generate_section=section
    try:items=await app.generate(state['documents'],report)
    finally:app.generate_section=original;rag.request=request;checklist_generation.repair=original_repair
    (app.ROOT/'.artifact-build/checklist-live-result.json').write_text(json.dumps([i.model_dump() for i in items],ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'PASS {len(items)} items {time.monotonic()-started:.1f}s; workspace untouched',flush=True)
if __name__=='__main__':asyncio.run(main())
