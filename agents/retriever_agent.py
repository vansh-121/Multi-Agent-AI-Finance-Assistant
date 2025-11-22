from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RetrieverAgent:
    def __init__(self):
        # Use a smaller, more memory-efficient model for production
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-MiniLM-L3-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.vector_store = None

    def index_documents(self, documents):
        try:
            texts = [doc['text'] for doc in documents]
            self.vector_store = FAISS.from_texts(texts, self.embeddings)
            logger.info("Documents indexed in FAISS")
        except Exception as e:
            logger.error(f"Error indexing documents: {str(e)}")

    def retrieve(self, query, k=3):
        try:
            if self.vector_store:
                docs = self.vector_store.similarity_search(query, k=k)
                logger.info(f"Retrieved {len(docs)} documents for query")
                return docs
            return []
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            return []