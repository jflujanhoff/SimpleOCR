import logging
from openai import OpenAI, AuthenticationError

logger = logging.getLogger(__name__)

# Default model
DEFAULT_MODEL = "gpt-4o-mini"

# Explanation prompt template (moved from ui_interactions)
EXPLANATION_PROMPT_TEMPLATE = (
    "Act as an expert communicator skilled at simplifying complex information. "
    "I will provide you with content from potentially multiple documents below. Your task is to:\n\n"
    "1.  **Identify the Core Subject:** What is this content fundamentally about?\n"
    "2.  **Extract Key Information:** What are the most crucial pieces of information, findings, or instructions?\n"
    "3.  **Simplify the Language:** Rewrite these points using everyday words. Imagine you are explaining it to someone completely unfamiliar with this topic or field.\n"
    "4.  **Explain Necessary Jargon:** If technical terms are unavoidable for accuracy, define them briefly in simple terms.\n"
    "5.  **Summarize Concisely:** Provide a brief summary that captures the essence of the content.\n\n"
    "Focus on clarity and accuracy, ensuring the main message is not lost.\n\n"
    "**Combined Content:**\n"
    "---\n"
    "{file_content}\n"
    "---"
)

# Resume prompt template
RESUME_PROMPT_TEMPLATE = (
    "Act as a professional resume writer. Based *only* on the text provided below, extract key information "
    "and structure it into a concise professional resume outline. Focus on skills, experience, projects, and education mentioned in the text. "
    "If the text is not suitable for creating a resume (e.g., it's a story, a technical manual with no personal info), state that clearly. "
    "Do not invent information not present in the text.\n\n"
    "**Provided Text:**\n"
    "---\n"
    "{file_content}\n"
    "---"
)


class OpenAIChat:
    """Handles interactions with the OpenAI Chat Completion API."""

    def __init__(self, api_key: str):
        """Initializes the OpenAI client."""
        if not api_key:
            raise ValueError("API key cannot be empty.")
        try:
            self.client = OpenAI(api_key=api_key)
            # Optional: Perform a quick test call like listing models?
            # self.client.models.list()
            logger.info("OpenAI client initialized successfully.")
        except AuthenticationError as auth_err:
             logger.error(f"OpenAI Authentication Error during client initialization: {auth_err}")
             raise # Re-raise the specific error
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            # Decide if we should raise a generic error or handle differently
            raise ConnectionError(f"Failed to initialize OpenAI client: {e}") from e

    def _call_api(self, prompt: str, model: str = DEFAULT_MODEL) -> str:
        """Makes a call to the Chat Completion API with the given prompt."""
        try:
            logger.info(f"Calling OpenAI API ({model}) with prompt length: {len(prompt)}")
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=model,
            )
            response = chat_completion.choices[0].message.content
            logger.info("Successfully received response from OpenAI.")
            return response.strip() if response else ""

        except AuthenticationError as auth_err:
            logger.error(f"OpenAI API authentication failed during call: {auth_err}")
            raise # Re-raise for specific handling upstream
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
            # Raise a more specific or custom error if needed
            raise ConnectionError(f"Error communicating with OpenAI API: {e}") from e

    def explain_text(self, text: str, model: str = DEFAULT_MODEL) -> str:
        """Generates an explanation for the given text."""
        if not text:
            logger.warning("explain_text called with empty text.")
            return "No text provided for explanation."
        prompt = EXPLANATION_PROMPT_TEMPLATE.format(file_content=text)
        return self._call_api(prompt, model=model)

    def generate_resume_outline(self, text: str, model: str = DEFAULT_MODEL) -> str:
        """Generates a resume outline based on the given text."""
        if not text:
            logger.warning("generate_resume_outline called with empty text.")
            return "No text provided for resume generation."
        prompt = RESUME_PROMPT_TEMPLATE.format(file_content=text)
        return self._call_api(prompt, model=model) 