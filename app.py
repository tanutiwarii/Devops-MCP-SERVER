from ast import Try
import os
import asyncio
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from mcp_use import MCPAgent,MCPClient

async def run_memory_chat():
    load_dotenv()
    os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
    config_file = "brower_mcp.json"
    print("Initializing Chat...")

    client = MCPClient.from_config_file(config_file)
    llm = ChatGroq(model="llama3-8b-8192-latest")
    agent = MCPAgent(llm=llm, client=client, max_steps = 15, memory_enabled=True)

    print("\n ================== Memory Chat ========================\n")
    print("Type 'exit' to end the chat.")
    print("Type 'clear' to clear the memory.")
    print("==========================================================\n")

    try:
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() == "exit":
                print("Exiting...")
                break
            if user_input.lower() == "clear":
                agent.clear_conversation_history()
                print("Memory cleared.")
                continue

            print("\nAssistant: ", end="", flush=True)

            try:
                response = await agent.run(user_input)
                print(response)
            except Exception as e:
                print(f"An error occurred: {e}")
    finally:
        if client and client.sessions:
            await client.close_all_sessions()

if __name__ == "__main__":
    asyncio.run(run_memory_chat())