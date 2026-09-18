import csv
import hashlib
import math
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class HashEmbeddingFunction:
    """Deterministic local embeddings for Chroma development and tests.

    Replace with a managed Gemini embedding function in production while
    keeping the Chroma collection and retriever contract unchanged.
    """

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def name(self) -> str:
        return "queryguard-hash-embedding-v1"

    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors = []
        for text in input:
            vector = [0.0] * self.dimensions
            for token in text.lower().split():
                index = int(hashlib.sha256(token.encode()).hexdigest(), 16) % self.dimensions
                vector[index] += 1.0
            magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / magnitude for value in vector])
        return vectors


class ChromaRAGRetriever:
    """Indexes approved text-to-SQL pairs in a persistent Chroma collection."""

    def __init__(self, csv_path: str, persist_directory: str = "data/chroma", collection_name: str = "text2sql_examples", chunk_size: int = 800, chunk_overlap: int = 120):
        import chromadb

        self.csv_path = Path(csv_path)
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=HashEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )
        self._index_csv()

    def _read_examples(self) -> list[dict[str, str]]:
        if not self.csv_path.exists():
            return []
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            return [
                {"text_query": row["text_query"].strip(), "sql_command": row["sql_command"].strip()}
                for row in csv.DictReader(file)
                if row.get("text_query") and row.get("sql_command")
            ]

    def _index_csv(self) -> None:
        examples = self._read_examples()
        if not examples:
            return
        documents: list[Document] = []
        for item in examples:
            source = f"Question: {item['text_query']}\nSQL: {item['sql_command']}"
            documents.extend(self.splitter.create_documents([source], metadatas=[{"sql_command": item["sql_command"]}]))
        ids = [hashlib.sha256(f"{self.csv_path}:{index}:{document.page_content}".encode()).hexdigest() for index, document in enumerate(documents)]
        self.collection.upsert(
            ids=ids,
            documents=[document.page_content for document in documents],
            metadatas=[document.metadata for document in documents],
        )

    def retrieve(self, question: str, top_k: int = 5) -> list[dict[str, Any]]:
        result = self.collection.query(query_texts=[question], n_results=top_k)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        return [
            {"text_query": document, "sql_command": metadata["sql_command"]}
            for document, metadata in zip(documents, metadatas)
        ]
