

from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI

from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

model = ChatOpenAI(model="gpt-4o-mini")


# Tools
# from git import Repo
import os
# def create_repo(project_name: str) -> None:
#     """
#     Create a new git repository under agent_workspace.
#     """
#     repo_path = f"agent_workspace/{project_name}"
#     Repo.init(repo_path)
#     return None

def make_dir(directory_path: str) -> None:
    """
    Create a new directory under agent_workspace for example:
        "example_project" makes a new directory "agent_workspace/example_project"
        "example_project/backend" makes a new directory "agent_workspace/example_project/backend"
    """
    print(f"Creating directory {directory_path}")
    os.makedirs(f'agent_workspace/{directory_path}', exist_ok=True)
    return None

def make_file(file_path: str, content: str) -> None:
    """
    Create a new file under agent_workspace for example:
        "example_project/backend/app.py" makes a new file "agent_workspace/example_project/backend/app.py"
        "example_project/frontend/index.html" makes a new file "agent_workspace/example_project/frontend/index.html"
    """
    print(f"Creating file {file_path}")
    with open(f'agent_workspace/{file_path}', "w") as f:
        f.write(content)
    return None

backend_swe_agent = create_react_agent(
    model=model,
    tools=[make_dir, make_file],
    name="backend_swe",
    prompt="You are a backend software engineer. You can create files and directories to build the project."
           "You first need to make a backend directory in the project folder."
           "Then you need to create all necessary files and content the backend directory."
           "Return a summary of what was done and how to run the code to the supervisor."
           "You have access to the following tools: make_dir, make_file."
)

frontend_swe_agent = create_react_agent(
    model=model,
    tools=[make_dir, make_file],
    name="frontend_swe",
    prompt="You are a frontend software engineer. You can create files and directories to build the project."
              "You first need to make a frontend directory in the project folder."
                "Then you need to create all necessary files and content the frontend directory."
                "Return a summary of what was done and how to run the code to the supervisor."
                "You have access to the following tools: make_dir, make_file."
)

# research_agent = create_react_agent(
#     model=model,
#     tools=[web_search],
#     name="research_expert",
#     prompt="You are a world class researcher with access to web search. Do not do any math."
# )

# Create supervisor workflow
# workflow = create_supervisor(
#     [research_agent, math_agent],
#     model=model,
#     prompt=(
#         "You are a team supervisor managing a research expert and a math expert. "
#         "For current events, use research_agent. "
#         "For math problems, use math_agent."
#     )
# )

workflow = create_supervisor(
    [backend_swe_agent, frontend_swe_agent],
    tools=[make_dir, make_file],
    model=model,
    prompt=(
        "You are a team supervisor managing two software engineers. "
        "You first make a new directory for the project by using make_dir."
        "Determine the interface between backend and frontend and assign tasks to each of them. Provide with the tasks they need and the name of the project_directory."
        "They will then report back to you and you will return a summary of the entire project and instructions on how to run it."
    )
)

# checkpointer = InMemorySaver()
# store = InMemoryStore()

# Compile and run
app = workflow.compile(
    # checkpointer=checkpointer,
    # store=store
)
result = app.invoke({
    "messages": [
        {
            "role": "user",
            "content": "Make a frontend and backend for a todo app using python."
        }
    ]
})

print(result)

