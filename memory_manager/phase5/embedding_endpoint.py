"""Opt-in raw-vector route; attach only after a reviewed CT205 service change.

Reuses the loaded model and lock. No model loading, downloads, collection writes,
or dependencies imported at module import. The caller must pin the actual loaded
ONNX path; whole manifest also covers tokenizer, preprocessing and runtime.
"""
import hashlib
import hmac
from pathlib import Path
from ..store import digest
from ..phase2.vector import MODEL
from .vector import validate_vector


def file_hash(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


class Provider:
    def __init__(self, *, model, lock, token_count, files, runtime, loaded_onnx, expected_manifest):
        if not files or not runtime or not callable(token_count): raise ValueError('Complete pinned pipeline required')
        resolved = {str(Path(p).resolve()): sha for p, sha in files.items()}
        if str(Path(loaded_onnx).resolve()) not in resolved: raise ValueError('Actual loaded artifact required')
        for path, sha in resolved.items():
            if file_hash(path) != sha: raise ValueError('Artifact changed')
        manifest = digest({'model': MODEL, 'files': resolved, 'runtime': runtime,
                           'preprocessing': 'fastembed-document/query-v1;max128;no-truncation'})
        if manifest != expected_manifest: raise ValueError('Pipeline manifest mismatch')
        self.model, self.lock, self.token_count, self.artifact = model, lock, token_count, manifest

    def embed(self, request):
        if not isinstance(request, dict) or set(request) != {'model', 'kind', 'input'}: raise ValueError('Embedding fields')
        text, kind = request['input'], request['kind']
        if request['model'] != MODEL or kind not in {'query', 'document'}: raise ValueError('Model or preprocessing')
        if not isinstance(text, str) or not 0 < len(text.encode()) <= 8000: raise ValueError('Input bound')
        # A separately constructed tokenizer must count special tokens and the
        # model-specific query prefix, with truncation disabled. Never mutate the
        # tokenizer of the already loaded historical service.
        with self.lock:
            count = self.token_count(text, kind)
            if type(count) is not int or not 0 < count <= 128: raise ValueError('Context limit; truncation forbidden')
            vectors = list((self.model.query_embed if kind == 'query' else self.model.embed)([text]))
        if len(vectors) != 1: raise ValueError('Single result required')
        v = vectors[0].tolist() if hasattr(vectors[0], 'tolist') else vectors[0]
        return {'model': MODEL, 'artifact_sha256': self.artifact, 'dimensions': 384,
                'kind': kind, 'input_tokens': count, 'data': [{'embedding': validate_vector(v)}]}


def attach(app, provider, *, enabled=False, token_file=None):
    """Disabled by default. Separate credential, never reuse historical API key."""
    if not enabled: return False
    from fastapi import Request, HTTPException
    import threading
    admission = threading.BoundedSemaphore(1)
    if Path(token_file).stat().st_mode & 0o077:raise PermissionError('0600 credential required')
    token = Path(token_file).read_text().strip()
    if len(token) < 32: raise ValueError('Dedicated credential required')
    async def route(request: Request):
        if not hmac.compare_digest(request.headers.get('Authorization', ''), 'Bearer ' + token):
            raise HTTPException(403, 'Denied')
        size = request.headers.get('content-length', '')
        if not size.isdigit() or not 0 < int(size) <= 16000 or request.headers.get('transfer-encoding'):
            raise HTTPException(413, 'Body limit')
        raw = await request.body()
        if len(raw) != int(size): raise HTTPException(400, 'Body length')
        try:
            from ..phase2.validation import loads
            import asyncio
            if not admission.acquire(blocking=False): raise HTTPException(429, 'Embedding capacity busy')
            def bounded():
                try: return provider.embed(loads(raw))
                finally: admission.release()
            return await asyncio.to_thread(bounded)
        except (ValueError, TypeError, KeyError): raise HTTPException(422, 'Invalid embedding request')
    app.add_api_route('/v1/embeddings', route, methods=['POST'])
    return True


def from_loaded_model(model, lock, config):
    """Version-specific binding, fails closed on unobserved fastembed internals.

    Config is reviewed host data containing files + expected manifest, never model
    output. No new TextEmbedding instance is created.
    """
    import importlib.metadata
    from tokenizers import Tokenizer
    from fastembed.text.text_embedding_base import TextEmbeddingBase
    versions={name:importlib.metadata.version(name) for name in ('fastembed','onnxruntime','tokenizers')}
    if versions!={'fastembed':'0.9.1','onnxruntime':'1.31.1','tokenizers':'0.23.3'}:raise ValueError('Review runtime version change')
    inner=model.model
    if type(inner).query_embed is not TextEmbeddingBase.query_embed:raise ValueError('Unreviewed query preprocessing')
    if inner.tokenizer.truncation and inner.tokenizer.truncation.get('max_length',0)<128:
        raise ValueError('Loaded tokenizer truncates below the serving limit')
    actual=Path(inner.model._model_path).resolve()
    counter=Tokenizer.from_str(inner.tokenizer.to_str());counter.no_truncation();counter.no_padding()
    return Provider(model=model,lock=lock,token_count=lambda text,kind:len(counter.encode(text).ids),
        files=config['files'],runtime=versions,loaded_onnx=actual,expected_manifest=config['manifest_sha256'])
