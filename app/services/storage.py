import boto3
from botocore.exceptions import ClientError

from app.config import settings


def get_r2_client():
    """Create and return an S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key,
        aws_secret_access_key=settings.r2_secret_key,
    )


def generate_r2_key(playlist_id: str, track_id: str) -> str:
    """Generate the R2 object key for a track.

    Format: audio/{playlist_id}/{track_id}.mp3
    """
    return f"audio/{playlist_id}/{track_id}.mp3"


def get_public_url(r2_key: str) -> str:
    """Generate public URL for an R2 object.

    Uses the R2.dev subdomain for public access.
    """
    # R2 public URL format: https://{bucket}.{account_id}.r2.dev/{key}
    # Or use custom domain if configured
    return f"{settings.r2_endpoint}/{settings.r2_bucket}/{r2_key}"


async def upload_file(
    local_path: str,
    playlist_id: str,
    track_id: str
) -> tuple[str, str] | None:
    """Upload a file to R2.

    Args:
        local_path: Path to the local file
        playlist_id: YouTube playlist ID
        track_id: YouTube video ID

    Returns:
        Tuple of (r2_key, public_url) or None if upload failed
    """
    r2_key = generate_r2_key(playlist_id, track_id)

    try:
        client = get_r2_client()
        client.upload_file(
            local_path,
            settings.r2_bucket,
            r2_key,
            ExtraArgs={"ContentType": "audio/mpeg"}
        )

        public_url = get_public_url(r2_key)
        return r2_key, public_url

    except ClientError:
        return None


async def delete_file(r2_key: str) -> bool:
    """Delete a file from R2.

    Args:
        r2_key: The R2 object key to delete

    Returns:
        True if deletion succeeded, False otherwise
    """
    try:
        client = get_r2_client()
        client.delete_object(
            Bucket=settings.r2_bucket,
            Key=r2_key
        )
        return True

    except ClientError:
        return False
