import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from langchain_openai import ChatOpenAI
model = ChatOpenAI(model="gpt-4o")


async def main():
    async with MultiServerMCPClient() as client:
        await client.connect_to_server(
            "math",
            command="python",
            # Make sure to update to the full absolute path to your math_server.py file
            args=["/path/to/math_server.py"],
        )
        await client.connect_to_server(
            "weather",
            command="python",
            # Make sure to update to the full absolute path to your weather_server.py file
            args=["/path/to/weather_server.py"],
        )
        agent = create_react_agent(model, client.get_tools())
        math_response = await agent.ainvoke({"messages": "what's (3 + 5) x 12?"})
        weather_response = await agent.ainvoke({"messages": "what is the weather in nyc?"})
        
        print(math_response)
        print(weather_response)
        


if __name__ == "__main__":
    asyncio.run(main())
