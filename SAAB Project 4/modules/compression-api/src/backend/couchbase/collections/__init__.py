"""
Couchbase collection bindings.

All collection classes should be imported here.
"""
# Import all collection classes here
# They will be auto-added by the add-couchbase-collection tool
from .archives import ArchivesCollection
from .files import FilesCollection

# Export all collections
COLLECTIONS = [
    FilesCollection,
    ArchivesCollection,
]
