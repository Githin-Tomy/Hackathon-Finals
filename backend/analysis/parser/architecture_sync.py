import os
os.environ["TIKTOKEN_CACHE_DIR"] = r"C:\Users\GenAIKOCVISUSR62\tiktoken_cache"
import ast
import re
import logging
import base64
from datetime import datetime
import httpx
from sqlalchemy.orm import Session
import chromadb
from langchain_openai import OpenAIEmbeddings

from app.config import get_settings
from app.db.database import Repository
from integrations.github.client import get_github_client

logger = logging.getLogger(__name__)

# Singleton httpx client to bypass SSL verification for custom Azure GenAILab endpoint
_http_client = httpx.Client(verify=False)

def get_embeddings():
    """Retrieve OpenAIEmbeddings configured with the custom Maas endpoint."""
    settings = get_settings()
    return OpenAIEmbeddings(
        base_url=settings.openai_base_url,
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        http_client=_http_client,
    )

def sanitize_text(text: str) -> str:
    """Strip secret tokens, keys, passwords, IP addresses and credentials for privacy."""
    if not text:
        return ""
    # Remove secrets like API keys, github tokens, private keys
    text = re.sub(r"(?i)(api[_-]key|secret|token|password|passwd|auth_token)\s*[:=]\s*['\"][^'\"]+['\"]", r"\1: [REDACTED]", text)
    # Remove general hex/alphanumeric keys
    text = re.sub(r"\b(sk-[a-zA-Z0-9]{20,})\b", "[REDACTED_API_KEY]", text)
    text = re.sub(r"\b(github_pat_[a-zA-Z0-9_]{20,})\b", "[REDACTED_GITHUB_TOKEN]", text)
    # Remove IPv4 addresses
    text = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[REDACTED_IP]", text)
    return text

def extract_ast_skeleton(code: str) -> str:
    """Extract AST signatures, docstrings, and imports programmatically without execution bodies."""
    if not code:
        return "Empty file"
    try:
        tree = ast.parse(code)
    except Exception as e:
        return f"Parse Error: {e}"
        
    skeleton = []
    
    # Extract imports
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.append(f"import {name.name}")
        elif isinstance(node, ast.ImportFrom):
            names = ", ".join(n.name for n in node.names)
            imports.append(f"from {node.module or ''} import {names}")
            
    if imports:
        skeleton.append("### Imports:")
        skeleton.extend(f"  - {imp}" for imp in imports)
        
    # Extract classes and function signatures
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node)
            class_doc_str = f" - Docstring: {class_doc}" if class_doc else ""
            skeleton.append(f"\n### Class {node.name}{class_doc_str}")
            
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_doc = ast.get_docstring(child)
                    func_doc_str = f" - Docstring: {func_doc}" if func_doc else ""
                    args = ", ".join(arg.arg for arg in child.args.args)
                    skeleton.append(f"  - Method {child.name}({args}){func_doc_str}")
                    
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_doc = ast.get_docstring(node)
            func_doc_str = f" - Docstring: {func_doc}" if func_doc else ""
            args = ", ".join(arg.arg for arg in node.args.args)
            skeleton.append(f"\n### Function {node.name}({args}){func_doc_str}")
            
    return sanitize_text("\n".join(skeleton))

def get_collection_name(repo_full_name: str) -> str:
    """Sanitize repository full name to create a valid Chroma collection identifier."""
    # Replace slashes and special characters with underscores
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", repo_full_name)
    # Strip leading/trailing dashes or underscores
    cleaned = cleaned.strip("_").strip("-")
    # Limit length to 3-63 characters per Chroma naming rules
    return cleaned[:63]

class ChromaDBManager:
    """Manages persistent embeddings storage using a local embedded ChromaDB instance."""
    def __init__(self):
        # Store DB in backend/chroma_db/ directory
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db")
        os.makedirs(db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)
        
    def get_collection(self, repo_full_name: str):
        """Returns collection segmented by repository name."""
        collection_name = get_collection_name(repo_full_name)
        # Chroma client handles creation/fetching
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

# Initialize Chroma manager
_chroma_manager = ChromaDBManager()

def sync_repo_context(repo_id: int, repo_full_name: str, db: Session) -> bool:
    """Sync repository architecture context: extracts AST structures and vectorizes them in Chroma DB."""
    logger.info("🔄 Starting context sync for %s (id: %d)...", repo_full_name, repo_id)
    try:
        gh = get_github_client()
        gh_repo = gh.get_repo(repo_full_name)
        
        # Get default branch head sha
        branch = gh_repo.default_branch
        head_sha = gh_repo.get_branch(branch).commit.sha
        
        # Get repository tree recursive
        git_tree = gh_repo.get_git_tree(sha=head_sha, recursive=True)
        py_files = [el.path for el in git_tree.tree if el.path.endswith(".py") and el.type == "blob"]
        
        collection = _chroma_manager.get_collection(repo_full_name)
        
        # Clear existing vectors to ensure fresh sync
        existing = collection.get()
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
            
        embeddings_model = get_embeddings()
        
        for file_path in py_files:
            try:
                # Download file
                content_file = gh_repo.get_contents(file_path, ref=head_sha)
                if isinstance(content_file, list):
                    content_file = content_file[0]
                raw = base64.b64decode(content_file.content).decode("utf-8", errors="replace")
                
                # Extract skeleton and sanitize
                skeleton = extract_ast_skeleton(raw)
                
                # Compute vector embedding via LangChain embeddings model
                vector = embeddings_model.embed_query(skeleton)
                
                # Insert in Chroma
                collection.add(
                    ids=[file_path],
                    embeddings=[vector],
                    documents=[skeleton],
                    metadatas=[{"file_path": file_path, "repo_id": repo_id}]
                )
                logger.info("   ✅ Indexed context for: %s", file_path)
            except Exception as file_err:
                logger.warning("   ⚠️ Failed context sync for file %s: %s", file_path, file_err)
                
        # Generate summary context for Repository model column
        # Query Chroma for the core structure summaries
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if repo:
            # We summarize the main file list & docstrings in a compact overview
            all_docs = collection.get()["documents"]
            summary_parts = []
            for doc in all_docs[:10]: # Limit to top 10 modules for high level overview
                # Extract class/function signatures
                first_lines = [line for line in doc.splitlines() if line.startswith("### ")][:3]
                summary_parts.extend(first_lines)
                
            repo.system_context = "\n".join(summary_parts) if summary_parts else "No signatures documented."
            repo.context_last_updated = datetime.now()
            db.commit()
            
        logger.info("✅ Context sync complete for %s. Total indexed files: %d", repo_full_name, len(py_files))
        return True
    except Exception as exc:
        logger.error("❌ Context sync failed for %s: %s", repo_full_name, exc, exc_info=True)
        return False

def query_architecture_context(repo_full_name: str, query_text: str, n_results: int = 3) -> str:
    """Query the repository's isolated Chroma DB collection to get matching caller/design signatures."""
    try:
        collection = _chroma_manager.get_collection(repo_full_name)
        embeddings_model = get_embeddings()
        
        # Compute vector for the query text
        query_vector = embeddings_model.embed_query(query_text)
        
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=n_results
        )
        
        documents = results.get("documents", [[]])[0]
        if not documents:
            return "No matching architecture context."
            
        return "\n\n---\n\n".join(documents)
    except Exception as exc:
        logger.error("⚠️ Failed to query Chroma DB for repo %s: %s", repo_full_name, exc)
        return "Error loading architecture context."
