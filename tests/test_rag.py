from app.rag import ChromaRAGRetriever


def test_csv_examples_are_retrieved():
    retriever = ChromaRAGRetriever("data/spider_text_sql.csv", persist_directory="data/test-chroma")
    results = retriever.retrieve("Which heads are older than 56?", top_k=3)
    assert results
    assert "FROM head" in results[0]["sql_command"]