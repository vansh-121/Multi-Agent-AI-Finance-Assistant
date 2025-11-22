from newspaper import Article
import yfinance as yf
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScrapingAgent:
    def __init__(self):
        pass

    def scrape_news(self, urls):
        """
        Fetch news articles. First tries to extract symbol from URL and use yfinance,
        then falls back to newspaper scraping if needed.
        
        Args:
            urls: List of URLs (can be Yahoo Finance quote pages or article URLs)
            
        Returns:
            List of article dictionaries with title, text, url, and publish_date
        """
        try:
            articles = []
            
            for url in urls:
                # Try to extract symbol from Yahoo Finance quote URL
                # Format: https://finance.yahoo.com/quote/SYMBOL/news/
                if 'finance.yahoo.com/quote/' in url:
                    try:
                        symbol = url.split('/quote/')[1].split('/')[0]
                        logger.info(f"Extracting news for {symbol} using yfinance API")
                        
                        ticker = yf.Ticker(symbol)
                        news_items = ticker.news
                        
                        if news_items:
                            for item in news_items[:5]:  # Limit to 5 most recent articles
                                articles.append({
                                    'title': item.get('title', 'No title'),
                                    'text': item.get('summary', item.get('title', '')),
                                    'url': item.get('link', url),
                                    'publish_date': datetime.fromtimestamp(item.get('providerPublishTime', 0)) if item.get('providerPublishTime') else None
                                })
                            logger.info(f"Fetched {len(news_items[:5])} news articles for {symbol} via yfinance")
                            continue
                    except Exception as e:
                        logger.warning(f"Could not fetch news via yfinance for {url}: {str(e)}")
                
                # Fallback to newspaper scraping for direct article URLs
                try:
                    article = Article(url)
                    article.download()
                    article.parse()
                    articles.append({
                        'title': article.title,
                        'text': article.text,
                        'url': url,
                        'publish_date': article.publish_date
                    })
                    logger.info(f"Scraped article via newspaper: {article.title}")
                except Exception as e:
                    logger.warning(f"Could not scrape {url} via newspaper: {str(e)}")
            
            if articles:
                logger.info(f"Total articles collected: {len(articles)}")
            else:
                logger.warning("No articles were collected from any source")
            
            return articles
            
        except Exception as e:
            logger.error(f"Error in scrape_news: {str(e)}")
            return []