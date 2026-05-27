import asyncio
import functools
import io
import json
import uuid


class StorageService:
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    MAX_SIZE_BYTES = 5 * 1024 * 1024
    _EXT: dict[str, str] = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        public_url: str,
    ) -> None:
        try:
            from minio import Minio
        except ImportError as exc:
            raise RuntimeError(
                "Le package 'minio' est requis pour l'upload d'images. "
                "Reconstruisez le container : docker-compose up --build service-recipe"
            ) from exc
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
        self._bucket = bucket
        self._public_url = public_url.rstrip("/")

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

    async def ensure_bucket(self) -> None:
        exists = await self._run(self._client.bucket_exists, self._bucket)
        if not exists:
            await self._run(self._client.make_bucket, self._bucket)
            policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self._bucket}/*"],
                }],
            }
            await self._run(self._client.set_bucket_policy, self._bucket, json.dumps(policy))

    async def upload_image(self, data: bytes, content_type: str) -> str:
        if content_type not in self.ALLOWED_TYPES:
            raise ValueError(f"Type de fichier non supporté : {content_type}")
        if len(data) > self.MAX_SIZE_BYTES:
            raise ValueError("L'image ne doit pas dépasser 5 Mo.")

        await self.ensure_bucket()

        filename = f"{uuid.uuid4()}.{self._EXT[content_type]}"
        await self._run(
            self._client.put_object,
            self._bucket,
            filename,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return f"{self._public_url}/{self._bucket}/{filename}"
