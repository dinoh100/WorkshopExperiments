"""
Routes for file compression API.
"""

import asyncio
import os
import shutil
import tarfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..utils import log
from ..couchbase.collections.files import FilesCollection, FilesDoc, FileState, ListParams as FileListParams
from ..couchbase.collections.archives import ArchivesCollection, ArchivesDoc, ArchiveState, ListParams as ArchiveListParams

logger = log.get_logger(__name__)
router = APIRouter()

# Storage configuration
UPLOAD_DIR = Path("/tmp/compression-uploads")
ARCHIVE_DIR = Path("/tmp/compression-archives")

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


#### Response Models ####

class FileUploadResponse(BaseModel):
    """Response for file upload."""
    archive_id: str


class FileMetadata(BaseModel):
    """File metadata response."""
    id: str
    filename: str
    size: int
    content_type: Optional[str] = None
    uploaded_at: datetime
    archive_id: Optional[str] = None
    state: str


class FileDetailResponse(BaseModel):
    """Detailed file response."""
    id: str
    filename: str
    size: int
    content_type: Optional[str] = None
    uploaded_at: datetime
    archive_id: Optional[str] = None
    state: str
    metadata: dict = Field(default_factory=dict)
    download_url: Optional[str] = None


class ArchiveMetadata(BaseModel):
    """Archive metadata response."""
    id: str
    state: str
    file_ids: List[str]
    total_size: int
    created_at: datetime
    completed_at: Optional[datetime] = None


class ArchiveDetailResponse(BaseModel):
    """Detailed archive response."""
    id: str
    state: str
    metadata: dict
    download_url: Optional[str] = None


#### Helper Functions ####

def get_collections(request: Request) -> tuple[FilesCollection, ArchivesCollection]:
    """Get collection instances from app state."""
    couchbase_client = request.app.state.couchbase_client
    files_collection = FilesCollection(couchbase_client)
    archives_collection = ArchivesCollection(couchbase_client)
    return files_collection, archives_collection


async def compress_files(archive_id: uuid.UUID, files: List[FilesDoc]) -> tuple[str, int]:
    """
    Compress multiple files into a tar.gz archive.
    Returns the archive path and total size.
    """
    archive_filename = f"archive-{archive_id}.tar.gz"
    archive_path = ARCHIVE_DIR / archive_filename
    
    # Create tar.gz archive
    with tarfile.open(archive_path, "w:gz") as tar:
        for file_doc in files:
            if file_doc.file_path and Path(file_doc.file_path).exists():
                tar.add(file_doc.file_path, arcname=file_doc.filename)
    
    # Get archive size
    archive_size = archive_path.stat().st_size
    
    return str(archive_path), archive_size


async def cleanup_files(files: List[FilesDoc]):
    """Delete temporary uploaded files."""
    for file_doc in files:
        if file_doc.file_path:
            try:
                Path(file_doc.file_path).unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to delete file {file_doc.file_path}: {e}")


async def process_archive(archive_id: uuid.UUID, files_collection: FilesCollection, archives_collection: ArchivesCollection):
    """Background task to compress files and update archive status."""
    try:
        # Get archive
        archive = await archives_collection.get(archive_id)
        if not archive:
            logger.error(f"Archive {archive_id} not found")
            return
        
        # Update archive state to processing
        archive.state = ArchiveState.PROCESSING
        await archives_collection.upsert(archive)
        
        # Get all files for this archive
        files = []
        for file_id in archive.file_ids:
            file_doc = await files_collection.get(file_id)
            if file_doc:
                files.append(file_doc)
                # Update file state
                file_doc.state = FileState.PROCESSING
                await files_collection.upsert(file_doc)
        
        # Compress files
        archive_path, archive_size = await compress_files(archive_id, files)
        
        # Update archive with results
        archive.state = ArchiveState.COMPLETED
        archive.archive_path = archive_path
        archive.total_size = archive_size
        archive.completed_at = datetime.utcnow()
        archive.download_url = f"/archives/{archive_id}/download"
        await archives_collection.upsert(archive)
        
        # Update all files to archived state
        for file_doc in files:
            file_doc.state = FileState.ARCHIVED
            await files_collection.upsert(file_doc)
        
        # Cleanup original uploaded files
        await cleanup_files(files)
        
        logger.info(f"Archive {archive_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to process archive {archive_id}: {e}")
        # Update archive state to failed
        try:
            archive = await archives_collection.get(archive_id)
            if archive:
                archive.state = ArchiveState.FAILED
                await archives_collection.upsert(archive)
        except Exception as update_error:
            logger.error(f"Failed to update archive state: {update_error}")


#### Routes ####

