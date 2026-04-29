class RagforgeError(Exception):
    exit_code: int = 1


class ConfigError(RagforgeError):
    """Invalid or missing ragforge.yaml (exit 2)."""
    exit_code = 2


class APIError(RagforgeError):
    """Embedding / LLM / vector store unreachable (exit 3)."""
    exit_code = 3


class ValidationError(RagforgeError):
    """Incompatible params, e.g. chunk_size > model token limit (exit 4)."""
    exit_code = 4


class IndexNotFoundError(RagforgeError):
    """query/eval called before ingest (exit 5)."""
    exit_code = 5
