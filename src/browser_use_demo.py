from langchain_openai import ChatOpenAI
from browser_use import Agent
import asyncio
from dotenv import load_dotenv
load_dotenv()

async def main():
    agent = Agent(
        task="Find the top 1 trending Github repositories from their website and give me a summary of each.",
        llm=ChatOpenAI(model="gpt-4o"),

    )
    result = await agent.run()
    print(result)

asyncio.run(main())