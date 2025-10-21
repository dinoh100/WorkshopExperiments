"""
Temporal workflows for file compression and state management.
"""

import base64
import io
import zipfile
from datetime import timedelta
from typing import List
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from ..couchbase.collections.files import FileState, FilesDoc
from ..couchbase.collections.archives import ArchiveState, ArchivesDoc


# Activities


@activity.defn
async def update_file_state(file_id: str, state: str, error_message: str = None) -> None:
    """Update the state of a file in Couchbase."""
    from ..main import app
    from ..couchbase.collections.files import FilesCollection
    from datetime import datetime, timezone

    client = app.state.couchbase_client
    files_collection = FilesCollection(client)
    await files_collection.initialize()

    file_doc = await files_collection.get(UUID(file_id))
    if file_doc:
        file_doc.state = FileState(state)
        file_doc.updated_at = datetime.now(timezone.utc)
        if error_message:
            file_doc.error_message = error_message
        await files_collection.upsert(file_doc)


@activity.defn
async def update_archive_state(archive_id: str, state: str, error_message: str = None) -> None:
    """Update the state of an archive in Couchbase."""
    from ..main import app
    from ..couchbase.collections.archives import ArchivesCollection
    from datetime import datetime, timezone

    client = app.state.couchbase_client
    archives_collection = ArchivesCollection(client)
    await archives_collection.initialize()

    archive_doc = await archives_collection.get(UUID(archive_id))
    if archive_doc:
        archive_doc.state = ArchiveState(state)
        archive_doc.updated_at = datetime.now(timezone.utc)
        if error_message:
            archive_doc.error_message = error_message
        await archives_collection.upsert(archive_doc)


@activity.defn
async def compress_files(file_ids: List[str], archive_id: str) -> dict:
    """Compress multiple files into a single archive."""
    from ..main import app
    from ..couchbase.collections.files import FilesCollection
    from ..couchbase.collections.archives import ArchivesCollection

    client = app.state.couchbase_client
    files_collection = FilesCollection(client)
    archives_collection = ArchivesCollection(client)
    await files_collection.initialize()
    await archives_collection.initialize()

    # Create zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_id_str in file_ids:
            file_doc = await files_collection.get(UUID(file_id_str))
            if file_doc:
                # In a real implementation, you'd retrieve actual file content
                # For now, we'll create a placeholder entry
                file_content = f"Content of {file_doc.filename}"
                zip_file.writestr(file_doc.filename, file_content)

    # Get compressed data
    zip_buffer.seek(0)
    compressed_data = zip_buffer.read()
    compressed_size = len(compressed_data)
    encoded_data = base64.b64encode(compressed_data).decode('utf-8')

    # Update archive with compressed data
    archive_doc = await archives_collection.get(UUID(archive_id))
    if archive_doc:
        archive_doc.compressed_data = encoded_data
        archive_doc.size = compressed_size
        await archives_collection.upsert(archive_doc)

    return {
        "size": compressed_size,
        "file_count": len(file_ids)
    }


@activity.defn
async def mark_files_as_archived(file_ids: List[str], archive_id: str) -> None:
    """Mark files as archived and set their archive_id."""
    from ..main import app
    from ..couchbase.collections.files import FilesCollection
    from datetime import datetime, timezone

    client = app.state.couchbase_client
    files_collection = FilesCollection(client)
    await files_collection.initialize()

    for file_id_str in file_ids:
        file_doc = await files_collection.get(UUID(file_id_str))
        if file_doc:
            file_doc.state = FileState.ARCHIVING
            file_doc.archive_id = UUID(archive_id)
            file_doc.updated_at = datetime.now(timezone.utc)
            await files_collection.upsert(file_doc)


@activity.defn
async def delete_files(file_ids: List[str]) -> None:
    """Delete files from Couchbase."""
    from ..main import app
    from ..couchbase.collections.files import FilesCollection
    from datetime import datetime, timezone

    client = app.state.couchbase_client
    files_collection = FilesCollection(client)
    await files_collection.initialize()

    for file_id_str in file_ids:
        file_doc = await files_collection.get(UUID(file_id_str))
        if file_doc:
            file_doc.state = FileState.DELETING
            file_doc.updated_at = datetime.now(timezone.utc)
            await files_collection.upsert(file_doc)
            
            # Actually delete the file
            await files_collection.delete(UUID(file_id_str))


# Workflows


@workflow.defn
class FileCompressionWorkflow:
    """Workflow for compressing files into an archive and managing state transitions."""

    @workflow.run
    async def run(self, archive_id: str, file_ids: List[str]) -> dict:
        """
        Execute the file compression workflow.
        
        Steps:
        1. Update archive state to COMPRESSING
        2. Update all files to ARCHIVING state
        3. Compress files into archive
        4. Update archive state to IDLE
        5. Delete original files
        6. Return result
        """
        retry_policy = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
        )

        try:
            # Step 1: Update archive state to COMPRESSING
            await workflow.execute_activity(
                update_archive_state,
                args=[archive_id, ArchiveState.COMPRESSING.value],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # Step 2: Mark files as being archived
            await workflow.execute_activity(
                mark_files_as_archived,
                args=[file_ids, archive_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # Step 3: Compress files
            compression_result = await workflow.execute_activity(
                compress_files,
                args=[file_ids, archive_id],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )

            # Step 4: Update archive state to IDLE
            await workflow.execute_activity(
                update_archive_state,
                args=[archive_id, ArchiveState.IDLE.value],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # Step 5: Delete original files
            await workflow.execute_activity(
                delete_files,
                args=[file_ids],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=retry_policy,
            )

            return {
                "status": "success",
                "archive_id": archive_id,
                "compressed_size": compression_result["size"],
                "file_count": compression_result["file_count"],
            }

        except Exception as e:
            # Mark archive as failed
            await workflow.execute_activity(
                update_archive_state,
                args=[archive_id, ArchiveState.FAILED.value, str(e)],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # Mark files as failed
            for file_id in file_ids:
                await workflow.execute_activity(
                    update_file_state,
                    args=[file_id, FileState.FAILED.value, str(e)],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )

            return {
                "status": "failed",
                "archive_id": archive_id,
                "error": str(e),
            }
