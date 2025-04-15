# Instructions
- Navigate to the `ai_agency` directory.
- Add your API keys to the `.example.env` file.
- Build the docker image with `docker build -t ai-agency .`
- Run the docker container with the following command: `docker run --env-file .example.env -p 8000:8000 -p 3000:3000 ai-agency`
- Access the web app at `http://localhost:3000`

# Warnings and Limitations
- This is a prototype and should not be used in production.
- This gives the ai agency access to the terminal and should be used with caution.
- This may produce unexpected results and should be used with caution.
- AI Assistants were used in the development of this code and should be used with caution.