"""Grounded Q&A and explicit, non-executing natural language action proposals."""
import json
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import HTTPException
from langgraph.graph import StateGraph, START, END
from backend.agents import FlowState, json_call
from backend import rag

class Citation(BaseModel):
    document_id: str
    chunk_id: str
    quote: str = Field(min_length=1,max_length=2000)
    kind: Literal['text','visual']='text'
    slide: int | None=None
class Action(BaseModel):
    kind: Literal['progress','calendar']
    item_ids: list[str] = Field(min_length=1,max_length=100)
    status: Literal['todo','doing','done']='done'
class Answer(BaseModel):
    answer: str = Field(min_length=1,max_length=8000)
    evidence: list[Citation] = Field(default_factory=list,max_length=12)
    insufficient: bool = False
    action: Action | None=None

async def search(documents, root, query):
    if not documents: return []
    if any(d.get('rag',{}).get('status')!='ready' or d['rag'].get('embedding_model')!=rag.model() or d['rag'].get('version')!=rag.VERSION for d in documents):
        raise HTTPException(409,'검색 자료를 다시 분석해 주세요.')
    vector=(await rag.embed([query]))[0]
    def run():
        collection=rag.collection(root)
        matches=[]
        for doc in documents:
            token=doc['rag']['index_id']
            count=len(collection.get(where={'index_id':token},include=[])['ids'])
            if count!=doc['rag']['chunk_count']: raise HTTPException(409,'문서 검색 자료가 불완전합니다.')
            result=collection.query(query_embeddings=[vector],where={'index_id':token},n_results=min(6,count),include=['documents','metadatas','distances'])
            for key,text,meta,distance in zip(result['ids'][0],result['documents'][0],result['metadatas'][0],result['distances'][0]):
                if meta.get('document_id')!=doc['id']: raise HTTPException(409,'검색 자료의 소속이 일치하지 않습니다.')
                if distance<=0.8: matches.append({'chunk_id':key,'text':text,**meta,'distance':distance})
        return sorted(matches,key=lambda c:c['distance'])[:12]
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(run)

async def answer_question(state, conversation, question, root, report, validate):
    async def retrieve(flow):
        report('retrieve','업무 Q&A Agent가 질문에 관련된 문서 근거를 검색합니다.')
        query=question
        if conversation.get('messages'):
            context=await json_call('업무 Q&A Agent','대화와 마지막 질문을 참고해 문서 검색에 사용할 독립적인 질문으로 바꾼다. 사실을 추가하지 마라. 출력 {"query":"검색 질문"}',{'summary':conversation.get('summary',''),'history':conversation['messages'][-6:],'question':question})
            query=str(context.get('query',question))[:4000]
        chunks=await search(state['documents'],root,query)
        if not chunks:
            rewritten=await json_call('업무 Q&A Agent','업무 문서 검색 질문을 동의어나 핵심 업무 용어로 보완한다. 출력 {"query":"검색어"}',{'question':query})
            chunks=await search(state['documents'],root,str(rewritten.get('query',query))[:4000])
        return {'context':chunks}
    async def respond(flow):
        report('analyze',f'{rag.chat_model()} · 업무 Q&A Agent가 근거를 확인하며 답변하고 있습니다.')
        from datetime import datetime
        from zoneinfo import ZoneInfo
        result=Answer.model_validate(await json_call('업무 Q&A Agent',
            '인수자의 업무 질문에 근거로 답한다. 문서가 뒷받침하지 않으면 insufficient=true로 하고 인계자 추가 확인을 안내한다. 대화는 맥락일 뿐 근거가 아니다. '
            '문서 사실을 답할 때는 evidence에 제공된 chunk_id와 document_id 및 정확한 원문 quote를 포함한다. 이미지 청크는 kind=visual과 slide를 포함하고 해석임을 명시한다. '
            '수행 완료/진행 상태 변경 또는 캘린더 등록을 명시적으로 요청한 경우에만 action을 제안하며, 실행 완료라고 말하지 마라. '
            'item_ids는 제공된 체크리스트 id만 사용한다. 대상이 모호하면 action=null로 추가 질문한다. 오늘은 제공된 한국 날짜 기준이다. '
            '출력 {"answer":"한국어 답변 또는 작업 확인 안내","evidence":[],"insufficient":false,"action":null}. '
            'action 형식: {"kind":"progress 또는 calendar","item_ids":["id"],"status":"todo 또는 doing 또는 done"}.',
            {'question':question,'today':datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat(),'summary':conversation.get('summary',''),
             'history':conversation.get('messages',[])[-8:],'chunks':flow['context'],'items':state['items'],'schedule':state.get('schedule',{}).get('confirmed',[])}))
        if result.action:
            ids=[i['id'] for i in state['items']]
            if set(result.action.item_ids)-set(ids) or len(set(result.action.item_ids))!=len(result.action.item_ids):
                raise HTTPException(502,'AI가 제안한 대상 업무가 올바르지 않습니다.')
        elif not result.insufficient and not result.evidence:
            result=Answer(answer='문서에서 답변 근거를 확인하지 못했습니다. 인계자에게 추가 설명을 요청해 주세요.',insufficient=True)
        if result.evidence:
            try: validate(result,flow['context'])
            except ValueError:
                result=Answer(answer='AI 답변의 원문 근거를 검증하지 못했습니다. 인계자에게 추가 설명을 요청하거나 질문을 구체화해 주세요.',insufficient=True)
        return {'result':result.model_dump(mode='json')}
    graph=StateGraph(FlowState)
    graph.add_node('knowledge_search',retrieve);graph.add_node('qa_agent',respond)
    graph.add_edge(START,'knowledge_search');graph.add_edge('knowledge_search','qa_agent');graph.add_edge('qa_agent',END)
    result=(await graph.compile().ainvoke({}))['result']
    return result
