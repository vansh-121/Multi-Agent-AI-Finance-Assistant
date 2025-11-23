import streamlit as st
import requests
import io
import logging
import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import sys
from pathlib import Path
from stock_symbols import ALL_STOCKS, CATEGORIES, get_stock_display_name, search_stocks

# Add parent directory to path for importing agents
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from agents.prediction_agent import PredictionAgent
from agents.graphing_agent import GraphingAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize agents
prediction_agent = PredictionAgent()
graphing_agent = GraphingAgent()

# Determine the API URL based on environment
# On Streamlit Cloud: Set API_URL in Secrets
# Locally: Use localhost:8000
try:
    # Try to get from Streamlit secrets first (Streamlit Cloud)
    API_URL = st.secrets.get("API_URL", os.environ.get("API_URL", "http://localhost:8000"))
except Exception:
    # Fallback to environment variable if secrets not available
    API_URL = os.environ.get("API_URL", "http://localhost:8000")

# Debug: Log the API URL being used
st.sidebar.text(f"API: {API_URL}")

st.title("🧠 Morning Market Brief Assistant")
st.markdown("""
**Professional market insights powered by AI - covering 460+ global stocks!**

Get comprehensive financial analysis on any stock from major exchanges worldwide:
🇺🇸 US Markets | 🌏 Asian Markets | 🌍 European Markets | 📊 ETFs | ₿ Crypto

Select stocks from the sidebar and ask your question below!
""")

# Data source info
st.info("""
📊 **Data Sources:** Real-time market data via Yahoo Finance API  
🤖 **AI Analysis:** Multi-agent system for portfolio risk assessment  
⚡ **Note:** On cloud deployments, news scraping may use enhanced fallback data enriched with market statistics
""")

# Display the current API endpoint (useful for debugging)
# st.sidebar.markdown(f"**API Endpoint:** `{API_URL}`")

# Stock selection feature
st.sidebar.header("📈 Stock Selection")
st.sidebar.markdown("**Select from 400+ global stocks, ETFs, and crypto!**")

# Selection method
selection_method = st.sidebar.radio(
    "Choose selection method:",
    ["Browse by Category", "Search by Name/Symbol", "Enter Custom Symbol"]
)

selected_stocks = []
selected_symbols = []

if selection_method == "Browse by Category":
    # Category-based selection
    selected_category = st.sidebar.selectbox("Select Category", list(CATEGORIES.keys()))
    
    # Get stocks for this category
    category_stocks = CATEGORIES[selected_category]
    stock_options = [get_stock_display_name(symbol) for symbol in category_stocks]
    
    selected_stocks = st.sidebar.multiselect(
        f"Select stocks from {selected_category}",
        stock_options,
        help="Select one or more stocks to analyze"
    )
    
    # Extract symbols
    selected_symbols = [stock.split(" - ")[0] for stock in selected_stocks]

elif selection_method == "Search by Name/Symbol":
    # Search-based selection
    search_query = st.sidebar.text_input(
        "🔍 Search stocks",
        placeholder="Type company name or symbol (e.g., Apple, MSFT, Tesla...)",
        help="Search across 400+ stocks"
    )
    
    if search_query:
        search_results = search_stocks(search_query)
        
        if search_results:
            st.sidebar.success(f"Found {len(search_results)} matches!")
            
            # Show results as a selectbox
            result_options = [f"{symbol} - {name}" for symbol, name in search_results[:20]]  # Limit to 20 results
            
            selected_stocks = st.sidebar.multiselect(
                "Select from search results",
                result_options,
                help="Select one or more stocks"
            )
            
            # Extract symbols
            selected_symbols = [stock.split(" - ")[0] for stock in selected_stocks]
        else:
            st.sidebar.warning("No stocks found. Try a different search term.")
            
elif selection_method == "Enter Custom Symbol":
    # Manual entry for any stock
    st.sidebar.info("💡 Enter any Yahoo Finance ticker symbol")
    custom_symbols_input = st.sidebar.text_input(
        "Enter symbol(s)",
        placeholder="e.g., AAPL, MSFT, TSM",
        help="Enter one or multiple symbols separated by commas"
    )
    
    if custom_symbols_input:
        # Parse comma-separated symbols
        selected_symbols = [s.strip().upper() for s in custom_symbols_input.split(",") if s.strip()]
        selected_stocks = [get_stock_display_name(symbol) for symbol in selected_symbols]
        
        st.sidebar.success(f"Selected: {', '.join(selected_symbols)}")

