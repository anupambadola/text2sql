import csv
import hashlib
import math
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class HashEmbeddingFunction:
    """Deterministic local embeddings for development and tests.

    Replace with a managed embedding function in production while keeping the
    retriever contract unchanged.
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


class LanceDBRAGRetriever:
    """Persistent local RAG store for examples and human SQL feedback."""

    def __init__(self, csv_path: str, persist_directory: str = "data/lancedb", collection_name: str = "text2sql_examples", chunk_size: int = 800, chunk_overlap: int = 120):
        import lancedb

        self.csv_path = Path(csv_path)
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.embedding = HashEmbeddingFunction()
        self.client = lancedb.connect(persist_directory)
        self.collection_name = collection_name
        self.table = self._open_table()
        self._index_csv()

    def _open_table(self):
        if self.collection_name in self.client.table_names():
            return self.client.open_table(self.collection_name)
        return self.client.create_table(self.collection_name, data=[self._row("seed", "", "", "example")])

    def _row(self, identifier: str, question: str, sql: str, source: str, note: str | None = None, correct: bool = False) -> dict[str, Any]:
        text = f"Question: {question}\nSQL: {sql}"
        return {
            "id": identifier,
            "vector": self.embedding([text])[0],
            "text_query": question,
            "sql_command": sql,
            "source": source,
            "note": note or "",
            "correct": correct,
        }

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
        self.table.delete("source = 'example'")
        documents: list[Document] = []
        for item in examples:
            source = f"Question: {item['text_query']}\nSQL: {item['sql_command']}"
            documents.extend(self.splitter.create_documents([source], metadatas=[{"sql_command": item["sql_command"]}]))
        rows = []
        for index, document in enumerate(documents):
            identifier = hashlib.sha256(f"{self.csv_path}:{index}:{document.page_content}".encode()).hexdigest()
            rows.append(self._row(identifier, document.page_content, document.metadata["sql_command"], "example"))
        self.table.add(rows)

    def retrieve(self, question: str, top_k: int = 5) -> list[dict[str, Any]]:
        matches = self.table.search(self.embedding([question])[0]).limit(top_k).to_list()
        return [
            {"text_query": match.get("text_query", ""), "sql_command": match.get("sql_command", ""), "source": match.get("source", "example"), "feedback_note": match.get("note", ""), "feedback_correct": match.get("correct")}
            for match in matches
            if match.get("id") != "seed" and match.get("sql_command") and not (match.get("source") == "feedback" and match.get("correct") is False)
        ]

    def record_feedback(self, query_id: str, question: str, sql: str, correct: bool, note: str | None = None) -> None:
        self.table.add([self._row(query_id, question, sql, "feedback", note, correct)])


ChromaRAGRetriever = LanceDBRAGRetriever
