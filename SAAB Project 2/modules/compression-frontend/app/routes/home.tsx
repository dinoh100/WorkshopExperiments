import { useState, useEffect } from "react";
import { Upload, FileArchive, Download, Clock, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Button } from "~/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "~/components/ui/card";
import { Badge } from "~/components/ui/badge";
import { Separator } from "~/components/ui/separator";
import { toast } from "sonner";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:3030";

interface FileMetadata {
  id: string;
  filename: string;
  size: number;
  content_type: string | null;
  uploaded_at: string;
  archive_id: string | null;
  state: string;
}

interface ArchiveMetadata {
  id: string;
  state: string;
  file_ids: string[];
  total_size: number;
  created_at: string;
  completed_at: string | null;
}

export default function HomePage() {
  const [files, setFiles] = useState<FileMetadata[]>([]);
  const [archives, setArchives] = useState<ArchiveMetadata[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [filesRes, archivesRes] = await Promise.all([
        fetch(`${API_BASE_URL}/files`),
        fetch(`${API_BASE_URL}/archives`),
      ]);
      
      if (filesRes.ok) {
        const filesData = await filesRes.json();
        setFiles(filesData);
      }
      
      if (archivesRes.ok) {
        const archivesData = await archivesRes.json();
        setArchives(archivesData);
      }
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files));
    }
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      toast.error("Please select files to upload");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append("files", file);
    });

    try {
      const response = await fetch(`${API_BASE_URL}/files`, {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        toast.success(`Files uploaded successfully! Archive ID: ${data.archive_id}`);
        setSelectedFiles([]);
        loadData();
      } else {
        toast.error("Failed to upload files");
      }
    } catch (error) {
      toast.error("Error uploading files");
      console.error(error);
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (archiveId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/archives/${archiveId}/download`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `archive-${archiveId}.tar.gz`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        toast.success("Archive downloaded successfully!");
      } else {
        toast.error("Failed to download archive");
      }
    } catch (error) {
      toast.error("Error downloading archive");
      console.error(error);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + " " + sizes[i];
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getStateIcon = (state: string) => {
    switch (state) {
      case "completed":
      case "archived":
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case "processing":
        return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-600" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStateBadge = (state: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      completed: "default",
      archived: "default",
      processing: "secondary",
      pending: "outline",
      uploaded: "outline",
      failed: "destructive",
    };
    return (
      <Badge variant={variants[state] || "outline"} className="gap-1">
        {getStateIcon(state)}
        {state}
      </Badge>
    );
  };

  return (
    <div className="container mx-auto py-8 px-4 max-w-7xl">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2 text-foreground">File Compression Service</h1>
        <p className="text-muted-foreground">
          Upload files to create compressed archives
        </p>
      </div>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Upload Files
          </CardTitle>
          <CardDescription>
            Select one or more files to upload and compress into an archive
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <input
              type="file"
              multiple
              onChange={handleFileSelect}
              className="block w-full text-sm text-foreground
                file:mr-4 file:py-2 file:px-4
                file:rounded-md file:border-0
                file:text-sm file:font-semibold
                file:bg-primary file:text-primary-foreground
                hover:file:bg-primary/90
                cursor-pointer"
            />
          </div>
          
          {selectedFiles.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">Selected files:</p>
              <div className="bg-muted rounded-md p-3 space-y-1">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="text-sm text-muted-foreground flex justify-between">
                    <span>{file.name}</span>
                    <span>{formatBytes(file.size)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <Button
            onClick={handleUpload}
            disabled={uploading || selectedFiles.length === 0}
            className="w-full"
          >
            {uploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Upload and Compress
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      <div className="grid md:grid-cols-2 gap-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileArchive className="h-5 w-5" />
              Archives ({archives.length})
            </CardTitle>
            <CardDescription>
              Compressed archives ready for download
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : archives.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No archives yet. Upload some files to get started!
              </p>
            ) : (
              <div className="space-y-4">
                {archives.map((archive) => (
                  <div key={archive.id} className="border border-border rounded-lg p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <p className="font-mono text-xs text-muted-foreground mb-1">
                          {archive.id}
                        </p>
                        {getStateBadge(archive.state)}
                      </div>
                    </div>
                    <Separator className="my-2" />
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Files:</span>
                        <span className="text-foreground">{archive.file_ids.length}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Size:</span>
                        <span className="text-foreground">{formatBytes(archive.total_size)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Created:</span>
                        <span className="text-foreground">{formatDate(archive.created_at)}</span>
                      </div>
                      {archive.completed_at && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Completed:</span>
                          <span className="text-foreground">{formatDate(archive.completed_at)}</span>
                        </div>
                      )}
                    </div>
                    {archive.state === "completed" && (
                      <Button
                        onClick={() => handleDownload(archive.id)}
                        className="w-full mt-3"
                        variant="default"
                      >
                        <Download className="mr-2 h-4 w-4" />
                        Download Archive
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Files ({files.length})</CardTitle>
            <CardDescription>
              All uploaded files and their status
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : files.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No files uploaded yet
              </p>
            ) : (
              <div className="space-y-3">
                {files.map((file) => (
                  <div key={file.id} className="border border-border rounded-lg p-3">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm text-foreground truncate">
                          {file.filename}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatBytes(file.size)}
                        </p>
                      </div>
                      {getStateBadge(file.state)}
                    </div>
                    <Separator className="my-2" />
                    <div className="text-xs space-y-1">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Uploaded:</span>
                        <span className="text-foreground">{formatDate(file.uploaded_at)}</span>
                      </div>
                      {file.archive_id && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Archive:</span>
                          <span className="font-mono text-foreground text-[10px]">
                            {file.archive_id.slice(0, 8)}...
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
