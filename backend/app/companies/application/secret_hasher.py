from dataclasses import dataclass
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
from secrets import randbelow, token_hex, token_urlsafe


@dataclass(frozen=True, slots=True)
class HashedSecret:
    secret_hash: str
    secret_salt: str


class SecretHasher:
    _iterations = 200_000

    def generate_enrollment_code(self) -> str:
        return token_urlsafe(12)

    def generate_numeric_code(self, *, digits: int = 6) -> str:
        upper_bound = 10**digits
        return f"{randbelow(upper_bound):0{digits}d}"

    def digest_secret(self, secret: str) -> str:
        return sha256(secret.strip().encode()).hexdigest()

    def hash_secret(self, secret: str, secret_salt: str | None = None) -> HashedSecret:
        salt = secret_salt or token_hex(16)
        digest = pbkdf2_hmac(
            "sha256",
            secret.strip().encode(),
            salt.encode(),
            self._iterations,
        ).hex()
        return HashedSecret(secret_hash=digest, secret_salt=salt)

    def verify(self, secret: str, *, expected_hash: str, secret_salt: str) -> bool:
        hashed_secret = self.hash_secret(secret, secret_salt)
        return compare_digest(hashed_secret.secret_hash, expected_hash)

