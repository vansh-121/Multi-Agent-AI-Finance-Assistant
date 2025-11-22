import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LanguageAgent:
    def __init__(self):
        """
        Initialize Language Agent with Google Gemini API.
        Set GEMINI_API_KEY environment variable to use Gemini.
        Falls back to structured template if API key not available.
        """
        self.use_gemini = False
        self.gemini_model = None
        
        # Try to initialize Gemini if API key is available
        try:
            import google.generativeai as genai
            api_key = os.getenv('GEMINI_API_KEY')
            
            if api_key:
                genai.configure(api_key=api_key)
                # Use the model name that works with the current API version
                self.gemini_model = genai.GenerativeModel('gemini-2.5-pro')
                self.use_gemini = True
                logger.info("Gemini Pro API initialized successfully")
            else:
                logger.info("GEMINI_API_KEY not found, using structured template")
        except ImportError:
            logger.info("google-generativeai not installed, using structured template")
        except Exception as e:
            logger.warning(f"Could not initialize Gemini: {str(e)}, using structured template")

    def generate_brief(self, context, exposure, earnings):
        """
        Generate a market brief using Gemini API or structured template.
        """
        try:
            # Try Gemini first if available
            if self.use_gemini and self.gemini_model:
                return self._generate_with_gemini(context, exposure, earnings)
            else:
                # Use structured template with real Yahoo Finance data
                logger.info("Generating brief with structured template")
                return self._generate_fallback_brief(context, exposure, earnings)
        except Exception as e:
            logger.error(f"Error generating brief: {str(e)}")
            return self._generate_fallback_brief(context, exposure, earnings)
    
    def _generate_with_gemini(self, context, exposure, earnings):
        """Generate market brief using Google Gemini API"""
        try:
            # Create a detailed prompt for Gemini
            prompt = f"""You are a professional financial analyst. Generate a comprehensive market analysis report based on the following real-time data from Yahoo Finance:

CONTEXT:
{context}

PORTFOLIO EXPOSURE:
{exposure}

EARNINGS DATA:
{earnings}

Please provide a detailed market analysis report that includes:
1. Executive Summary
2. Current Portfolio Positions (with actual prices and values shown)
3. Earnings Analysis and Growth Trends
4. Risk Assessment
5. Key Insights and Recommendations

Format the response in clear, professional markdown. Include specific numbers from the data provided. Be concise but informative."""

            response = self.gemini_model.generate_content(prompt)
            
            if response and response.text:
                logger.info("Successfully generated brief with Gemini API")
                return response.text
            else:
                logger.warning("Gemini returned empty response, using fallback")
                return self._generate_fallback_brief(context, exposure, earnings)
                
        except Exception as e:
            logger.error(f"Error with Gemini API: {str(e)}, using fallback")
            return self._generate_fallback_brief(context, exposure, earnings)
    
    def _generate_fallback_brief(self, context, exposure, earnings):
        """Generate a professional brief with actual Yahoo Finance data"""
        try:
            import re
            import ast
            from datetime import datetime
            
            # Parse exposure data to extract real values
            exposure_data = {}
            if isinstance(exposure, dict):
                exposure_data = exposure
            elif isinstance(exposure, str):
                try:
                    exposure_data = ast.literal_eval(exposure)
                except:
                    pass
            
            # Parse earnings data
            earnings_data = {}
            if isinstance(earnings, dict):
                earnings_data = earnings
            elif isinstance(earnings, str):
                try:
                    earnings_data = ast.literal_eval(earnings)
                except:
                    pass
            
            # Create a professional brief with actual Yahoo Finance data
            brief = "# 📊 Market Analysis Report\n"
            brief += f"*Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n"
            brief += "---\n\n"
            
            # Portfolio Overview
            if exposure_data:
                symbols = list(exposure_data.keys())
                brief += f"## Portfolio Overview\n\n"
                brief += f"**Analyzing:** {', '.join(symbols)}\n\n"
                
                # Total portfolio value
                total_value = sum([exp.get('value', 0) for exp in exposure_data.values()])
                brief += f"### Total Portfolio Value: **${total_value:,.2f}**\n\n"
                
                # Individual positions with real Yahoo Finance data
                brief += "## Position Details\n\n"
                for symbol, exp in exposure_data.items():
                    weight = exp.get('weight', 0) * 100
                    value = exp.get('value', 0)
                    price = exp.get('price', 0)
                    
                    brief += f"### 📈 {symbol}\n\n"
                    brief += f"| Metric | Value |\n"
                    brief += f"|--------|-------|\n"
                    brief += f"| **Current Price** | ${price:.2f} |\n"
                    brief += f"| **Portfolio Weight** | {weight:.1f}% |\n"
                    brief += f"| **Position Value** | ${value:,.2f} |\n"
                    
                    # Add earnings analysis if available
                    if symbol in earnings_data:
                        earnings_info = earnings_data[symbol]
                        if isinstance(earnings_info, list) and len(earnings_info) > 0:
                            brief += f"\n**Earnings Performance:**\n\n"
                            
                            # Sort by year
                            sorted_earnings = sorted(earnings_info, key=lambda x: x.get('Year', 0), reverse=True)
                            
                            # Show recent years
                            for i, period in enumerate(sorted_earnings[:4]):
                                year = period.get('Year', 'N/A')
                                earnings_val = period.get('Earnings', 0)
                                brief += f"- **{year}:** ${earnings_val/1e9:.2f}B\n"
                            
                            # Calculate growth if we have multiple years
                            if len(sorted_earnings) >= 2:
                                latest = sorted_earnings[0].get('Earnings', 0)
                                previous = sorted_earnings[1].get('Earnings', 0)
                                if previous > 0:
                                    growth = ((latest - previous) / previous) * 100
                                    brief += f"\n**Year-over-Year Growth:** {growth:+.1f}%\n"
                    
                    brief += "\n"
                
                # Market context
                if context:
                    context_str = str(context)
                    if len(context_str) > 10:  # Has meaningful content
                        brief += "## Market Context\n\n"
                        # Clean up context
                        if isinstance(context, list):
                            for ctx in context:
                                brief += f"• {ctx}\n"
                        else:
                            brief += f"{context_str[:500]}\n"
                        brief += "\n"
                
                # Risk assessment
                brief += "## Risk Assessment\n\n"
                if len(symbols) == 1:
                    symbol = symbols[0]
                    weight_val = list(exposure_data.values())[0].get('weight', 0)*100
                    brief += f"⚠️ **Concentration Risk:** Portfolio is concentrated in {symbol} "
                    brief += f"with {weight_val:.1f}% allocation.\n\n"
                    brief += "**Recommendation:** Consider diversification to reduce single-stock risk. "
                    brief += "A well-diversified portfolio typically limits individual positions to 5-10%.\n"
                else:
                    brief += f"✅ **Diversification:** Portfolio is diversified across {len(symbols)} positions.\n\n"
                    brief += "**Allocation:**\n"
                    for symbol, exp in exposure_data.items():
                        weight = exp.get('weight', 0) * 100
                        brief += f"- {symbol}: {weight:.1f}%\n"
                
                brief += "\n---\n\n"
                brief += "*Data Source: Yahoo Finance (Real-time)*\n"
                brief += "*Note: Past performance does not guarantee future results. This is for informational purposes only.*"
                
            else:
                brief += "⚠️ **No Portfolio Data Available**\n\n"
                brief += "Please ensure stock symbols are properly specified in your query."
            
            logger.info("Generated professional brief with real Yahoo Finance data")
            return brief
            
        except Exception as e:
            logger.error(f"Error generating fallback brief: {str(e)}")
            return f"Market brief generation encountered an error: {str(e)}\n\nPlease try again with a specific stock symbol."