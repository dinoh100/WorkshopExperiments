# File Compression API - Implementation Summary

## Overview
A REST API for file compression that accepts file uploads, compresses them into tar.gz archives, and provides download endpoints. Built with FastAPI, Couchbase, and Polytope.

## Implemented Endpoints

### Files
- **POST /files** - Upload one or more files
  - Accepts multipart form data with file attachments
  - Returns: `{"archive_id": "uuid"}`
  - Files are automatically queued for compression

- **GET /files** - List all uploaded files
  - Query params: `limit` (default: 50), `offset` (default: 0)
  - Returns array of file metadata with state information

- **GET /files/{fileId}** - Get specific file details
  - Returns file state, metadata (filename, size, timestamps)
  - Includes download URL when archive is completed

### Archives
- **GET /archives** - List all archives
  - Query params: `limit` (default: 50), `offset` (default: 0)
  - Returns array of archive metadata

- **GET /archives/{archiveId}** - Get archive details
  - Returns archive state, metadata (contained files, total size, timestamps)
  - Includes download URL when state is "completed"

- **GET /archives/{archiveId}/download** - Download compressed archive
  - Returns tar.gz file for download
  - Only available when archive state is "completed"

## Architecture

### Storage
- **Couchbase**: Stores metadata for files and archives
  - `files` collection: Tracks uploaded files with state management
  - `archives` collection: Tracks compression jobs and archive metadata

### File States
- **uploaded**: Initial state after file upload
- **processing**: File is being compressed
- **archived**: File has been compressed and is available in archive
- **failed**: Compression failed

### Archive States
- **pending**: Archive created, waiting to process
- **processing**: Files are being compressed
- **completed**: Archive ready for download
- **failed**: Compression failed

### Background Processing
- File compression happens asynchronously after upload
- Original uploaded files are automatically deleted after successful compression
- Archives are stored in `/tmp/compression-archives/` within the container

## Testing

Example test commands:

```bash
# Upload files
cd /tmp
echo "Test file 1" > file1.txt
echo "Test file 2" > file2.txt
curl -X POST http://localhost:3030/files \
  -F "files=@file1.txt" \
  -F "files=@file2.txt"

# List files
curl http://localhost:3030/files

# List archives
curl http://localhost:3030/archives

# Get archive details
curl http://localhost:3030/archives/{archive_id}

# Download archive
curl -O http://localhost:3030/archives/{archive_id}/download
```

## Key Features

✅ Multi-file upload support
✅ Automatic background compression
✅ State tracking for files and archives
✅ Metadata storage in Couchbase
✅ Automatic cleanup of temporary files
✅ RESTful API design
✅ OpenAPI/Swagger documentation available at `/docs`
✅ Health check endpoint with service status

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:3030/docs
- **Health Check**: http://localhost:3030/health

## Service Information

- **Port**: 3030
- **Hot Reload**: Enabled (changes auto-applied)
- **Couchbase**: Connected and operational
- **Container**: compression-api
