# Instructions
- Navigate to the `ai_agency` directory.
- Add your API keys to the `.example.env` file.

## Building the Docker Image
`docker build -t ai-agency .`


## Running the Docker Image
`docker run --env-file .example.env -p 8000:8000 -p 3000:3000 ai-agency`