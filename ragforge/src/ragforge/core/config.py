from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, model_validator

from ragforge.core.exceptions import ConfigError, ValidationError

CONFIG_FILENAME = "ragforge.yaml"

_MODEL_TOKEN_LIMITS: dict[str, int] = {
    "openai/text-embedding-3-small": 8191,
    "openai/text-embedding-3-large": 8191,
    "openai/text-embedding-ada-002": 8191,
    "huggingface/BAAI/bge-small-en-v1.5": 512,
    "huggingface/BAAI/bge-large-en-v1.5": 512,
    "huggingface/sentence-transformers/all-MiniLM-L6-v2": 256,
    "cohere/embed-english-v3.0": 512,
}
_DEFAULT_TOKEN_LIMIT = 512


# --- sub-models ---

class ChunkingConfig(BaseModel):
    strategy: str = "semantic"
    chunk_size: int = 512
    overlap: int = 64


class EmbeddingConfig(BaseModel):
    model: str = "openai/text-embedding-3-small"


class IngestionConfig(BaseModel):
    sources: list[str] = ["./docs"]
    document_types: list[str] = ["pdf", "docx"]
    chunking: ChunkingConfig = ChunkingConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()


class VectorStoreConfig(BaseModel):
    provider: str = "chroma"
    host: str = "localhost"
    port: int = 8000
    collection: str = "ragforge"


class RetrievalConfig(BaseModel):
    strategy: str = "hybrid"
    top_k: int = 10
    reranker: Optional[str] = None


class GenerationConfig(BaseModel):
    model: str = "openai/gpt-4o-mini"
    citation_mode: str = "inline"
    max_tokens: int = 1024


class EvalThreshold(BaseModel):
    warning: float = 0.75
    critical: float = 0.60


class EvalThresholds(BaseModel):
    faithfulness: EvalThreshold = EvalThreshold(warning=0.75, critical=0.60)
    answer_relevance: EvalThreshold = EvalThreshold(warning=0.80, critical=0.65)


class EvalSynthetic(BaseModel):
    num_questions: int = 50


class EvalConfig(BaseModel):
    thresholds: EvalThresholds = EvalThresholds()
    synthetic: EvalSynthetic = EvalSynthetic()


class ObservabilityConfig(BaseModel):
    backend: str = "langfuse"
    host: str = "http://localhost:3000"


class DeploymentConfig(BaseModel):
    target: str = "local"


class ProjectConfig(BaseModel):
    name: str
    description: str = ""


# --- root model ---

class RagforgeConfig(BaseModel):
    project: ProjectConfig
    ingestion: IngestionConfig = IngestionConfig()
    vector_store: VectorStoreConfig = VectorStoreConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    generation: GenerationConfig = GenerationConfig()
    eval: EvalConfig = EvalConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    deployment: DeploymentConfig = DeploymentConfig()

    @model_validator(mode="after")
    def _validate_chunk_vs_token_limit(self) -> RagforgeConfig:
        model_key = self.ingestion.embedding.model
        limit = _MODEL_TOKEN_LIMITS.get(model_key, _DEFAULT_TOKEN_LIMIT)
        chunk_size = self.ingestion.chunking.chunk_size
        if chunk_size > limit:
            raise ValidationError(
                f"chunk_size={chunk_size} exceeds token limit={limit} "
                f"for embedding model '{model_key}'. "
                f"Reduce chunk_size or choose a model with a higher token ceiling."
            )
        return self

    # --- persistence ---

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / CONFIG_FILENAME
        data = self.model_dump()
        with path.open("w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        return path

    @classmethod
    def load(cls, path: Path) -> RagforgeConfig:
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
        try:
            with path.open() as f:
                data = yaml.safe_load(f)
            return cls.model_validate(data)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    @classmethod
    def from_wizard_answers(cls, answers: dict[str, Any]) -> RagforgeConfig:
        chunking_strategy = answers.get("chunking_strategy", "semantic")
        return cls(
            project=ProjectConfig(
                name=answers["project_name"],
                description=answers.get("project_description", ""),
            ),
            ingestion=IngestionConfig(
                sources=answers.get("sources", ["./docs"]),
                document_types=answers.get("document_types", ["pdf", "docx"]),
                chunking=ChunkingConfig(
                    strategy=chunking_strategy,
                    chunk_size=answers.get("chunk_size", 512),
                    overlap=answers.get("overlap", 64),
                ),
                embedding=EmbeddingConfig(
                    model=answers.get("embedding_model", "openai/text-embedding-3-small"),
                ),
            ),
            vector_store=VectorStoreConfig(
                provider=answers.get("vector_store_provider", "chroma"),
                host=answers.get("vector_store_host", "localhost"),
                port=int(answers.get("vector_store_port", 8000)),
                collection=answers.get("vector_store_collection", answers["project_name"]),
            ),
            retrieval=RetrievalConfig(
                strategy=answers.get("retrieval_strategy", "hybrid"),
                top_k=int(answers.get("top_k", 10)),
                reranker=answers.get("reranker") or None,
            ),
            generation=GenerationConfig(
                model=answers.get("llm_model", "openai/gpt-4o-mini"),
                citation_mode=answers.get("citation_mode", "inline"),
                max_tokens=int(answers.get("max_tokens", 1024)),
            ),
            eval=EvalConfig(
                thresholds=EvalThresholds(
                    faithfulness=EvalThreshold(
                        warning=answers.get("faithfulness_warning", 0.75),
                        critical=answers.get("faithfulness_critical", 0.60),
                    ),
                    answer_relevance=EvalThreshold(
                        warning=answers.get("answer_relevance_warning", 0.80),
                        critical=answers.get("answer_relevance_critical", 0.65),
                    ),
                ),
                synthetic=EvalSynthetic(
                    num_questions=int(answers.get("num_questions", 50)),
                ),
            ),
            observability=ObservabilityConfig(
                backend=answers.get("observability_backend", "langfuse"),
                host=answers.get("observability_host", "http://localhost:3000"),
            ),
            deployment=DeploymentConfig(
                target=answers.get("deployment_target", "local"),
            ),
        )
