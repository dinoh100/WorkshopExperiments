"""
Bindings for working with the 'files' collection.
"""

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID, uuid4

from ...clients.couchbase import CouchbaseClient


# The type used for keys in this collection.
_KEY_TYPE = UUID

# The collection name in Couchbase
_COLLECTION_NAME = "files"


class FileState(str, Enum):
    """States a file can be in."""
    UPLOADING = "uploading"
    ARCHIVING = "archiving"
    DELETING = "deleting"
    DELETED = "deleted"
    FAILED = "failed"


class FilesDoc(BaseModel):
    """Model for files rows."""
    id: _KEY_TYPE = Field(default_factory=uuid4)
    filename: str
    size: int  # Size in bytes
    content_type: str
    state: FileState = FileState.UPLOADING
    archive_id: Optional[UUID] = None  # Set when file is archived
    error_message: Optional[str] = None  # Set when state is FAILED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ListParams(BaseModel):
    """Supported parameters for files list operations."""
    # Add more params here as needed
    limit: int = 50
    offset: int = 0


class FilesCollection:
    """Bindings for working with the 'files' Couchbase collection"""

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
        """Retrieves a files doc as a plain dict."""
        await self._get_collection()
        keyspace = self._client.get_keyspace(_COLLECTION_NAME)
        return await self._client.get_document(keyspace, str(id))

    async def get(self, id: _KEY_TYPE) -> FilesDoc | None:
        """Retrieves a files doc as a FilesDoc."""
        doc = await self._get_doc(id)
        if doc is None:
            return None
        doc['id'] = id
        return FilesDoc(**doc)

    async def _list_rows(self, params: ListParams | None = None) -> list[dict]:
        """Retrieves files docs as a list of plain dicts."""
        params = params or ListParams()
        keyspace = self._client.get_keyspace(_COLLECTION_NAME)
        query = self._client.build_list_query(keyspace, limit=params.limit, offset=params.offset)
        return await self._client.query_documents(query)

    async def list(self, params: ListParams | None = None) -> list[FilesDoc]:
        """Retrieves a list of files docs as FilesDoc instances."""
        rows = await self._list_rows(params)
        return [FilesDoc(**{**row, 'id': row.get('id')}) for row in rows]

    async def delete(self, id: _KEY_TYPE) -> bool:
        """Delete a files doc."""
        keyspace = self._client.get_keyspace(_COLLECTION_NAME)
        return await self._client.delete_document(keyspace, str(id))

    async def upsert(self, doc: FilesDoc) -> FilesDoc:
        """Insert or update a files doc."""
        keyspace = self._client.get_keyspace(_COLLECTION_NAME)
        await self._client.upsert_document(keyspace, str(doc.id), doc.model_dump(mode='json'))
        return doc
