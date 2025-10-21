# File Compression REST API

A REST API for managing file compression with automatic archiving, built with FastAPI, Couchbase, and Temporal.

## Architecture

- **FastAPI**: REST API framework
- **Couchbase**: NoSQL database for storing files and archives
- **Temporal**: Workflow orchestration for state management and compression tasks
- **Docker**: All services run in containers managed by Polytope

## Features

### Files Resource
Files support the following states:
- `uploading` - File is being uploaded
- `archiving` - File is being added to an archive
- `deleting` - File is being deleted
- `deleted` - File has been deleted
- `failed` - Operation failed

### Archives Resource
Archives support the following states:
- `queued` - Archive is waiting to be processed
- `compressing` - Files are being compressed
- `idle` - Archive is ready for download
- `downloading` - Archive is being downloaded
- `failed` - Compression failed

### Workflow
When an archive is created:
1. Archive state changes to `compressing`
2. Files are marked as `archiving`
3. Files are compressed into a ZIP archive
4. Compressed data is stored in Couchbase (base64 encoded)
5. Archive state changes to `idle`
6. Original files are deleted from the database
7. Archive is ready for download

## API Endpoints

### Files

#### Create File
```bash
POST /files
Content-Type: application/json

{
  "filename": "document.pdf",
  "size": 1024000,
  "content_type": "application/pdf"
}
```

#### Get File
```bash
GET /files/{file_id}
```

#### List Files
```bash
GET /files?limit=50&offset=0
```

### Archives

#### Create Archive (triggers compression workflow)
```bash
POST /archives
Content-Type: application/json

{
  "name": "my-archive",
  "file_ids": [
    "uuid-of-file-1",
    "uuid-of-file-2"
  ]
}
```

#### Get Archive
```bash
GET /archives/{archive_id}
```

#### List Archives
```bash
GET /archives?limit=50&offset=0
```

#### Download Archive
```bash
GET /archives/{archive_id}/download
```
Returns a ZIP file when archive is in `idle` state.

### Health Check
```bash
GET /health
```

## Quick Start

The API is already running at `http://localhost:3030`

### Test the API

1. Create some files:
```bash
# Create first file
curl -X POST http://localhost:3030/files \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "document1.txt",
    "size": 1024,
    "content_type": "text/plain"
  }'

# Create second file
curl -X POST http://localhost:3030/files \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "document2.txt",
    "size": 2048,
    "content_type": "text/plain"
  }'
```

2. List files to get their IDs:
```bash
curl http://localhost:3030/files
```

3. Create an archive with the file IDs:
```bash
curl -X POST http://localhost:3030/archives \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-documents",
    "file_ids": ["<file-id-1>", "<file-id-2>"]
  }'
```

4. Check archive status (wait for compression to complete):
```bash
curl http://localhost:3030/archives/<archive-id>
```

5. Download the archive when state is `idle`:
```bash
curl http://localhost:3030/archives/<archive-id>/download -o archive.zip
```

## Services

- **API**: `http://localhost:3030`
- **Couchbase**: Running in container
- **Temporal**: Running in container
- **Temporal UI**: `http://localhost:8080` (if configured)

## Development

### View Logs
```bash
# Using MCP tool
__polytope__get_container_logs(container: compression-api, limit: 50)

# Or directly
docker logs <container-id>
```

### Check Service Status
```bash
curl http://localhost:3030/health
```

## Project Structure

```
modules/compression-api/
├── src/backend/
│   ├── couchbase/collections/
│   │   ├── files.py          # Files collection model
│   │   └── archives.py       # Archives collection model
│   ├── workflows/
│   │   ├── compression_workflows.py  # Temporal workflows
│   │   └── __init__.py               # Workflow registry
│   ├── routes/
│   │   └── base.py           # API routes
│   └── conf.py               # Configuration
└── polytope.yml              # Service configuration
```

## Implementation Details

### State Management
All state transitions are managed by Temporal workflows, ensuring:
- Reliability through automatic retries
- Visibility into workflow execution
- Durability of state changes
- Error handling and recovery

### Data Storage
- Files metadata stored in Couchbase `files` collection
- Archives metadata and compressed data stored in Couchbase `archives` collection
- Compressed data is base64-encoded for storage

### Compression
Files are compressed into ZIP format using Python's `zipfile` module. The current implementation creates placeholder content, but can be extended to:
- Accept file uploads via multipart/form-data
- Store files in object storage (S3, GCS, etc.)
- Stream large files for compression
