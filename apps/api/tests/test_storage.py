import os
import tempfile
import pytest
from fastapi import HTTPException
from app.services.storage import StorageService


class TestStorageService:
    @pytest.fixture
    def temp_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StorageService(base_dir=tmpdir)
            yield service

    def test_sanitize_filename_basic(self, temp_storage: StorageService):
        assert temp_storage.sanitize_filename("my_model.stl") == "my_model.stl"
        assert temp_storage.sanitize_filename("model with spaces.obj") == "model_with_spaces.obj"

    def test_sanitize_filename_path_traversal(self, temp_storage: StorageService):
        traversal = "../../etc/passwd.stl"
        sanitized = temp_storage.sanitize_filename(traversal)
        assert "/" not in sanitized
        assert "\\" not in sanitized
        assert ".." not in sanitized
        assert sanitized == "passwd.stl"

    def test_validate_extension_valid(self, temp_storage: StorageService):
        assert temp_storage.validate_extension("model.STL") == "stl"
        assert temp_storage.validate_extension("sculpture.obj") == "obj"
        assert temp_storage.validate_extension("asset.glb") == "glb"
        assert temp_storage.validate_extension("scene.gltf") == "gltf"

    def test_validate_extension_invalid(self, temp_storage: StorageService):
        with pytest.raises(HTTPException) as exc:
            temp_storage.validate_extension("script.py")
        assert exc.value.status_code == 400

        with pytest.raises(HTTPException) as exc:
            temp_storage.validate_extension("executable.exe")
        assert exc.value.status_code == 400

    def test_validate_file_size(self, temp_storage: StorageService):
        # 10MB is valid
        temp_storage.validate_file_size(10 * 1024 * 1024)

        # 101MB raises 413
        with pytest.raises(HTTPException) as exc:
            temp_storage.validate_file_size(101 * 1024 * 1024)
        assert exc.value.status_code == 413

    def test_save_original_and_resolve(self, temp_storage: StorageService):
        data = b"solid test\nendsolid test\n"
        dest_path, rel_path, clean_name, size = temp_storage.save_original(data, "test_cube.stl")

        assert dest_path.exists()
        assert clean_name == "test_cube.stl"
        assert size == len(data)
        assert rel_path.startswith("original/")

        resolved = temp_storage.resolve_path(rel_path)
        assert resolved == dest_path

    def test_path_traversal_detection(self, temp_storage: StorageService):
        outside_path = temp_storage.base_dir.parent / "outside.txt"
        with pytest.raises(HTTPException) as exc:
            temp_storage.validate_safe_path(outside_path)
        assert exc.value.status_code == 403
