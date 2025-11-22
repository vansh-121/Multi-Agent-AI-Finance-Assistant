"""
Simple retriever without ML embeddings for low-memory environments
"""
import logging
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleRetrieverAgent:
    def __init__(self):
        self.documents = []

    def index_documents(self, documents):
        """Store documents without embeddings"""
        try:
            self.documents = documents
            logger.info(f"Indexed {len(documents)} documents")
        except Exception as e:
            logger.error(f"Error indexing documents: {str(e)}")

    def retrieve(self, query, k=3):
        """Simple keyword-based retrieval"""
        try:
            if not self.documents:
                return []
            
            # Score documents based on keyword overlap
            scored_docs = []
            query_words = set(query.lower().split())
            
            for doc in self.documents:
                text = doc.get('text', '').lower()
                title = doc.get('title', '').lower()
                
                # Count matching words
                text_words = set(text.split())
                title_words = set(title.split())
                
                text_overlap = len(query_words & text_words)
                title_overlap = len(query_words & title_words) * 2  # Weight titles higher
                
                score = text_overlap + title_overlap
                scored_docs.append((score, doc['text']))
            
            # Sort by score and return top k
            scored_docs.sort(reverse=True, key=lambda x: x[0])
            results = [doc[1] for doc in scored_docs[:k]]
            
            logger.info(f"Retrieved {len(results)} documents for query")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            return []
