# src\rag\memory_retriever.py
import uuid
from typing import List, Dict, Any, Optional
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

class MemoryRetriever:
    """
    Handles long-term conversation memory using ChromaDB.
    
    This allows the chatbot to recall facts from past sessions (e.g., "Last time we talked about your Saturn return")
    by performing semantic search over previous conversation turns.
    """
    def __init__(
        self,
        persist_directory: str = "data/vectordb",
        collection_name: str = "conversation_memories",
        embeddings = None
    ):
        # Default to large for consistency with classic knowledge retrieval
        self.embeddings = embeddings or OpenAIEmbeddings(
            model="text-embedding-3-large"
        )
        
        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory
        )

    def add_memory(self, user_id: str, content: str, role: str = "user", metadata: Optional[Dict] = None):
        """
        Add a conversation segment to long-term memory.
        
        Args:
            user_id: The unique ID of the user
            content: The text to remember (should be summarized if long)
            role: "user" | "assistant" | "turn"
            metadata: Additional context (date, intent, etc.)
        """
        meta = metadata or {}
        meta["user_id"] = user_id
        meta["role"] = role
        
        self.vector_store.add_texts(
            texts=[content],
            metadatas=[meta],
            ids=[str(uuid.uuid4())]
        )
        print(f"[MEMORY] Saved new segment to ChromaDB for {user_id}")

    def retrieve_memories(self, user_id: str, query: str, k: int = 3) -> List[Dict]:
        """
        Retrieve relevant past memories for a user given a new query.
        
        Args:
            user_id: Unique user ID
            query: The current query/context to match against
            k: Number of memories to retrieve
            
        Returns:
            List of relevant memory dictionaries
        """
        try:
            results = self.vector_store.similarity_search(
                query,
                k=k,
                filter={"user_id": user_id}
            )
            return [{"content": res.page_content, "metadata": res.metadata} for res in results]
        except Exception as e:
            print(f"[MEMORY] [ERROR] Retrieval failed: {e}")
            return []