# Display selected stocks with details
if selected_symbols:
    st.sidebar.markdown("### ✅ Selected Stocks:")
    for symbol in selected_symbols:
        company_name = ALL_STOCKS.get(symbol, "Custom Symbol")
        if company_name != "Custom Symbol":
            st.sidebar.text(f"• {symbol} - {company_name}")
        else:
            st.sidebar.text(f"• {symbol}")
    
    st.sidebar.markdown(f"**Total: {len(selected_symbols)} stock(s)**")
    
    # Prepare query with selected stocks
    stock_query = f"Analyze {', '.join(selected_symbols)}. What's the current market situation and risk exposure?"
else:
    stock_query = ""
    st.sidebar.info("👆 Select stocks above to analyze")

# Show available stock count
st.sidebar.markdown("---")
st.sidebar.info(f"📊 Total available stocks: {len(ALL_STOCKS)}")
st.sidebar.caption("248 US | 49 Asian | 40 European | 98 ETFs | 20 Crypto")

# Quick reference guide
with st.sidebar.expander("📖 Symbol Format Guide"):
    st.markdown("""
    **Stock Symbol Formats:**
    - 🇺🇸 US: `AAPL`, `MSFT`, `GOOGL`
    - 🇰🇷 Korea: `005930.KS` (Samsung)
    - 🇯🇵 Japan: `7203.T` (Toyota)
    - 🇨🇳 Hong Kong: `0700.HK` (Tencent)
    - 🇮🇳 India: `RELIANCE.NS`
    - 🇬🇧 UK: `BP.L`
    - 🇩🇪 Germany: `SAP.DE`
    - 🇫🇷 France: `MC.PA`
    - 🇨🇭 Switzerland: `NESN.SW`
    - 🇨🇦 Canada: `SHOP.TO`
    - 🇦🇺 Australia: `CBA.AX`
    - ₿ Crypto: `BTC-USD`, `ETH-USD`
    
    **Tips:**
    - Most US stocks use simple tickers
    - International stocks have country suffixes
    - Search by company name if unsure
    """)

# Text query input with default that includes selected stocks
st.markdown("### 💬 Ask Your Question")

# Example queries
with st.expander("💡 Example Questions"):
    st.markdown("""
    - "Analyze AAPL, MSFT, and GOOGL. What's the market trend?"
    - "Compare Samsung (005930.KS) and TSMC performance"
    - "What's the risk exposure in my crypto portfolio? BTC-USD, ETH-USD"
    - "How are European tech stocks performing? SAP.DE, ASML"
    - "Give me a market brief on SPY and QQQ ETFs"
    - "Analyze Tesla vs traditional auto makers"
    - "What's happening with semiconductor stocks?"
    """)

query = st.text_input(
    "Enter your market analysis question:", 
    value=stock_query if stock_query else "What's our risk exposure in tech stocks today?",
    help="Ask about specific stocks, market trends, or portfolio risk"
)

