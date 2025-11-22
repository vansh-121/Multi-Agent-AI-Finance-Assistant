from newspaper import Article
import yfinance as yf
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScrapingAgent:
    def __init__(self):
        pass

    def scrape_news(self, urls, timeout=10):
        """
        Fetch news articles. First tries to extract symbol from URL and use yfinance,
        then falls back to newspaper scraping if needed.
        
        Args:
            urls: List of URLs (can be Yahoo Finance quote pages or article URLs)
            timeout: Timeout in seconds for scraping operations
            
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
                                # Use summary, or title, or create from available fields
                                text = item.get('summary', '') or item.get('title', '')
                                title = item.get('title', 'Market Update')
                                
                                # Ensure we have actual content
                                if not text or len(text.strip()) < 10:
                                    text = f"{title}. Market activity for {symbol}."
                                
                                articles.append({
                                    'title': title,
                                    'text': text,
                                    'url': item.get('link', url),
                                    'publish_date': datetime.fromtimestamp(item.get('providerPublishTime', 0)) if item.get('providerPublishTime') else None
                                })
                            logger.info(f"✅ Fetched {len(news_items[:5])} news articles for {symbol} via yfinance")
                            continue
                        else:
                            logger.warning(f"No news items returned from yfinance for {symbol}")
                    except Exception as e:
                        logger.warning(f"Could not fetch news via yfinance for {url}: {str(e)}")
                
                # Fallback to newspaper scraping for direct article URLs
                try:
                    article = Article(url)
                    article.download()
                    article.parse()
                    
                    if article.text and len(article.text.strip()) > 50:
                        articles.append({
                            'title': article.title or 'Market Article',
                            'text': article.text,
                            'url': url,
                            'publish_date': article.publish_date
                        })
                        logger.info(f"✅ Scraped article via newspaper: {article.title}")
                    else:
                        logger.warning(f"Article text too short or empty from {url}")
                except Exception as e:
                    logger.warning(f"Could not scrape {url} via newspaper: {str(e)}")
            
            if articles:
                logger.info(f"✅ Total articles collected: {len(articles)}")
            else:
                logger.warning("⚠️ No articles were collected from any source - will use fallback")
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Error in scrape_news: {str(e)}")
            return []