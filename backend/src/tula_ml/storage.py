from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import shutil

from .config import AppConfig

class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, key: str) -> Path:
        return (self.root / key).resolve()

    def reserve_upload_key(self, upload_id: str, filename: str) -> str:
        suffix = Path(filename).suffix or ".bin"
        return f"uploads/{upload_id}/source{suffix}"

    def put_bytes(self, key: str, data: bytes) -> Path:
        path = self.resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def put_json(self, key: str, payload: Any) -> Path:
        path = self.resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read_json(self, key: str) -> Any:
        return json.loads(self.resolve(key).read_text(encoding="utf-8"))

    def copy_from(self, source_path: Path, destination_key: str) -> Path:
        destination = self.resolve(destination_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        return destination

    def delete_key(self, key: str) -> None:
        path = self.resolve(key)
        if path.exists():
            path.unlink()

    def delete_prefix(self, prefix: str) -> None:
        path = self.resolve(prefix)
        if path.exists():
            shutil.rmtree(path)

    def healthcheck(self) -> dict[str, object]:
        return {"backend": "local", "root": str(self.root), "reachable": self.root.exists()}


class S3ObjectStore:
    def __init__(
        self,
        *,
        cache_root: Path,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        try:
            import boto3  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("boto3 is required for the s3 object store backend") from exc
        self.root = cache_root
        self.root.mkdir(parents=True, exist_ok=True)
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def _full_key(self, key: str) -> str:
        return f"{self.prefix}/{key}".strip("/") if self.prefix else key

    def resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._client.download_file(self.bucket, self._full_key(key), str(path))
        except Exception as exc:  # pragma: no cover - networked backend
            raise FileNotFoundError(f"Unable to resolve object from s3: {key}") from exc
        return path

    def reserve_upload_key(self, upload_id: str, filename: str) -> str:
        suffix = Path(filename).suffix or ".bin"
        return f"uploads/{upload_id}/source{suffix}"

    def put_bytes(self, key: str, data: bytes) -> Path:
        path = (self.root / key).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._client.put_object(Bucket=self.bucket, Key=self._full_key(key), Body=data)
        return path

    def put_json(self, key: str, payload: Any) -> Path:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self.put_bytes(key, encoded)

    def read_json(self, key: str) -> Any:
        return json.loads(self.resolve(key).read_text(encoding="utf-8"))

    def copy_from(self, source_path: Path, destination_key: str) -> Path:
        destination = (self.root / destination_key).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        self._client.upload_file(str(destination), self.bucket, self._full_key(destination_key))
        return destination

    def delete_key(self, key: str) -> None:
        path = (self.root / key).resolve()
        if path.exists():
            path.unlink()
        self._client.delete_object(Bucket=self.bucket, Key=self._full_key(key))

    def delete_prefix(self, prefix: str) -> None:
        path = (self.root / prefix).resolve()
        if path.exists():
            shutil.rmtree(path)
        full_prefix = self._full_key(prefix)
        response = self._client.list_objects_v2(Bucket=self.bucket, Prefix=full_prefix)
        objects = response.get("Contents") or []
        if objects:
            self._client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": item["Key"]} for item in objects]},
            )

    def healthcheck(self) -> dict[str, object]:
        self._client.list_objects_v2(Bucket=self.bucket, Prefix=self._full_key(""), MaxKeys=1)
        return {"backend": "s3", "bucket": self.bucket, "prefix": self.prefix, "reachable": True}


def build_object_store(config: AppConfig):
    if config.object_store_backend == "s3":
        if not config.s3_bucket:
            raise RuntimeError("TULA_S3_BUCKET is required when TULA_OBJECT_STORE_BACKEND=s3")
        return S3ObjectStore(
            cache_root=config.runtime_dir / "storage-cache",
            bucket=config.s3_bucket,
            prefix=config.s3_prefix,
            endpoint_url=config.s3_endpoint_url,
            region_name=config.s3_region,
            access_key_id=config.s3_access_key_id,
            secret_access_key=config.s3_secret_access_key,
        )
    return LocalObjectStore(config.runtime_dir / "storage")
