"""Opt-in extension: the existing authenticated Memory API and MCP stay authoritative."""
from ..phase2.http_bridge import dispatch
from .vector import search


def extension(driver,embeddings,*,observer=None):
    def searcher(memory,principal,query,**filters):
        rows=search(memory,principal,query,driver,embeddings,**filters)
        if observer:observer(query,filters,rows)
        return rows
    def handle(memory,principal,request,url,query):
        if url.path=='/v1/search' and request.command=='GET':
            if set(query)-{'q','type','subject','limit'}:raise ValueError('Unknown filter')
            return 200,{'items':searcher(memory,principal,query.get('q',''),memory_type=query.get('type'),subject=query.get('subject'),limit=int(query.get('limit',10)))},'application/json'
        return dispatch(memory,principal,request,url,query,searcher=searcher)
    return handle
