import os
import re
import json
import math
from typing import List, Dict, Any, Optional
import httpx
from db import supabase

# Pure Python TF-IDF implementation for fallback search
class MiniTFIDF:
    def __init__(self, documents: List[str]):
        self.documents = documents
        self.doc_tokens = [self.tokenize(doc) for doc in documents]
        self.df = {}
        for tokens in self.doc_tokens:
            for token in set(tokens):
                self.df[token] = self.df.get(token, 0) + 1
        self.n = len(documents)

    def tokenize(self, text: str) -> List[str]:
        # Lowercase and split on non-alphanumeric characters
        return re.findall(r'\w+', text.lower())

    def get_similarity(self, query: str) -> List[float]:
        query_tokens = self.tokenize(query)
        if not query_tokens or self.n == 0:
            return [0.0] * self.n

        # Calculate query term weights
        query_weights = {}
        for token in query_tokens:
            if token in self.df:
                idf = math.log((self.n + 1) / (self.df[token] + 0.5)) + 1
                query_weights[token] = query_weights.get(token, 0) + idf

        # Calculate doc similarities
        scores = []
        for doc_idx, doc_toks in enumerate(self.doc_tokens):
            if not doc_toks:
                scores.append(0.0)
                continue

            doc_tf = {}
            for t in doc_toks:
                doc_tf[t] = doc_tf.get(t, 0) + 1

            score = 0.0
            doc_norm = 0.0
            query_norm = sum(w * w for w in query_weights.values())

            for token, tf in doc_tf.items():
                if token in self.df:
                    idf = math.log((self.n + 1) / (self.df[token] + 0.5)) + 1
                    w_doc = tf * idf
                    doc_norm += w_doc * w_doc
                    if token in query_weights:
                        score += w_doc * query_weights[token]

            if doc_norm > 0 and query_norm > 0:
                score = score / (math.sqrt(doc_norm) * math.sqrt(query_norm))
            else:
                score = 0.0
            scores.append(score)

        return scores


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
    """Split text into overlapping chunks of roughly chunk_size characters."""
    if not text:
        return []
    
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Try to find a sentence/paragraph end within the overlap margin
        if end < len(text):
            # Look backwards up to 'overlap' characters for a period or newline
            lookback_limit = max(start, end - overlap)
            break_idx = -1
            for i in range(end - 1, lookback_limit - 1, -1):
                if text[i] in ['.', '\n', '?', '!']:
                    break_idx = i + 1
                    break
            if break_idx != -1:
                end = break_idx
                
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else end
        if start >= len(text) or (end - start) < 50: # prevent infinite loop or tiny trailing chunks
            break
            
    return [c for c in chunks if len(c) > 10]


def parse_file(file_path: str, filename: str) -> str:
    """Parse document content using MarkItDown, with graceful fallback to standard text extraction."""
    # Try using MarkItDown
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(file_path)
        if result and result.text_content:
            text = result.text_content.strip()
            if text:
                print(f"[RAG] MarkItDown successfully parsed {filename}")
                return text
    except Exception as e:
        print(f"[RAG] MarkItDown conversion failed for {filename}, using fallback: {e}")

    # Fallback to legacy parser
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == '.txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
            
    elif ext == '.csv':
        import csv
        text_lines = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if headers:
                for row_idx, row in enumerate(reader):
                    row_details = []
                    for h, val in zip(headers, row):
                        if val.strip():
                            row_details.append(f"{h}: {val}")
                    if row_details:
                        text_lines.append(f"Row {row_idx + 1}: " + ", ".join(row_details))
            else:
                for row_idx, row in enumerate(reader):
                    text_lines.append(f"Row {row_idx + 1}: " + ", ".join(row))
        return "\n".join(text_lines)
        
    elif ext == '.pdf':
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            pages_text = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            return "\n".join(pages_text)
        except ImportError:
            # Fallback to crude text scanner if pypdf not available
            with open(file_path, 'rb') as f:
                content = f.read()
                # Extract ASCII-like text sequences from the PDF stream
                ascii_chars = re.findall(b'[\x20-\x7E\x0A\x0D]{4,}', content)
                return "\n".join(chunk.decode('ascii', errors='ignore') for chunk in ascii_chars)
    else:
        # Default fallback
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ""


_embedding_service_available = True

async def get_openai_embedding(text: str) -> Optional[List[float]]:
    """Fetch semantic embedding vector from OpenAI API if available."""
    global _embedding_service_available
    if not _embedding_service_available:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
        
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "input": text,
                    "model": "text-embedding-3-small"
                }
            )
            if res.status_code == 200:
                data = res.json()
                return data["data"][0]["embedding"]
            else:
                print(f"[RAG] OpenAI Embedding API returned status {res.status_code}: {res.text}")
                if res.status_code in (401, 403, 429):
                    print("[RAG] Disabling OpenAI embeddings due to authorization/rate limits.")
                    _embedding_service_available = False
    except Exception as e:
        print(f"[RAG] OpenAI Embedding error: {e}")
        print("[RAG] Disabling OpenAI embeddings due to network/timeout issue.")
        _embedding_service_available = False
    return None


