import { useState, useEffect } from "react";
import { Button } from "~/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "~/components/ui/card";
import { Input } from "~/components/ui/input";
import { Badge } from "~/components/ui/badge";
import { Checkbox } from "~/components/ui/checkbox";
import { toast } from "sonner";
import { FileIcon, ArchiveIcon, DownloadIcon, Trash2Icon, PackageIcon } from "lucide-react";

const API_BASE_URL = "http://localhost:3030";

// Required loader function for React Router v7
export async function loader() {
  return null;
}

interface File {
  id: string;
  filename: string;
  size: number;
  content_type: string;
  state: string;
  archive_id: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

interface Archive {
  id: string;
  name: string;
  file_ids: string[];
  state: string;
  size: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export default function HomePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [archives, setArchives] = useState<Archive[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [archiveName, setArchiveName] = useState("");
  const [loading, setLoading] = useState(false);

  // Fetch files and archives
  const fetchData = async () => {
    try {
      const [filesRes, archivesRes] = await Promise.all([
        fetch(`${API_BASE_URL}/files`),
        fetch(`${API_BASE_URL}/archives`)
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
      console.error("Error fetching data:", error);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 2000); // Refresh every 2 seconds
    return () => clearInterval(interval);
  }, []);

  // Create a new file
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          size: file.size,
          content_type: file.type || "application/octet-stream",
        }),
      });

      if (response.ok) {
        toast.success(`File "${file.name}" added successfully`);
        fetchData();
      } else {
        toast.error("Failed to add file");
      }
    } catch (error) {
      toast.error("Error adding file");
    } finally {
      setLoading(false);
    }
  };

  // Create archive from selected files
  const handleCreateArchive = async () => {
    if (selectedFiles.size === 0) {
      toast.error("Please select at least one file");
      return;
    }

    if (!archiveName.trim()) {
      toast.error("Please enter an archive name");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/archives`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: archiveName,
          file_ids: Array.from(selectedFiles),
        }),
      });

      if (response.ok) {
        toast.success("Archive created! Compression in progress...");
        setSelectedFiles(new Set());
        setArchiveName("");
        fetchData();
      } else {
        toast.error("Failed to create archive");
      }
    } catch (error) {
      toast.error("Error creating archive");
    } finally {
      setLoading(false);
    }
  };

  // Download archive
  const handleDownload = async (archive: Archive) => {
    if (archive.state !== "idle") {
      toast.error(`Archive is not ready (current state: ${archive.state})`);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/archives/${archive.id}/download`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${archive.name}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        toast.success("Archive downloaded successfully");
      } else {
        toast.error("Failed to download archive");
      }
    } catch (error) {
      toast.error("Error downloading archive");
    }
  };

  // Toggle file selection
  const toggleFileSelection = (fileId: string) => {
    const newSelection = new Set(selectedFiles);
    if (newSelection.has(fileId)) {
      newSelection.delete(fileId);
    } else {
      newSelection.add(fileId);
    }
    setSelectedFiles(newSelection);
  };

  // Get state badge variant
  const getStateBadgeVariant = (state: string) => {
    switch (state) {
      case "idle":
      case "uploading":
        return "default";
      case "compressing":
      case "archiving":
        return "secondary";
      case "queued":
        return "outline";
      case "downloading":
      case "deleting":
        return "secondary";
      case "failed":
        return "destructive";
      default:
        return "outline";
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto p-6 max-w-7xl">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-foreground mb-2">File Compression App</h1>
          <p className="text-muted-foreground">
            Upload files, create archives, and download compressed files
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Files Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileIcon className="h-5 w-5" />
                Files ({files.length})
              </CardTitle>
              <CardDescription>Upload and manage your files</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Input
                  type="file"
                  onChange={handleFileUpload}
                  disabled={loading}
                  className="cursor-pointer"
                />
              </div>

              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                {files.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">
                    No files yet. Upload a file to get started.
                  </p>
                ) : (
                  files.map((file) => (
                    <div
                      key={file.id}
                      className="flex items-center gap-3 p-3 border border-border rounded-lg hover:bg-accent/50 transition-colors"
                    >
                      <Checkbox
                        checked={selectedFiles.has(file.id)}
                        onCheckedChange={() => toggleFileSelection(file.id)}
                        disabled={file.state !== "uploading"}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-foreground truncate">
                          {file.filename}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {formatFileSize(file.size)}
                        </p>
                      </div>
                      <Badge variant={getStateBadgeVariant(file.state)}>
                        {file.state}
                      </Badge>
                    </div>
                  ))
                )}
              </div>

              {files.filter(f => f.state === "uploading").length > 0 && (
                <div className="pt-4 border-t border-border">
                  <div className="flex gap-2 mb-2">
                    <Input
                      placeholder="Archive name"
                      value={archiveName}
                      onChange={(e) => setArchiveName(e.target.value)}
                      disabled={loading || selectedFiles.size === 0}
                    />
                  </div>
                  <Button
                    onClick={handleCreateArchive}
                    disabled={loading || selectedFiles.size === 0 || !archiveName.trim()}
                    className="w-full"
                  >
                    <PackageIcon className="h-4 w-4 mr-2" />
                    Create Archive ({selectedFiles.size} files)
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Archives Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ArchiveIcon className="h-5 w-5" />
                Archives ({archives.length})
              </CardTitle>
              <CardDescription>Your compressed archives</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {archives.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">
                    No archives yet. Create an archive from your files.
                  </p>
                ) : (
                  archives.map((archive) => (
                    <div
                      key={archive.id}
                      className="p-4 border border-border rounded-lg hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <p className="font-medium text-foreground">
                            {archive.name}.zip
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {archive.file_ids.length} files
                            {archive.size && ` • ${formatFileSize(archive.size)}`}
                          </p>
                        </div>
                        <Badge variant={getStateBadgeVariant(archive.state)}>
                          {archive.state}
                        </Badge>
                      </div>
                      
                      {archive.error_message && (
                        <p className="text-sm text-destructive mb-2">
                          Error: {archive.error_message}
                        </p>
                      )}

                      {archive.state === "idle" && (
                        <Button
                          onClick={() => handleDownload(archive)}
                          size="sm"
                          className="w-full mt-2"
                        >
                          <DownloadIcon className="h-4 w-4 mr-2" />
                          Download
                        </Button>
                      )}

                      {archive.state === "compressing" && (
                        <div className="mt-2 text-sm text-muted-foreground">
                          Compressing files...
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
