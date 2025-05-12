from newspaper import Article
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScrapingAgent:
    def __init__(self):
        pass

    def scrape_news(self, urls):
        try:
            articles = []
            for url in urls:
                article = Article(url)
                article.download()
                article.parse()
                articles.append({
                    'title': article.title,
                    'text': article.text,
                    'url': url,
                    'publish_date': article.publish_date
                })
            logger.info(f"Scraped {len(articles)} articles")
            return articles
        except Exception as e:
            logger.error(f"Error scraping articles: {str(e)}")
            return []