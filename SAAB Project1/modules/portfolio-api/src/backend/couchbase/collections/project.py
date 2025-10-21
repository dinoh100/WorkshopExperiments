"""
Bindings for working with the 'project' collection.
"""

from pydantic import BaseModel
from uuid import UUID
from datetime import date

from ...clients.couchbase import CouchbaseClient


# The type used for keys in this collection.
_KEY_TYPE = UUID

# The collection name in Couchbase
_COLLECTION_NAME = "project"


class ProjectDoc(BaseModel):
    """Model for project rows."""
    id: _KEY_TYPE
    title: str
    description: str
    skills: list[str]
    started_at: date
    finished_at: date | None = None


class ListParams(BaseModel):
    """Supported parameters for project list operations."""
    # Add more params here as needed
    limit: int = 50
    offset: int = 0


class ProjectCollection:
    """Bindings for working with the 'project' Couchbase collection"""

    def __init__(self, client: CouchbaseClient):
        self._client = client
        self._collection = None

    ## Utils ##

    async def _get_collection(self):
        """Get the collection handle, creating it if necessary."""
        if not self._collection:
            keyspace = self._client.get_keyspace(_COLLECTION_NAME)
            self._collection = await self._client.get_collection(keyspace)
        return self._collection

    ## Initialization ##

    async def initialize(self):
        """Creates the collection if it doesn't already exist, and stores a handle to it."""
        await self._get_collection()

    ## Operations ##

    async def _get_doc(self, id: _KEY_TYPE) -> dict | None:
        """Retrieves a project doc as a plain dict."""
        await self._get_collection()
        keyspace = self._client.get_keyspace(_COLLECTION_NAME)
        return await self._client.get_document(keyspace, str(id))

    async def get(self, id: _KEY_TYPE) -> ProjectDoc | None:
        """Retrieves a project doc as a ProjectDoc."""
        doc = await self._get_doc(id)
        if doc is None:
            return None
        doc['id'] = id
        return ProjectDoc(**doc)

    async def _list_rows(self, params: ListParams | None = None) -> list[dict]:
        """Retrieves project docs as a list of plain dicts."""
        params = params or ListParams()
        keyspace = self._client.get_keyspace(_COLLECTION_NAME)
        query = self._client.build_list_query(keyspace, limit=params.limit, offset=params.offset)
        return await self._client.query_documents(query)

    async def list(self, params: ListParams | None = None) -> list[ProjectDoc]:
        """Retrieves a list of project docs as ProjectDoc instances."""
        rows = await self._list_rows(params)
        return [ProjectDoc(**{**row, 'id': row.get('id')}) for row in rows]

    async def delete(self, id: _KEY_TYPE) -> bool:
        """Delete a project doc."""
        keyspace = self._client.get_keyspace(_COLLECTION_NAME)
        return await self._client.delete_document(keyspace, str(id))

    async def upsert(self, doc: ProjectDoc) -> ProjectDoc:
        """Insert or update a project doc."""
        keyspace = self._client.get_keyspace(_COLLECTION_NAME)
        await self._client.upsert_document(keyspace, str(doc.id), doc.model_dump(mode='json'))
        return doc
