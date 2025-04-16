from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from typing import Optional, List
import os

from backend.agency import (
    Agency, Agent, remove_agent_helper, message_agent_helper, create_new_agent_helper,
    all_tools
)

SAVE_DIR = "conversations"
os.makedirs(SAVE_DIR, exist_ok=True)

app = FastAPI()



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize Agency ---
# PROMPTS
MAIN_AGENT_SYSTEM_PROMPT = """You are a friendly, helpful assistant. You are the main agent in a hierachical system of agents.
You have access to a variety of tools including the ability to create new agents, message other agents, and have meetings.
When the user gives you a task, you will first think through the task and then decide which tool to use. Use your ability to work with
other agents to complete the task by delegating subtasks. Hold meetings to ensure all agents are on the same page and that everyone is working towards the same goal.
"""


app.state.agency = Agency(workspace_id="webapi_workspace", main_agent_system_prompt=MAIN_AGENT_SYSTEM_PROMPT)

# --- Pydantic models for requests ---

class CreateAgentRequest(BaseModel):
    name: str
    system_prompt: str
    parent_id: Optional[str] = None

class MessageAgentRequest(BaseModel):
    message: str

class StartAgencyRequest(BaseModel):
    workspace_id: Optional[str] = None
    from_state_file: Optional[str] = None  # filename in SAVE_DIR

# --- API Endpoints ---

@app.get("/agency/state")
async def get_agency_state(request: Request):
    agency = request.app.state.agency
    return agency.save_state().model_dump()

@app.get("/agent/{agent_id}/state")
async def get_agent_state(agent_id: str, request: Request):
    agency = request.app.state.agency
    agent = agency.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.save_state().model_dump()

@app.get("/agents")
async def list_agents(request: Request):
    agency = request.app.state.agency
    return [agent.save_state().model_dump() for agent in agency.agents.values()]

@app.post("/agent/create")
async def create_agent(req: CreateAgentRequest, request: Request):
    agency = request.app.state.agency
    parent_id = req.parent_id or agency.main_agent.id
    # Ensure new agents get default MCP servers
    
    new_agent_id = agency.next_id()
    new_agent = Agent(
        agency,
        req.name,
        new_agent_id,
        agency.default_provider,
        req.system_prompt,
        mcp_servers=agency.default_mcp_servers
    )
    agency.agents[new_agent_id] = new_agent
    if parent_id in agency.agents:
        new_agent.parent_id = parent_id
        agency.agents[parent_id].children[new_agent_id] = new_agent
    return {"agent_id": new_agent_id}

@app.post("/agent/{agent_id}/message")
async def message_agent(agent_id: str, req: MessageAgentRequest, request: Request):
    agency = request.app.state.agency
    if agent_id not in agency.agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        response = await message_agent_helper(agency, agent_id, req.message)
        return {"response": response}
    except Exception as e:
        print(f"Error messaging agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/agent/{agent_id}")
async def remove_agent(agent_id: str, request: Request):
    agency = request.app.state.agency
    if agent_id not in agency.agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    result = await remove_agent_helper(agency, agent_id)
    return {"result": result}

# --- Agency State Management Endpoints ---

@app.get("/agency/states")
def list_agency_states():
    """List all saved agency state files."""
    files = [
        f for f in os.listdir(SAVE_DIR)
        if f.endswith(".json") or f.endswith(".yaml") or f.endswith(".yml")
    ]
    return {"states": files}

@app.get("/agency/state/{state_file}")
def get_agency_state_file(state_file: str):
    """Get a specific saved agency state by file name."""
    file_path = os.path.join(SAVE_DIR, state_file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="State file not found")
    with open(file_path, "r") as f:
        if state_file.endswith(".json"):
            import json
            return json.load(f)
        else:
            import yaml
            return yaml.safe_load(f)

@app.post("/agency/start")
async def start_new_agency(req: StartAgencyRequest):
    """Start a new agency, optionally from a saved state file."""
    # Stop and clean up current agency
    if hasattr(app.state, "agency") and app.state.agency:
        await app.state.agency.shutdown()
    # Start new agency
    if req.from_state_file:
        file_path = os.path.join(SAVE_DIR, req.from_state_file)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="State file not found")
        app.state.agency = Agency.load_from_file(file_path, tools=all_tools)
        return {"status": "started", "from_state_file": req.from_state_file}
    else:
        workspace_id = req.workspace_id or f"webapi_workspace_{os.urandom(4).hex()}"
        app.state.agency = Agency(workspace_id=workspace_id, main_agent_system_prompt=MAIN_AGENT_SYSTEM_PROMPT)
        return {"status": "started", "workspace_id": workspace_id}

@app.post("/agency/stop")
async def stop_agency():
    """Stop the current agency and save its state."""
    if not hasattr(app.state, "agency") or not app.state.agency:
        raise HTTPException(status_code=400, detail="No active agency")
    agency = app.state.agency
    # Save state
    agency.save_to_file(SAVE_DIR)
    await agency.shutdown()
    app.state.agency = None
    return {"status": "stopped", "saved": True}

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "agency") and app.state.agency:
        await app.state.agency.shutdown()

# --- Run with: uvicorn api_server:app --reload ---