if st.button("Get Brief"):
    with st.spinner("Processing query..."):
        try:
            # Check if FastAPI is reachable
            try:
                st.info(f"🔗 Connecting to: {API_URL}")
                logger.info(f"Attempting to connect to {API_URL}")
                
                health_check = requests.get(f"{API_URL}/", timeout=10)
                if health_check.status_code != 200:
                    st.error(f"FastAPI server not reachable: {health_check.status_code} - {health_check.text}")
                    logger.error(f"FastAPI health check failed: {health_check.status_code} - {health_check.text}")
                else:
                    st.success("✅ Connected to backend!")
                    logger.info("FastAPI server is healthy")
                    
                    # Step 1: Retrieve relevant documents with explicit symbols if selected
                    logger.info(f"Sending retrieve request with query: {query}")
                    
                    # Add selected symbols as query parameters if they exist
                    params = {"query": query}
                    if selected_symbols:
                        params["symbols"] = ",".join(selected_symbols)
                        st.info(f"Explicitly requesting analysis for: {', '.join(selected_symbols)}")
                    
                    retrieve_response = requests.get(f"{API_URL}/retrieve/retrieve", params=params, timeout=30)
                    logger.info(f"Retrieve response status: {retrieve_response.status_code}")
                    
                    if retrieve_response.status_code != 200:
                        st.error(f"Retrieval failed with status {retrieve_response.status_code}")
                        logger.error(f"Retrieval failed: {retrieve_response.status_code} - {retrieve_response.text}")
                        
                        # Add detailed error information
                        try:
                            error_details = retrieve_response.json()
                            if "error" in error_details:
                                st.code(f"Error details: {error_details['error']}")
                        except:
                            st.code(f"Raw response: {retrieve_response.text[:500]}...")
                    else:
                        retrieve_data = retrieve_response.json()
                        logger.info(f"Retrieved data successfully")
                        
                        if "error" in retrieve_data:
                            st.error(f"❌ {retrieve_data['error']}")
                            logger.error(f"Retrieval error: {retrieve_data['error']}")
                            
                            # Show helpful suggestions
                            if "attempted_symbols" in retrieve_data:
                                st.warning(f"Failed symbols: {', '.join(retrieve_data['attempted_symbols'])}")
                            if "suggestion" in retrieve_data:
                                st.info(f"💡 {retrieve_data['suggestion']}")
                            
                            # Show example valid symbols
                            st.markdown("### Valid Symbol Examples:")
                            st.markdown("""
                            - **US Tech:** AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA
                            - **Finance:** JPM, BAC, V, MA, GS
                            - **Asian:** TSM, 005930.KS, 0700.HK, RELIANCE.NS
                            - **Crypto:** BTC-USD, ETH-USD, SOL-USD
                            - **ETFs:** SPY, QQQ, VOO
                            """)
                        else:
                            # If we have selected symbols, make sure they're in the data
                            if selected_symbols:
                                retrieve_data["symbols"] = selected_symbols
                            
                            # Display the analyzed stocks
                            symbols = retrieve_data.get("symbols", [])
                            if symbols:
                                st.info(f"📊 Analyzing stocks: {', '.join(symbols)}")
                            
                            # Check if we have real market data
                            market_data_available = bool(retrieve_data.get("market_data", {}))
                            context_available = bool(retrieve_data.get("context", []))
                            
                            if market_data_available:
                                st.success(f"✅ Real-time market data loaded for {len(retrieve_data.get('market_data', {}))} symbols")
                            
                            # Display some retrieved data for verification
                            with st.expander("📈 View retrieved data"):
                                st.write("**Query:**", retrieve_data.get("query"))
                                st.write("**Markets included:**", list(retrieve_data.get("market_data", {}).keys()))
                                st.write("**Context sources:**", len(retrieve_data.get("context", [])))
                                
                                # Show sample context
                                contexts = retrieve_data.get("context", [])
                                if contexts:
                                    st.write("**Sample context:**")
                                    for i, ctx in enumerate(contexts[:2], 1):
                                        # Show first 200 chars of each context
                                        ctx_preview = ctx[:200] + "..." if len(ctx) > 200 else ctx
                                        st.text(f"{i}. {ctx_preview}")
                            
                            # Step 2: Analyze and get summary
                            st.info("Generating market brief...")
                            analyze_response = requests.post(
                                f"{API_URL}/analyze/analyze", 
                                json={"data": retrieve_data},
                                timeout=60
                            )
                            logger.info(f"Analyze response status: {analyze_response.status_code}")
                            
                            if analyze_response.status_code != 200:
                                st.error(f"Analysis failed with status {analyze_response.status_code}")
                                logger.error(f"Analysis failed: {analyze_response.status_code} - {analyze_response.text}")
                                
                                # Add detailed error information
                                try:
                                    error_details = analyze_response.json()
                                    if "error" in error_details:
                                        st.code(f"Error details: {error_details['error']}")
                                except:
                                    st.code(f"Raw response: {analyze_response.text[:500]}...")
                            else:
                                analyze_data = analyze_response.json()
                                
                                if "error" in analyze_data:
                                    st.error(f"Analysis error: {analyze_data['error']}")
                                    logger.error(f"Analysis error: {analyze_data['error']}")
                                else:
                                    # Display market brief
                                    st.subheader("Market Brief:")
                                    st.markdown(analyze_data["summary"])
                                    
                                    # If 2 or more stocks are analyzed, show comparison
                                    if len(selected_symbols) >= 2:
                                        st.divider()
                                        st.subheader("📊 Side-by-Side Comparison")
                                        
                                        # Extract market data for comparison
                                        market_data = retrieve_data.get("market_data", {})
                                        
                                        if market_data:
                                            # Prepare comparison data
                                            comparison_cols = st.columns(len(selected_symbols))
                                            
                                            for idx, symbol in enumerate(selected_symbols):
                                                with comparison_cols[idx]:
                                                    st.markdown(f"### {symbol}")
                                                    
                                                    if symbol in market_data:
                                                        stock_data = market_data[symbol]
                                                        
                                                        # Display key metrics
                                                        if isinstance(stock_data, dict):
                                                            st.metric(
                                                                "Current Price",
                                                                f"${stock_data.get('price', 'N/A'):.2f}" if isinstance(stock_data.get('price'), (int, float)) else stock_data.get('price', 'N/A')
                                                            )
                                                            
                                                            if stock_data.get('change'):
                                                                try:
                                                                    change_value = float(stock_data.get('change', 0))
                                                                    change_color = "normal" if change_value >= 0 else "inverse"
                                                                    st.metric(
                                                                        "Daily Change",
                                                                        f"{change_value:.2f}%",
                                                                        delta_color=change_color
                                                                    )
                                                                except (ValueError, TypeError):
                                                                    st.metric(
                                                                        "Daily Change",
                                                                        f"{stock_data.get('change', 'N/A')}"
                                                                    )
                                                            
                                                            if stock_data.get('52_week_high'):
                                                                st.caption(f"52W High: ${stock_data.get('52_week_high', 'N/A')}")
                                                            
                                                            if stock_data.get('52_week_low'):
                                                                st.caption(f"52W Low: ${stock_data.get('52_week_low', 'N/A')}")
                                                            
                                                            if stock_data.get('market_cap'):
                                                                st.caption(f"Market Cap: {stock_data.get('market_cap', 'N/A')}")
                                                            
                                                            if stock_data.get('pe_ratio'):
                                                                st.caption(f"P/E Ratio: {stock_data.get('pe_ratio', 'N/A')}")
                                                        else:
                                                            # Fallback display for other data types
                                                            st.write(stock_data)
                                                    else:
                                                        st.warning(f"No data available for {symbol}")
                                        
                                        # Add detailed line-by-line comparison table
                                        st.markdown("#### Detailed Metrics Comparison")
                                        
                                        # Build comparison table from actual market data
                                        comparison_data = {}
                                        
                                        for symbol in selected_symbols:
                                            if symbol in market_data:
                                                stock_data = market_data[symbol]
                                                
                                                # If stock_data is a list (serialized DataFrame), calculate metrics
                                                if isinstance(stock_data, list) and len(stock_data) > 0:
                                                    try:
                                                        # Convert to DataFrame for easier processing
                                                        df = pd.DataFrame(stock_data)
                                                        
                                                        # Calculate metrics from the data
                                                        latest = df.iloc[-1] if not df.empty else {}
                                                        
                                                        comparison_data[symbol] = {
                                                            'Current Price': f"${latest.get('Close', 'N/A'):.2f}" if 'Close' in latest and pd.notna(latest.get('Close')) else 'N/A',
                                                            'Daily Change %': f"{((latest.get('Close', 0) - df.iloc[-2].get('Close', 0)) / df.iloc[-2].get('Close', 1) * 100):.2f}%" if len(df) > 1 and 'Close' in latest else 'N/A',
                                                            '52W High': f"${df['High'].max():.2f}" if 'High' in df.columns else 'N/A',
                                                            '52W Low': f"${df['Low'].min():.2f}" if 'Low' in df.columns else 'N/A',
                                                            'Avg Volume': f"{df['Volume'].mean():,.0f}" if 'Volume' in df.columns else 'N/A',
                                                            'Latest Volume': f"{latest.get('Volume', 'N/A'):,.0f}" if 'Volume' in latest and pd.notna(latest.get('Volume')) else 'N/A'
                                                        }
                                                    except Exception as e:
                                                        logger.warning(f"Error calculating metrics for {symbol}: {str(e)}")
                                                        comparison_data[symbol] = {
                                                            'Current Price': 'N/A',
                                                            'Daily Change %': 'N/A',
                                                            '52W High': 'N/A',
                                                            '52W Low': 'N/A',
                                                            'Avg Volume': 'N/A',
                                                            'Latest Volume': 'N/A'
                                                        }
                                                # If stock_data is already a dict with metrics
                                                elif isinstance(stock_data, dict):
                                                    comparison_data[symbol] = {
                                                        'Current Price': f"${stock_data.get('price', 'N/A'):.2f}" if isinstance(stock_data.get('price'), (int, float)) else stock_data.get('price', 'N/A'),
                                                        'Daily Change %': f"{stock_data.get('change', 'N/A')}%",
                                                        '52W High': stock_data.get('52_week_high', 'N/A'),
                                                        '52W Low': stock_data.get('52_week_low', 'N/A'),
                                                        'Market Cap': stock_data.get('market_cap', 'N/A'),
                                                        'P/E Ratio': stock_data.get('pe_ratio', 'N/A')
                                                    }
                                                else:
                                                    comparison_data[symbol] = {'Status': 'No data available'}
                                            else:
                                                comparison_data[symbol] = {'Status': 'Symbol not found'}
                                        
                                        # Create and display comparison dataframe
                                        if comparison_data:
                                            comparison_df = pd.DataFrame(comparison_data)
                                            st.dataframe(comparison_df, use_container_width=True)
                                        else:
                                            st.info("No data available for comparison table")
                                    
                                    st.success("Query processed successfully!")
                                    
                                    # ===== EARNINGS AND GROWTH TRENDS VISUALIZATION SECTION =====
                                    st.divider()
                                    st.subheader("📊 Yearly Earnings & Growth Analysis")
                                    
                                    # Fetch earnings data and create predictions
                                    earnings_data_dict = {}
                                    growth_data_dict = {}
                                    
                                    try:
                                        with st.spinner("Generating earnings forecasts and growth trend analysis..."):
                                            for symbol in selected_symbols:
                                                try:
                                                    # Try to get earnings data from the backend
                                                    earnings_response = requests.get(
                                                        f"{API_URL}/get_earnings",
                                                        params={"symbol": symbol},
                                                        timeout=15
                                                    )
                                                    
                                                    if earnings_response.status_code == 200:
                                                        earnings_json = earnings_response.json()
                                                        if "earnings" in earnings_json and earnings_json["earnings"]:
                                                            # Convert to DataFrame
                                                            earnings_df = pd.DataFrame(earnings_json["earnings"])
                                                            
                                                            # Generate predictions
                                                            earnings_with_pred = prediction_agent.predict_earnings(
                                                                earnings_df, symbol, years_to_predict=2
                                                            )
                                                            if earnings_with_pred is not None:
                                                                earnings_data_dict[symbol] = earnings_with_pred
                                                                
                                                                # Get growth rate predictions
                                                                growth_with_pred = prediction_agent.predict_growth_rate(
                                                                    earnings_df, symbol, years_to_predict=2
                                                                )
                                                                if growth_with_pred is not None:
                                                                    growth_data_dict[symbol] = growth_with_pred
                                                except Exception as e:
                                                    logger.warning(f"Could not get earnings for {symbol}: {str(e)}")
                                                    continue
                                        
                                        # Display visualizations if we have data
                                        if earnings_data_dict:
                                            st.info(f" Generated predictions for {len(earnings_data_dict)} stock(s)")
                                            
                                            # Create tabs for different visualization types
                                            tab1, tab2, tab3 = st.tabs([
                                                "📈 Earnings Trends",
                                                "📊 Growth Rates",
                                                "🔄 Combined Analysis"
                                            ])
                                            
                                            with tab1:
                                                st.markdown("#### Yearly Earnings Comparison (Historical + Predicted)")
                                                st.caption("Blue lines show historical earnings, Orange dashed lines show AI predictions")
                                                
                                                try:
                                                    fig_earnings = graphing_agent.create_yearly_earnings_comparison(
                                                        earnings_data_dict,
                                                        title="Yearly Earnings Comparison: Historical vs Predicted"
                                                    )
                                                    if fig_earnings:
                                                        st.pyplot(fig_earnings)
                                                        
                                                        # Add interpretation
                                                        with st.expander("📝 How to read this chart"):
                                                            st.markdown("""
                                                            - **Blue lines (circles)**: Actual historical earnings
                                                            - **Orange dashed lines (squares)**: AI-predicted future earnings
                                                            - **Vertical gap**: Transition point from historical to predicted data
                                                            
                                                            The predictions are based on polynomial regression analysis of historical trends.
                                                            """)
                                                except Exception as e:
                                                    logger.error(f"Error creating earnings chart: {str(e)}")
                                                    st.warning(f"Could not generate earnings chart: {str(e)}")
                                            
                                            with tab2:
                                                st.markdown("#### Year-over-Year Growth Trends (Historical + Predicted)")
                                                st.caption("Shows growth rates with baseline at 0% for reference")
                                                
                                                try:
                                                    fig_growth = graphing_agent.create_growth_trend_comparison(
                                                        growth_data_dict,
                                                        title="Year-over-Year Growth Trends: Historical vs Predicted"
                                                    )
                                                    if fig_growth:
                                                        st.pyplot(fig_growth)
                                                        
                                                        # Add interpretation
                                                        with st.expander("📝 How to read this chart"):
                                                            st.markdown("""
                                                            - **Blue lines (circles)**: Historical growth rates
                                                            - **Orange dashed lines (squares)**: Predicted growth rates
                                                            - **Black line at 0%**: No growth reference baseline
                                                            
                                                            Positive values indicate earnings growth, negative values indicate decline.
                                                            """)
                                                except Exception as e:
                                                    logger.error(f"Error creating growth chart: {str(e)}")
                                                    st.warning(f"Could not generate growth chart: {str(e)}")
                                            
                                            with tab3:
                                                st.markdown("#### Combined Earnings & Growth Analysis")
                                                st.caption("Integrated view showing both metrics simultaneously")
                                                
                                                try:
                                                    fig_combined = graphing_agent.create_combined_earnings_and_growth(
                                                        earnings_data_dict,
                                                        growth_data_dict,
                                                        title="Comprehensive Analysis"
                                                    )
                                                    if fig_combined:
                                                        st.pyplot(fig_combined)
                                                        
                                                        # Add interpretation
                                                        with st.expander("📝 How to read this chart"):
                                                            st.markdown("""
                                                            **Top Panel - Earnings:**
                                                            - Shows absolute earnings values over time
                                                            - Useful for assessing company size and profitability
                                                            
                                                            **Bottom Panel - Growth Trends:**
                                                            - Shows percentage change year-over-year
                                                            - Useful for assessing company momentum
                                                            
                                                            Both panels show historical data (solid lines) and predictions (dashed lines).
                                                            """)
                                                except Exception as e:
                                                    logger.error(f"Error creating combined chart: {str(e)}")
                                                    st.warning(f"Could not generate combined chart: {str(e)}")
                                            
                                            # Display comparison table
                                            st.divider()
                                            st.markdown("#### 📊 Key Metrics Comparison Table")
                                            
                                            try:
                                                comparison_table = graphing_agent.create_comparison_table(
                                                    selected_symbols,
                                                    earnings_data_dict,
                                                    growth_data_dict
                                                )
                                                if comparison_table is not None and not comparison_table.empty:
                                                    st.dataframe(comparison_table, use_container_width=True)
                                                    
                                                    # Add download button for the data
                                                    csv = comparison_table.to_csv(index=False)
                                                    st.download_button(
                                                        label="📥 Download Comparison Data (CSV)",
                                                        data=csv,
                                                        file_name=f"earnings_analysis_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                                        mime="text/csv"
                                                    )
                                            except Exception as e:
                                                logger.error(f"Error creating comparison table: {str(e)}")
                                                st.warning(f"Could not generate comparison table: {str(e)}")
                                        else:
                                            st.info("💡 Earnings data not available for the selected stocks. This may occur for newer companies or limited data availability.")
                                    
                                    except Exception as e:
                                        logger.error(f"Error in earnings analysis section: {str(e)}")
                                        st.warning(f"Earnings analysis encountered an issue: {str(e)}")
                                
            except requests.exceptions.ConnectionError:
                st.error(f"FastAPI server is trying to connect to Render services. If it takes long, try running it locally.")
                logger.error(f"Connection error: Failed to connect to FastAPI server at {API_URL}")
        except Exception as e:
            st.error(f"Failed to process query: {str(e)}")
            logger.error(f"Exception in query processing: {str(e)}")

