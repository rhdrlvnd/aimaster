"""Opt-in real PowerPoint + gateway smoke check, isolated from user workspace."""
import sys
import tempfile
import subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend import app as module

if len(sys.argv)==1:
    with tempfile.TemporaryDirectory() as folder:
        subprocess.run([sys.executable,__file__,'--worker',folder],check=True)
    print('Temporary ChromaDB cleaned after worker exit.',flush=True)
    raise SystemExit(0)

module.DB=Path(sys.argv[2])/'smoke.sqlite3'
try:
    with TestClient(module.app) as client:
        file=Path('outputs/handover-set/03_배치설계와_운영개선_검토.pptx')
        result=client.post('/api/documents',files={'file':(file.name,file.read_bytes())})
        assert result.status_code==200, result.text
        state=client.get('/api/workspace').json()
        doc=state['documents'][0]
        assert doc['slide_count']==5
        print('upload/render:',doc['slide_count'],'slides',flush=True)
        for path in sorted(Path('outputs/handover-set').glob('*')):
            if path.suffix not in {'.docx','.xlsx'}: continue
            result=client.post('/api/documents',files={'file':(path.name,path.read_bytes())})
            assert result.status_code==200,result.text
            print('indexed:',path.suffix,flush=True)
        state=client.get('/api/workspace').json()
        assert all(d['rag']['status']=='ready' for d in state['documents'])
        print('chunks:',sum(d['rag']['chunk_count'] for d in state['documents']),flush=True)
        result=client.post('/api/generate',json={'revision':state['revision']})
        assert result.status_code==200, result.text
        state=client.get('/api/workspace').json()
        visual=[e for item in state['items'] for e in item['evidence'] if e['kind']=='visual']
        assert visual
        assert all(1<=e['slide']<=5 for e in visual)
        for e in visual:
            assert client.get(f'/api/documents/{doc["id"]}/slides/{e["slide"]}').status_code==200
        print('real AI:',len(state['items']),'items,',len(visual),'visual references',flush=True)
finally:
    pass
