"""PDF extraction, chunking, and ChromaDB vector ingestion module."""

from pathlib import Path
import hashlib
import sys
from typing import List, Dict, Any, Optional
import pypdf
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from config import settings, logger


class RecursiveCharacterTextSplitter:
    """Zero-dependency recursive text splitter with overlap."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
        separators: Optional[List[str]] = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def split_text(self, text: str) -> List[str]:
        """Recursively split text using hierarchy of separators."""
        text = text.strip()
        if not text:
            return []
        return self._split(text, self.separators)

    def _split(self, text: str, separators: List[str]) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        separator = separators[-1]
        remaining_separators: List[str] = []
        for i, sep in enumerate(separators):
            if sep == "" or sep in text:
                separator = sep
                remaining_separators = separators[i + 1 :]
                break

        splits = text.split(separator) if separator != "" else list(text)
        good_splits: List[str] = []
        current_doc: List[str] = []
        total_len = 0

        for s in splits:
            s_len = len(s) + (len(separator) if current_doc else 0)
            if total_len + s_len > self.chunk_size:
                if current_doc:
                    doc = separator.join(current_doc)
                    if doc.strip():
                        good_splits.append(doc.strip())
                    # Overlap handling
                    while current_doc and total_len > self.chunk_overlap:
                        popped = current_doc.pop(0)
                        total_len -= len(popped) + (len(separator) if current_doc else 0)
                current_doc = [s]
                total_len = len(s)
            else:
                current_doc.append(s)
                total_len += s_len

        if current_doc:
            doc = separator.join(current_doc)
            if doc.strip():
                good_splits.append(doc.strip())

        # If any split is still too large and we have more separators, recurse
        final_chunks: List[str] = []
        for chunk in good_splits:
            if len(chunk) > self.chunk_size and remaining_separators:
                final_chunks.extend(self._split(chunk, remaining_separators))
            else:
                final_chunks.append(chunk)

        return final_chunks


class PDFIngestor:
    """Extracts, chunks, embeds, and indexes trading PDF documents into ChromaDB."""

    def __init__(self) -> None:
        self.pdf_dir: Path = settings.resolved_pdf_dir
        self.knowledge_dir: Path = settings.resolved_knowledge_dir
        self.collection_name: str = settings.COLLECTION_NAME
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        self.client = self._init_chroma_client()
        self.collection = self._get_or_create_collection()

    def _init_chroma_client(self) -> chromadb.PersistentClient:
        """Initialize ChromaDB persistent client."""
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(
            path=str(self.knowledge_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _get_or_create_collection(self) -> chromadb.Collection:
        """Get or create ChromaDB collection using default or Gemini embedding function."""
        # Use default sentence-transformer embedding function built into ChromaDB
        ef = embedding_functions.DefaultEmbeddingFunction()
        return self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=ef,
            metadata={"description": "Proprietary trading modules and SOP knowledge base"},
        )

    @staticmethod
    def _determine_category(source_name: str) -> str:
        """Categorize trading documents for high-precision RAG filtering."""
        s = source_name.lower()
        if "nison" in s or "candlestick" in s or "star" in s or "hammer" in s or "3400e" in s:
            return "candlestick_sop"
        elif "smc" in s or "ict" in s or "mega" in s or "fibonacci" in s or "divergence" in s:
            return "smc_ict"
        elif "regime" in s or "adx" in s or "trend" in s or "timeframe" in s or "matrix" in s:
            return "trend_regime"
        elif "risiko" in s or "atr" in s or "news" in s or "calendar" in s:
            return "risk_atr"
        return "general_tech"

    def extract_from_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Extract text page by page from a PDF file preserving metadata."""
        documents: List[Dict[str, Any]] = []
        try:
            reader = pypdf.PdfReader(str(pdf_path))
            total_pages = len(reader.pages)
            logger.info("Extracting '%s' (%d pages)...", pdf_path.name, total_pages)

            cat = self._determine_category(pdf_path.name)
            for page_idx, page in enumerate(reader.pages, start=1):
                raw_text = page.extract_text() or ""
                cleaned_text = " ".join(raw_text.split())
                if len(cleaned_text) < 40:
                    continue  # Skip empty or negligible pages

                documents.append({
                    "text": cleaned_text,
                    "metadata": {
                        "source": pdf_path.name,
                        "file_path": str(pdf_path),
                        "page": page_idx,
                        "total_pages": total_pages,
                        "category": cat,
                    },
                })
        except Exception as exc:
            logger.error("Failed to read PDF '%s': %s", pdf_path.name, exc)

        return documents

    def extract_from_text(self, text_path: Path) -> List[Dict[str, Any]]:
        """Extract text from markdown or plain text file preserving metadata."""
        documents: List[Dict[str, Any]] = []
        try:
            with open(text_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                documents.append({
                    "text": content,
                    "metadata": {
                        "source": text_path.name,
                        "file_path": str(text_path),
                        "page": 1,
                        "total_pages": 1,
                        "category": self._determine_category(text_path.name),
                    },
                })
        except Exception as exc:
            logger.error("Failed to read text/md file '%s': %s", text_path.name, exc)
        return documents

    def extract_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract documents based on file extension."""
        if file_path.suffix.lower() == ".pdf":
            return self.extract_from_pdf(file_path)
        elif file_path.suffix.lower() in (".md", ".txt"):
            return self.extract_from_text(file_path)
        return []

    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chunk document texts and generate deterministic chunk IDs."""
        chunks: List[Dict[str, Any]] = []
        for doc in documents:
            sub_chunks = self.splitter.split_text(doc["text"])
            for sub_idx, chunk_text in enumerate(sub_chunks):
                # Deterministic hash ID based on filename, page, and chunk text
                unique_str = f"{doc['metadata']['source']}_p{doc['metadata']['page']}_c{sub_idx}_{chunk_text[:50]}"
                chunk_id = hashlib.sha256(unique_str.encode("utf-8")).hexdigest()[:16]

                meta = dict(doc["metadata"])
                meta["chunk_index"] = sub_idx
                meta["char_count"] = len(chunk_text)

                chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "metadata": meta,
                })
        return chunks

    def ingest_all(self, force_reindex: bool = False) -> Dict[str, int]:
        """Scan pdf_dir, extract, chunk, and incrementally index into ChromaDB."""
        if force_reindex:
            logger.warning("Force reindex requested. Resetting collection '%s'...", self.collection_name)
            self.client.delete_collection(self.collection_name)
            self.collection = self._get_or_create_collection()

        files_to_index = sorted(
            list(self.pdf_dir.glob("*.pdf")) +
            list(self.pdf_dir.glob("*.md")) +
            list(self.pdf_dir.glob("*.txt"))
        )
        if not files_to_index:
            logger.warning("No PDF/MD/TXT files found in '%s'", self.pdf_dir)
            return {"files_found": 0, "chunks_added": 0, "chunks_skipped": 0, "total_in_db": self.collection.count()}

        logger.info("Found %d document file(s) in '%s'", len(files_to_index), self.pdf_dir)

        # Retrieve existing IDs for incremental indexing
        existing_ids = set()
        try:
            existing_records = self.collection.get()
            if existing_records and "ids" in existing_records:
                existing_ids = set(existing_records["ids"])
            logger.info("Current vector store contains %d existing chunk(s).", len(existing_ids))
        except Exception as exc:
            logger.debug("Could not fetch existing IDs: %s", exc)

        total_added = 0
        total_skipped = 0

        for file_path in files_to_index:
            pages = self.extract_file(file_path)
            chunks = self.chunk_documents(pages)

            new_ids: List[str] = []
            new_texts: List[str] = []
            new_metadatas: List[Dict[str, Any]] = []

            if not chunks:
                logger.warning("No extractable text found in '%s' (file may be scanned/image-only). Skipping.", file_path.name)
                continue

            for chunk in chunks:
                if chunk["id"] in existing_ids:
                    total_skipped += 1
                else:
                    new_ids.append(chunk["id"])
                    new_texts.append(chunk["text"])
                    new_metadatas.append(chunk["metadata"])

            if new_ids:
                # Add in batches of 100 for memory and embedding efficiency
                batch_size = 100
                for i in range(0, len(new_ids), batch_size):
                    self.collection.add(
                        ids=new_ids[i : i + batch_size],
                        documents=new_texts[i : i + batch_size],
                        metadatas=new_metadatas[i : i + batch_size],
                    )
                existing_ids.update(new_ids)
                total_added += len(new_ids)
                logger.info("Indexed %d new chunk(s) from '%s'", len(new_ids), file_path.name)
            else:
                logger.info("All chunks for '%s' already indexed. Skipping.", file_path.name)

        final_count = self.collection.count()
        logger.info(
            "Ingestion finished. Added: %d, Skipped: %d, Total indexed in DB: %d",
            total_added,
            total_skipped,
            final_count,
        )

        return {
            "files_found": len(files_to_index),
            "chunks_added": total_added,
            "chunks_skipped": total_skipped,
            "total_in_db": final_count,
        }


def run_ingest() -> None:
    """CLI Entrypoint for manual PDF ingestion."""
    force = "--force" in sys.argv or "--reset" in sys.argv
    ingestor = PDFIngestor()
    results = ingestor.ingest_all(force_reindex=force)
    print(
        f"\n[OK] Ingestion Complete:\n"
        f"  - Files: {results['files_found']}\n"
        f"  - Added: {results['chunks_added']}\n"
        f"  - Skipped: {results['chunks_skipped']}\n"
        f"  - Total Chunks in DB: {results['total_in_db']}\n"
    )


if __name__ == "__main__":
    run_ingest()
