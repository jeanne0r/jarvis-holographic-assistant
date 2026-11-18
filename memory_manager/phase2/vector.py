"""Embedding identity checks and dedicated Qdrant transport; no prune/delete."""
import math
from ..indexer import index

COLLECTION = 'jarvis_knowledge_experimental_v1'
MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'


class Embeddings:
    def __init__(self, transport, artifact_sha256):
        if len(artifact_sha256) != 64 or any(c not in '0123456789abcdef' for c in artifact_sha256): raise ValueError('Pinned embedding artifact required')
        self.http, self.artifact = transport, artifact_sha256

    def __call__(self, text):
        response = self.http('POST', '/v1/embeddings', {'model': MODEL, 'input': text}, timeout=15)
        if response.get('model') != MODEL or response.get('artifact_sha256') != self.artifact or response.get('dimensions') != 384:
            raise ValueError('Embedding identity mismatch')
        vector = response['data'][0]['embedding']
        if len(vector) != 384 or any(type(v) not in (float, int) or not math.isfinite(v) for v in vector): raise ValueError('Embedding shape')
        return vector


class Qdrant:
    def __init__(self, transport): self.http = transport

    @staticmethod
    def path(collection):
        if collection != COLLECTION: raise PermissionError('Exact experimental collection required')
        return '/collections/' + collection

    def dimensions(self, collection):
        result = self.http('GET', self.path(collection), timeout=5)['result']
        config = result['config']['params']['vectors']
        if config.get('distance') != 'Cosine': raise ValueError('Vector distance mismatch')
        return config['size']

    def upsert(self, collection, point):
        return self.http('PUT', self.path(collection) + '/points', {'points': [point]}, timeout=10)

    def search(self, vector, scopes, owner):
        result = self.http('POST', self.path(COLLECTION) + '/points/query', {'query': vector, 'limit': 40, 'with_payload': True,
            'filter': {'must': [{'key': 'scope', 'match': {'any': sorted(scopes)}}],
                       'should': [{'key': 'owner', 'match': {'value': owner}}, {'key': 'scope', 'match': {'except': ['private']}}]}}, timeout=10)
        return [r['payload'] for r in result['result']['points']]


def index_validated(memory, principal, driver, embeddings):
    class BoundDriver:
        def dimensions(self, collection): return driver.dimensions(collection)
        def upsert(self, collection, point):
            point['payload'].update(embedding_model=MODEL, embedding_artifact_sha256=embeddings.artifact)
            return driver.upsert(collection, point)
    return index(memory, principal, BoundDriver(), embeddings, collection=COLLECTION)


def search(memory, principal, query, driver, embeddings):
    # Even a forged payload cannot authorize data: all IDs/revisions/ACL are reread.
    hits = driver.search(embeddings(query), principal.scopes, principal.name)
    hits = [hit for hit in hits if hit.get('embedding_model') == MODEL
            and hit.get('embedding_artifact_sha256') == embeddings.artifact]
    return memory.search(principal, query, vector_hits=hits)


def preflight(driver, embeddings):
    """Explicitly invoked read/query-only probe, never provision or mutate Qdrant."""
    if driver.dimensions(COLLECTION) != 384:
        raise ValueError('Experimental collection dimension mismatch')
    embeddings('Précontrôle synthétique JARVIS')
    return {'collection': COLLECTION, 'dimensions': 384, 'model': MODEL,
            'artifact_sha256': embeddings.artifact, 'qdrant_writes': 0}
