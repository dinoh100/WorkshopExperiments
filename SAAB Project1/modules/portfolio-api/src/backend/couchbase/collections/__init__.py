"""
Couchbase collection bindings.

All collection classes should be imported here.
"""
# Import all collection classes here
# They will be auto-added by the add-couchbase-collection tool
from .project import ProjectCollection

# Export all collections
COLLECTIONS = [
    ProjectCollection,
]
