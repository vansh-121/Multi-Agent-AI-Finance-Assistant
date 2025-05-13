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
            pipeline_kwargs={"max_length": 200}
        )
        self.prompt_template = PromptTemplate(
            input_variables=["context", "exposure", "earnings"],
            template="Generate a market brief based on: Context: {context}, Exposure: {exposure}, Earnings: {earnings}"
        )

    def generate_brief(self, context, exposure, earnings):
        try:
            prompt = self.prompt_template.format(
                context=context,
                exposure=exposure,
                earnings=earnings
            )
            brief = self.llm(prompt)
            logger.info("Market brief generated")
            return brief
        except Exception as e:
            logger.error(f"Error generating brief: {str(e)}")
            return ""