# Audio query input (optional for voice I/O)
st.subheader("Or upload an audio query (WAV/MP3)")
audio_file = st.file_uploader("Upload audio", type=["wav", "mp3"])

if audio_file is not None:
    st.audio(audio_file, format="audio/wav")
    with st.spinner("Processing audio query..."):
        try:
            files = {"audio": (audio_file.name, audio_file, "audio/wav")}
            
            # If we have selected symbols, add them as form data
            data = {}
            if selected_symbols:
                data = {"symbols": ",".join(selected_symbols)}
                
            response = requests.post(f"{API_URL}/process_query", files=files, data=data, stream=True)
            logger.info(f"Audio process_query response status: {response.status_code}")
            
            if response.status_code == 200:
                audio_bytes = io.BytesIO(response.content)
                st.audio(audio_bytes, format="audio/mp3")
                st.success("Audio query processed successfully!")
            else:
                try:
                    error_msg = response.json().get("error", "Unknown error")
                    st.error(f"Audio processing error: {error_msg}")
                    logger.error(f"Audio processing error: {error_msg}")
                except:
                    st.error(f"Audio processing failed with status {response.status_code}")
                    logger.error(f"Audio processing failed with status {response.status_code}")
        except requests.exceptions.ConnectionError:
            st.error(f"FastAPI server is trying to connect to Render services. If it takes long, try running it locally.")
            logger.error(f"Connection error: Failed to connect to FastAPI server at {API_URL}")
        except Exception as e:
            st.error(f"Failed to process audio query: {str(e)}")
            logger.error(f"Exception in audio query processing: {str(e)}")

