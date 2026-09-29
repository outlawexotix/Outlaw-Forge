import os
import re
import uuid
from pathlib import Path
from typing import Optional, Set, Tuple, Union
from fastapi import HTTPException, status

from app.core.config import settings

ALLOWED_EXTENSIONS: Set[str] = {"stl", "obj", "glb", "gltf", "3mf"}
MAX_FILE_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB


class StorageService:
    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            configured_dir = Path(settings.STORAGE_BASE_DIR)
            if not configured_dir.is_absolute():
                # Walk up to find root containing 'apps' or 'packages'
                curr = Path(__file__).resolve().parent
                while curr.parent != curr:
                    if (curr / "apps").exists() and (curr / "packages").exists():
                        break
                    curr = curr.parent
                repo_root = curr
                self.base_dir = (repo_root / configured_dir).resolve()
            else:
                self.base_dir = configured_dir.resolve()

        self.original_dir = (self.base_dir / "original").resolve()
        self.working_dir = (self.base_dir / "working").resolve()
        self.exports_dir = (self.base_dir / "exports").resolve()

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create storage directories if they do not exist."""
        self.original_dir.mkdir(parents=True, exist_ok=True)
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent directory traversal and invalid filesystem characters.
        Strips leading/trailing whitespace, replaces slashes and non-standard characters.
        """
        if not filename:
            return f"model_{uuid.uuid4().hex[:8]}.stl"

        # Remove any path separators
        clean_name = os.path.basename(filename).strip()
        # Remove null bytes
        clean_name = clean_name.replace("\0", "")
        # Replace spaces and dangerous characters with underscores
        clean_name = re.sub(r"[^\w\.-]", "_", clean_name)
        # Prevent hidden files or double dots
        clean_name = re.sub(r"^\.+", "", clean_name)
        clean_name = re.sub(r"\.{2,}", ".", clean_name)

        if not clean_name:
            clean_name = f"model_{uuid.uuid4().hex[:8]}.stl"

        return clean_name

    @staticmethod
    def validate_extension(filename: str, allowed_extensions: Optional[Set[str]] = None) -> str:
        """
        Validate that the filename has an allowed 3D extension.
        Returns the normalized extension without dot.
        """
        allowed = allowed_extensions or ALLOWED_EXTENSIONS
        ext = Path(filename).suffix.lower().lstrip(".")
        if not ext or ext not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '.{ext}'. Supported formats: {', '.join(sorted(allowed))}",
            )
        return ext

    @staticmethod
    def validate_file_size(size_bytes: int, max_size: int = MAX_FILE_SIZE_BYTES) -> None:
        """Enforce maximum file upload size (100MB)."""
        if size_bytes > max_size:
            max_mb = max_size / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File size exceeds maximum allowed limit of {max_mb:.0f} MB.",
            )

    def validate_safe_path(self, target_path: Union[str, Path]) -> Path:
        """
        Ensure the resolved target path is strictly within the allowed base storage directory,
        preventing directory traversal vulnerabilities.
        """
        resolved = Path(target_path).resolve()
        try:
            resolved.relative_to(self.base_dir)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Path is outside the designated storage directory.",
            )
        return resolved

    def save_original(self, file_bytes: bytes, filename: str) -> Tuple[Path, str, str, int]:
        """
        Save an original uploaded model file immutably in data/original/<uuid>_<sanitized_name>.
        Returns: (absolute_path, relative_storage_path, sanitized_filename, file_size_bytes)
        """
        self._ensure_directories()
        self.validate_file_size(len(file_bytes))
        sanitized = self.sanitize_filename(filename)
        self.validate_extension(sanitized)

        file_uuid = uuid.uuid4().hex[:12]
        stored_name = f"{file_uuid}_{sanitized}"
        dest_path = (self.original_dir / stored_name).resolve()
        self.validate_safe_path(dest_path)

        with open(dest_path, "wb") as f:
            f.write(file_bytes)

        relative_path = f"original/{stored_name}"
        return dest_path, relative_path, sanitized, len(file_bytes)

    def save_working(self, file_bytes: bytes, filename: str) -> Tuple[Path, str]:
        """
        Save a working model file into data/working/<uuid>_<sanitized_name>.
        Returns: (absolute_path, relative_storage_path)
        """
        self._ensure_directories()
        sanitized = self.sanitize_filename(filename)
        file_uuid = uuid.uuid4().hex[:12]
        stored_name = f"{file_uuid}_{sanitized}"
        dest_path = (self.working_dir / stored_name).resolve()
        self.validate_safe_path(dest_path)

        with open(dest_path, "wb") as f:
            f.write(file_bytes)

        relative_path = f"working/{stored_name}"
        return dest_path, relative_path

    def save_export(self, file_bytes: bytes, filename: str) -> Tuple[Path, str]:
        """
        Save an exported model file into data/exports/<uuid>_<sanitized_name>.
        Returns: (absolute_path, relative_storage_path)
        """
        self._ensure_directories()
        sanitized = self.sanitize_filename(filename)
        file_uuid = uuid.uuid4().hex[:12]
        stored_name = f"{file_uuid}_{sanitized}"
        dest_path = (self.exports_dir / stored_name).resolve()
        self.validate_safe_path(dest_path)

        with open(dest_path, "wb") as f:
            f.write(file_bytes)

        relative_path = f"exports/{stored_name}"
        return dest_path, relative_path

    def resolve_path(self, storage_path: Union[str, Path]) -> Path:
        """
        Resolve a relative or absolute storage path to a validated absolute path.
        """
        path = Path(storage_path)
        if not path.is_absolute():
            resolved = (self.base_dir / path).resolve()
        else:
            resolved = path.resolve()

        return self.validate_safe_path(resolved)


# Singleton instance
storage_service = StorageService()