@router.post("/files", response_model=FileUploadResponse)
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    """
    Upload one or more files for compression.
    Returns an archive ID that can be used to check status and download.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    files_collection, archives_collection = get_collections(request)
    
    # Create archive record
    archive_id = uuid.uuid4()
    archive = ArchivesDoc(
        id=archive_id,
        state=ArchiveState.PENDING,
        file_ids=[],
        total_size=0,
        created_at=datetime.utcnow()
    )
    
    # Save uploaded files and create file records
    file_ids = []
    total_size = 0
    
    for upload_file in files:
        # Generate unique file ID
        file_id = uuid.uuid4()
        
        # Save file to temporary storage
        file_path = UPLOAD_DIR / f"{file_id}_{upload_file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        
        # Get file size
        file_size = file_path.stat().st_size
        total_size += file_size
        
        # Create file record
        file_doc = FilesDoc(
            id=file_id,
            filename=upload_file.filename,
            size=file_size,
            content_type=upload_file.content_type,
            uploaded_at=datetime.utcnow(),
            archive_id=archive_id,
            state=FileState.UPLOADED,
            file_path=str(file_path)
        )
        
        await files_collection.upsert(file_doc)
        file_ids.append(file_id)
    
    # Update archive with file IDs
    archive.file_ids = file_ids
    archive.total_size = total_size
    await archives_collection.upsert(archive)
    
    # Start background compression task
    asyncio.create_task(process_archive(archive_id, files_collection, archives_collection))
    
    return FileUploadResponse(archive_id=str(archive_id))


@router.get("/files", response_model=List[FileMetadata])
async def list_files(request: Request, limit: int = 50, offset: int = 0):
    """
    List all uploaded files.
    """
    files_collection, _ = get_collections(request)
    
    params = FileListParams(limit=limit, offset=offset)
    files = await files_collection.list(params)
    
    return [
        FileMetadata(
            id=str(f.id),
            filename=f.filename,
            size=f.size,
            content_type=f.content_type,
            uploaded_at=f.uploaded_at,
            archive_id=str(f.archive_id) if f.archive_id else None,
            state=f.state.value
        )
        for f in files
    ]


@router.get("/files/{file_id}", response_model=FileDetailResponse)
async def get_file(request: Request, file_id: str):
    """
    Get file details including state, metadata, and download URL if available.
    """
    files_collection, archives_collection = get_collections(request)
    
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    
    file_doc = await files_collection.get(file_uuid)
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Build metadata
    metadata = {
        "filename": file_doc.filename,
        "size": file_doc.size,
        "uploaded_at": file_doc.uploaded_at.isoformat()
    }
    
    if file_doc.content_type:
        metadata["content_type"] = file_doc.content_type
    
    # Get download URL if file is archived
    download_url = None
    if file_doc.archive_id and file_doc.state == FileState.ARCHIVED:
        archive = await archives_collection.get(file_doc.archive_id)
        if archive and archive.state == ArchiveState.COMPLETED:
            download_url = f"/archives/{file_doc.archive_id}/download"
    
    return FileDetailResponse(
        id=str(file_doc.id),
        filename=file_doc.filename,
        size=file_doc.size,
        content_type=file_doc.content_type,
        uploaded_at=file_doc.uploaded_at,
        archive_id=str(file_doc.archive_id) if file_doc.archive_id else None,
        state=file_doc.state.value,
        metadata=metadata,
        download_url=download_url
    )


@router.get("/archives", response_model=List[ArchiveMetadata])
async def list_archives(request: Request, limit: int = 50, offset: int = 0):
    """
    List all archives.
    """
    _, archives_collection = get_collections(request)
    
    params = ArchiveListParams(limit=limit, offset=offset)
    archives = await archives_collection.list(params)
    
    return [
        ArchiveMetadata(
            id=str(a.id),
            state=a.state.value,
            file_ids=[str(fid) for fid in a.file_ids],
            total_size=a.total_size,
            created_at=a.created_at,
            completed_at=a.completed_at
        )
        for a in archives
    ]


@router.get("/archives/{archive_id}", response_model=ArchiveDetailResponse)
async def get_archive(request: Request, archive_id: str):
    """
    Get archive details including state, metadata, and download URL if completed.
    """
    _, archives_collection = get_collections(request)
    
    try:
        archive_uuid = uuid.UUID(archive_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid archive ID format")
    
    archive = await archives_collection.get(archive_uuid)
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")
    
    # Build metadata
    metadata = {
        "contained_files": [str(fid) for fid in archive.file_ids],
        "total_size": archive.total_size,
        "created_at": archive.created_at.isoformat()
    }
    
    if archive.completed_at:
        metadata["completed_at"] = archive.completed_at.isoformat()
    
    # Add download URL if archive is completed
    download_url = None
    if archive.state == ArchiveState.COMPLETED:
        download_url = f"/archives/{archive_id}/download"
    
    return ArchiveDetailResponse(
        id=str(archive.id),
        state=archive.state.value,
        metadata=metadata,
        download_url=download_url
    )


@router.get("/archives/{archive_id}/download")
async def download_archive(request: Request, archive_id: str):
    """
    Download the compressed archive.
    Only available if archive is completed.
    """
    _, archives_collection = get_collections(request)
    
    try:
        archive_uuid = uuid.UUID(archive_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid archive ID format")
    
    archive = await archives_collection.get(archive_uuid)
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")
    
    if archive.state != ArchiveState.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Archive is not ready for download. Current state: {archive.state.value}"
        )
    
    if not archive.archive_path or not Path(archive.archive_path).exists():
        raise HTTPException(status_code=404, detail="Archive file not found")
    
    # Read and return the archive file
    archive_path = Path(archive.archive_path)
    
    from fastapi.responses import FileResponse
    
    return FileResponse(
        path=archive_path,
        media_type="application/gzip",
        filename=f"archive-{archive_id}.tar.gz"
    )