async def ingest_document(agent_id: str, user_id: str, file_path: str, filename: str) -> tuple[bool, str]:
    """Parse, chunk, embed, and store document in database."""
    if not supabase:
        return False, "Supabase connection is not configured."

    try:
        # 1. Extract plaintext
        full_text = parse_file(file_path, filename)
        if not full_text.strip():
            return False, "No readable text could be extracted. If it is a PDF or PPTX, please verify it contains digital, selectable text and is not a scanned image."

        # 2. Chunk text
        chunks = chunk_text(full_text)
        if not chunks:
            return False, "Could not segment the extracted document text into chunks."

        # 3. Create Knowledge Base record
        kb_res = supabase.table("knowledge_bases").insert({
            "agent_id": agent_id,
            "user_id": user_id,
            "filename": filename
        }).execute()
        
        if not kb_res.data:
            return False, "Failed to insert document metadata into database."
            
        kb_id = kb_res.data[0]["id"]

        # 4. Process and insert chunks (with optional embeddings)
        chunk_inserts = []
        for chunk in chunks:
            embedding = await get_openai_embedding(chunk)
            chunk_inserts.append({
                "kb_id": kb_id,
                "content": chunk,
                "embedding": embedding # Will be JSON null if not available
            })

        # Insert in batches
        batch_size = 50
        for i in range(0, len(chunk_inserts), batch_size):
            supabase.table("kb_chunks").insert(chunk_inserts[i:i+batch_size]).execute()

        print(f"[RAG] Successfully ingested {filename} ({len(chunks)} chunks) for agent {agent_id}.")
        return True, f"Successfully ingested {filename} ({len(chunks)} chunks)."
    except Exception as e:
        print(f"[RAG] Ingestion failed for {filename}: {e}")
        return False, str(e)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    dot_prod = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a > 0 and norm_b > 0:
        return dot_prod / (norm_a * norm_b)
    return 0.0


async def query_knowledge_base(agent_id: str, query: str, limit: int = 3) -> str:
    """Retrieve the most relevant context chunks for a query from agent's KB."""
    if not supabase:
        return "System error: Knowledge base database connection is not configured."

    try:
        # 1. Fetch all documents for this agent
        kb_res = supabase.table("knowledge_bases").select("id").eq("agent_id", agent_id).execute()
        if not kb_res.data:
            return ""

        kb_ids = [doc["id"] for doc in kb_res.data]
        
        # 2. Fetch all chunks under these docs
        chunk_res = supabase.table("kb_chunks").select("content, embedding").in_("kb_id", kb_ids).execute()
        chunks = chunk_res.data or []
        if not chunks:
            return ""

        # 3. Perform matching
        # Attempt semantic search if query embeddings are available and database contains embeddings
        query_emb = await get_openai_embedding(query)
        has_db_embs = any(c.get("embedding") is not None for c in chunks)

        if query_emb and has_db_embs:
            # Vector cosine similarity matching
            scored_chunks = []
            for chunk in chunks:
                emb = chunk.get("embedding")
                if emb:
                    sim = cosine_similarity(query_emb, emb)
                else:
                    sim = 0.0
                scored_chunks.append((chunk["content"], sim))
            
            # Sort by similarity score descending
            scored_chunks.sort(key=lambda x: x[1], reverse=True)
            top_chunks = [c[0] for c in scored_chunks[:limit]]
            print(f"[RAG] Semantic match complete. Top similarity: {scored_chunks[0][1] if scored_chunks else 0.0}")
            
        else:
            # Fallback to TF-IDF keyword match
            doc_contents = [c["content"] for c in chunks]
            tfidf = MiniTFIDF(doc_contents)
            similarities = tfidf.get_similarity(query)
            
            scored_chunks = list(zip(doc_contents, similarities))
            scored_chunks.sort(key=lambda x: x[1], reverse=True)
            top_chunks = [c[0] for c in scored_chunks[:limit] if c[1] > 0.0]
            print(f"[RAG] Keyword TF-IDF match complete. Matches found: {len(top_chunks)}")

        if not top_chunks:
            return "No relevant facts or information found in the knowledge base."

        # Format context response
        formatted_context = "### KNOWLEDGE BASE RETRIEVED CONTEXT:\n"
        for idx, chunk in enumerate(top_chunks):
            formatted_context += f"Fact {idx + 1}:\n{chunk}\n\n"
            
        return formatted_context.strip()
        
    except Exception as e:
        print(f"[RAG] Query retrieval error: {e}")
        return f"Error retrieving facts: {str(e)}"
