from dotenv import load_dotenv
load_dotenv()

from langchain_deepseek import ChatDeepSeek
import logging
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage

model_name = "deepseek-chat"
# model_name = "deepseek-reasoner"

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ModelLogger")

class LoggingChatDeepSeek(ChatDeepSeek):
    """A wrapper around ChatDeepSeek that logs message previews."""
    
    def _log_message_preview(self, message: BaseMessage, prefix: str = ""):
        """Log a preview of a message with its role."""
        role = message.type
        content = message.content
        if isinstance(content, str):
            preview = content[:50] + ("..." if len(content) > 50 else "")
            logger.info(f"{prefix}[{role}] {preview}")
        else:
            logger.info(f"{prefix}[{role}] [Non-text content]")
    
    def _log_helper(self, messages: List[BaseMessage]):
        """Log a list of messages."""
        logger.info("New Invocation:")
        for i, msg in enumerate(messages):
            self._log_message_preview(
                msg,
                f"  Message {i+1}: "
            )
    
    def invoke(self, messages: List[BaseMessage], **kwargs) -> BaseMessage:
        """Invoke the model with a list of messages."""
        self._log_helper(messages)
        return super().invoke(messages, **kwargs)

# Initialize the model
model = LoggingChatDeepSeek(model=model_name)


if __name__ == "__main__":
    prompt = "What is the capital of France?"
    response = model.invoke([HumanMessage(content=prompt)])
    print(response.content)