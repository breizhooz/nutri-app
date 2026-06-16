import asyncio
import functools
import uuid

from app.core.exceptions import ImageTooLarge, UnsupportedImageType

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - boto3 fourni par requirements.txt
    boto3 = None  # type: ignore[assignment]
    Config = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment,misc]


class StorageService:
    """Stockage d'images via une API S3 (SeaweedFS).

    Client S3 générique (boto3) : ne dépend d'aucun produit serveur précis. La
    lecture publique des objets est assurée par l'identité « anonymous » déclarée
    côté serveur (infra/seaweedfs/entrypoint.sh) — il n'y a donc plus de bucket
    policy posée par l'application.
    """

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
        if boto3 is None:
            raise RuntimeError(
                "Le package 'boto3' est requis pour l'upload d'images. "
                "Reconstruisez le container : docker-compose up --build service-recipe"
            )
        endpoint_url = endpoint if "://" in endpoint else f"http://{endpoint}"
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            # path-style obligatoire (SeaweedFS/MinIO n'ont pas de vhost-bucket DNS).
            config=Config(
                signature_version="s3v4", s3={"addressing_style": "path"}
            ),
        )
        self._bucket = bucket
        self._public_url = public_url.rstrip("/")

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

    def _bucket_exists(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return True
        except ClientError:
            return False

    async def ensure_bucket(self) -> None:
        exists = await self._run(self._bucket_exists)
        if not exists:
            await self._run(self._client.create_bucket, Bucket=self._bucket)
        # Lecture publique : gérée côté serveur via l'identité « anonymous »
        # (Read:<bucket>), pas par une bucket policy applicative.

    async def upload_image(self, data: bytes, content_type: str) -> str:
        if content_type not in self.ALLOWED_TYPES:
            raise UnsupportedImageType(content_type)
        if len(data) > self.MAX_SIZE_BYTES:
            raise ImageTooLarge()

        await self.ensure_bucket()

        filename = f"{uuid.uuid4()}.{self._EXT[content_type]}"
        await self._run(
            self._client.put_object,
            Bucket=self._bucket,
            Key=filename,
            Body=data,
            ContentType=content_type,
        )
        return f"{self._public_url}/{self._bucket}/{filename}"
