from utils.network import is_public_url

ALLOWED_IMAGE_TYPES = {'png', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024

_IMAGE_SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': 'png',
    b'\xff\xd8\xff': 'jpeg',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'RIFF': 'webp',
}


def is_safe_url(url: str) -> bool:
    return is_public_url(url)


def detect_image_type(image_bytes: bytes) -> str | None:
    if len(image_bytes) < 12:
        return None
    for sig, fmt in _IMAGE_SIGNATURES.items():
        if image_bytes.startswith(sig):
            if fmt == 'webp':
                return fmt if b'WEBP' in image_bytes[8:12] else None
            return fmt if fmt in ALLOWED_IMAGE_TYPES else None
    return None


def validate_image_format(image_bytes: bytes) -> bool:
    return detect_image_type(image_bytes) is not None