# Add a section to explain how the application works
with st.expander("ℹ️ How this application works"):
    st.write("""
    ### Architecture
    
    This application uses a **separated frontend-backend architecture**:
    
    1. **Streamlit Frontend** (This interface):
       - User-friendly interface for stock selection and queries
       - Communicates with the FastAPI backend via REST API
       - Displays analysis results and market briefs
    
    2. **FastAPI Backend** (Orchestrator):
       - Runs independently on port 8000
       - Orchestrates multiple AI agents for data processing
       - Handles API requests from the frontend
    
    3. **AI Agents**:
       - **API Agent**: Fetches market data via yfinance
       - **Scraping Agent**: Crawls news using newspaper3k  
       - **Retriever Agent**: Indexes and retrieves relevant data
       - **Analysis Agent**: Calculates portfolio risk exposure
       - **Language Agent**: Generates comprehensive narratives
       - **Voice Agent**: Handles speech-to-text and text-to-speech
    
    ### Data Flow:
    
    ```
    User Query → Streamlit → FastAPI Backend → AI Agents → Analysis → Response → Streamlit → User
    ```
    
    ### Features:
    
    - ✅ **460+ Global Stocks**: US, Asia, Europe, Canada, Australia
    - ✅ **ETFs & Indices**: SPY, QQQ, S&P 500, NASDAQ, and more
    - ✅ **Cryptocurrencies**: Bitcoin, Ethereum, and major altcoins
    - ✅ **Real-time Data**: Via Yahoo Finance API
    - ✅ **News Analysis**: Scrapes and analyzes market news
    - ✅ **Risk Assessment**: Portfolio exposure analysis
    - ✅ **AI-Powered Briefs**: Comprehensive market narratives
    
    When you ask a question, the system:
    1. Fetches real-time market data
    2. Retrieves relevant news articles
    3. Calculates portfolio risk and exposure
    4. Generates earnings analysis
    5. Creates a comprehensive market brief
    """)

# Add a section to explain how to debug the application
with st.expander("🔧 Troubleshooting"):
    st.write("""
    ### Common issues and solutions:
    
    1. **FastAPI server not reachable**: Make sure the FastAPI server is running on the right port with:
       ```
       uvicorn orchestrator.orchestrator:app --host 0.0.0.0 --port 8000
       ```
       
    2. **Running in Streamlit Cloud**: Both services must be running. Make sure the FastAPI orchestrator 
       is started in the Dockerfile or defined in your cloud deployment.
       
    3. **Internal Server Error (500)**: Check the logs of the FastAPI server for more details.
    
    4. **JSON serialization errors**: These often happen with pandas DataFrames. The updated code should handle this.
    
    5. **Empty or incorrect responses**: The system now has fallback data to ensure you always get a response.
    
    6. **Stock not recognized**: Try using the ticker symbol directly (e.g., AAPL instead of Apple) in your query.
    """)