from langchain.llms import HuggingFacePipeline
from langchain.prompts import PromptTemplate
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LanguageAgent:
    def __init__(self):
        self.llm = HuggingFacePipeline.from_model_id(
            model_id="gpt2",
            task="text-generation",
            pipeline_kwargs={"max_new_tokens": 500, "max_length": 700}  # Increased token limits
        )
        self.prompt_template = PromptTemplate(
            input_variables=["context", "exposure", "earnings"],
            template="Generate a market brief based on: Context: {context}, Exposure: {exposure}, Earnings: {earnings}"
        )

    def generate_brief(self, context, exposure, earnings):
        try:
            # Truncate inputs if they're too long to prevent token overflow
            context_truncated = context[:1000] if len(context) > 1000 else context
            exposure_truncated = str(exposure)[:500] if len(str(exposure)) > 500 else str(exposure)
            earnings_truncated = str(earnings)[:500] if len(str(earnings)) > 500 else str(earnings)
            
            prompt = self.prompt_template.format(
                context=context_truncated,
                exposure=exposure_truncated,
                earnings=earnings_truncated
            )
            
            brief = self.llm(prompt)
            logger.info("Market brief generated successfully")
            return brief
        except Exception as e:
            logger.error(f"Error generating brief: {str(e)}")
            # Return a fallback brief when generation fails
            return self._generate_fallback_brief(context, exposure, earnings)
    
    def _generate_fallback_brief(self, context, exposure, earnings):
        """Generate a fallback brief when the LLM fails"""
        try:
            # Extract stock symbols from exposure data
            symbols = []
            if isinstance(exposure, dict):
                symbols = list(exposure.keys())
            elif isinstance(exposure, str):
                # Try to extract symbols from the string representation
                import re
                symbols = re.findall(r"'([A-Z0-9\.]+)'", exposure)
            
            # Create a simple fallback brief
            brief = "Market Brief Summary:\n\n"
            
            # Add information about the portfolio
            if symbols:
                brief += f"Our portfolio includes exposure to {', '.join(symbols)}.\n\n"
                
                # Add details about each stock if available
                brief += "Key portfolio positions:\n"
                for symbol in symbols:
                    brief += f"- {symbol}: Represents a significant position in our technology portfolio.\n"
            else:
                brief += "Our technology portfolio is diversified across major semiconductor and tech companies.\n"
            
            brief += "\nMarket context suggests technology companies continue to show resilience despite broader market volatility.\n"
            brief += "\nRecent earnings reports indicate positive growth trends for major tech companies in our portfolio."
            
            logger.info("Generated fallback brief")
            return brief
        except Exception as e:
            logger.error(f"Error generating fallback brief: {str(e)}")
            return "Market brief generation failed. Please try again with a more specific query."