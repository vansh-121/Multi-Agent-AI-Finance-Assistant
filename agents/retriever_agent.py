import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RetrieverAgent:
    """Lightweight retriever using keyword matching (no ML embeddings)"""
    def __init__(self):
        self.documents = []
        self.texts = []

    def index_documents(self, documents):
        """Store documents for keyword-based retrieval"""
        try:
            self.documents = documents
            self.texts = []
            
            for doc in documents:
                # Try to get text from 'text' or 'content' or 'summary' fields
                text = doc.get('text', '') or doc.get('content', '') or doc.get('summary', '')
                
                # Also accept the title if text is empty
                if not text:
                    text = doc.get('title', '')
                
                # Add document with combined text and title for better matching
                if text.strip():
                    # Combine title + text for better keyword matching
                    title = doc.get('title', '')
                    full_text = f"{title}. {text}" if title else text
                    self.texts.append(full_text)
            
            logger.info(f"Indexed {len(self.texts)} documents (from {len(documents)} total)")
            if len(self.texts) == 0 and documents:
                logger.warning(f"No valid texts found. Sample doc keys: {documents[0].keys() if documents else 'empty'}")
        except Exception as e:
            logger.error(f"Error indexing documents: {str(e)}")

    def retrieve(self, query, k=3):
        """Simple keyword-based retrieval"""
        try:
            if not self.texts:
                return []
            
            # Score texts based on keyword overlap
            query_words = set(query.lower().split())
            scored_texts = []
            
            for i, text in enumerate(self.texts):
                text_words = set(text.lower().split())
                overlap = len(query_words & text_words)
                scored_texts.append((overlap, text))
            
            # Sort by score and return top k
            scored_texts.sort(reverse=True, key=lambda x: x[0])
            results = [{"page_content": text} for score, text in scored_texts[:k] if score > 0]
            
            # If no matches, return all texts
            if not results:
                results = [{"page_content": text} for text in self.texts[:k]]
            
            logger.info(f"Retrieved {len(results)} documents for query")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            return []