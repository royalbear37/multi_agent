"""No dotenv loading or shared LLM settings. Secrets are runtime-only."""
from dataclasses import dataclass, field
import math
import os
import re
from urllib.parse import urlsplit

from .contracts import A2AError

PROFILE = 'a2a-1.0-jsonrpc'


@dataclass(frozen=True)
class A2AConfig:
    endpoint: str = field(default='', repr=False)
    protocol_profile: str = PROFILE
    api_key: str = field(default='', repr=False)
    version_header: str | None = 'A2A-Version'
    protocol_version: str = '1.0'
    connect_timeout: float = 5.0
    read_timeout: float = 30.0
    deadline_seconds: float = 45.0
    max_response_bytes: int = 1_048_576

    @classmethod
    def from_env(cls, *, credentials: bool = True):
        # Do not include invalid values in errors (they may contain secrets).
        try:
            return cls(endpoint=os.getenv('ITRI_A2A_ENDPOINT', ''),
                       protocol_profile=os.getenv('ITRI_A2A_PROTOCOL_PROFILE', PROFILE),
                       api_key=os.getenv('ITRI_A2A_API_KEY', '') if credentials else '',
                       version_header=os.getenv('ITRI_A2A_VERSION_HEADER', 'A2A-Version') or None,
                       protocol_version=os.getenv('ITRI_A2A_PROTOCOL_VERSION', '1.0'),
                       connect_timeout=float(os.getenv('ITRI_A2A_CONNECT_TIMEOUT_SECONDS', '5')),
                       read_timeout=float(os.getenv('ITRI_A2A_READ_TIMEOUT_SECONDS', '30')),
                       deadline_seconds=float(os.getenv('ITRI_A2A_TOTAL_DEADLINE_SECONDS', '45')),
                       max_response_bytes=int(os.getenv('ITRI_A2A_MAX_RESPONSE_BYTES', '1048576')))
        except (TypeError, ValueError):
            raise A2AError('INVALID_CONFIG') from None

    def check(self, *, authenticated: bool = True):
        if self.protocol_profile != PROFILE or self.protocol_version != '1.0':
            raise A2AError('UNSUPPORTED_PROTOCOL_VERSION')
        if authenticated and (not isinstance(self.api_key, str) or not self.api_key.strip()):
            raise A2AError('MISSING_API_KEY')
        # Treat the provider's credential as opaque. Validate safe header bytes,
        # not a guessed token alphabet; never trim or rewrite the credential.
        # Acceptance here is not proof of server authentication.
        if authenticated and not re.fullmatch(r'[\x21-\x7e]+', self.api_key):
            raise A2AError('INVALID_CREDENTIAL')
        try:
            url = urlsplit(self.endpoint)
            valid = (url.scheme == 'https' and url.hostname and not url.username and not url.password
                     and not url.query and not url.fragment and not any(c.isspace() for c in self.endpoint)
                     and (not self.api_key or self.api_key not in self.endpoint))
            _ = url.port
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise A2AError('INVALID_ENDPOINT')
        if self.version_header is not None and self.version_header.lower() != 'a2a-version':
            raise A2AError('INVALID_VERSION_HEADER')
        if any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0
               for n in (self.connect_timeout, self.read_timeout, self.deadline_seconds)):
            raise A2AError('INVALID_CONFIG')
        if type(self.max_response_bytes) is not int or not 1 <= self.max_response_bytes <= 10_485_760:
            raise A2AError('INVALID_CONFIG')
