import ipaddress
import imghdr
from urllib.parse import urlparse

PRIVATE_IP_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
]

ALLOWED_IMAGE_TYPES = {'png', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        try:
            ip = ipaddress.ip_address(hostname)
            for private_range in PRIVATE_IP_RANGES:
                if ip in private_range:
                    return False
        except ValueError:
            pass

        return True
    except Exception:
        return False


def validate_image_format(image_bytes: bytes) -> bool:
    img_type = imghdr.what(None, h=image_bytes)
    return img_type in ALLOWED_IMAGE_TYPES
