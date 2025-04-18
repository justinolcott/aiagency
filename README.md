# Instructions
## Docker
- Navigate to the `ai_agency` directory.
- Add your API keys and the default provider to the `.example.env` file.
    - Visit [PydanticAI](https://ai.pydantic.dev/api/models/base/#pydantic_ai.models.KnownModelNames) to get the list of available models.
- Build the docker image with `docker build -t ai-agency .`
- Run the docker container with the following command: `docker run --env-file .example.env -p 8000:8000 -p 3000:3000 ai-agency`
- Access the web app at `http://localhost:3000`

## Locally
- Navigate to the `ai_agency` directory.
- Make sure to have `uv` installed. You can install it with `pip install uv`.
- Set up a virtual environment with `uv venv` and `source .venv/bin/activate`.
- Install the required packages with `uv pip install -r backend/requirements.txt`.
- Set up the environment variables:
    - export `DEFAULT_PROVIDER` to the default provider you want to use.
    - export a corresponding API key for the provider you want to use.
- Run the backend with `uv run -- uvicorn backend.server.app --host 0.0.0.0 --port 8000 --reload`.
- Run the frontend with:
    - `cd frontend`
    - `npm install`
    - `npm run dev`
- Access the web app at `http://localhost:3000` or whichever port is specified.

# Warnings and Limitations
- This is a prototype and should not be used in production.
- This gives the ai agency access to the terminal and should be used with caution.
- This may produce unexpected results and should be used with caution.
- AI Assistants were used in the development of this code and should be used with caution.

end