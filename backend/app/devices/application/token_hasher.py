from dataclasses import dataclass
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from secrets import token_hex, token_urlsafe


@dataclass(frozen=True, slots=True)
class HashedToken:
    token_hash: str
    token_salt: str


class AgentTokenHasher:
    _iterations = 200_000

    def generate_token(self) -> str:
        return token_urlsafe(32)

    def hash_token(self, token: str, token_salt: str | None = None) -> HashedToken:
        salt = token_salt or token_hex(16)
        digest = pbkdf2_hmac(
            "sha256",
            token.encode(),
            salt.encode(),
            self._iterations,
        ).hex()
        return HashedToken(token_hash=digest, token_salt=salt)

    def verify(self, token: str, *, expected_hash: str, token_salt: str) -> bool:
        hashed_token = self.hash_token(token, token_salt)
        return compare_digest(hashed_token.token_hash, expected_hash)

