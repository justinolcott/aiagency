"""
MESSAGING
I need to come up with a way for AI agents to message each other which is fairly simple, the hard part is knowing what context to include:

- No context, just a simple expert question
- Common context, include the last message both agents had in common, so maybe the last supervisor message before the split or the meeting they had together.
- Full context, include the entire conversation history of the agent, so they can use their detailed knowledge of the conversation to inform their response.
- Maybe we send a message to a supervisor, and he passes it on, and they pass it on, so on and so forth. This way, the agent can send a message and it finds the exact person.
    - This might be implemented as to make sending a message quite simple and solve the problem of knowing who to send it to since the agent might not know.
    - Or maybe this is used simply to find who to send a message to, and then the agent sends the message directly to that person which could include the user.


FILE EDITING
We need a way for the agents to create, edit, and delete files. We might need a summary of all files. They then can open the relevant file and edit the necessary parts.
- rewrite the entire file
- specify the lines to rewrite

GIT
The agents will all be working in parallel, so we need a way to manage the git repository. By using Git...
- we can track changes made by the agents
- we will need a way to resolve conflicts
- it would provide a nice way to review the changes made by the agents
- it would also allow for changes to be labeled, so they can be easily undone later.

TERMINAL
- Ideally the terminal would be able to be saved and loaded, so the agents can continue where they left off. Almost like tmux.
- The terminal would be able to run commands and display the output.
- The tools would be like new terminal, new command, ls command, and delete.
- so we would have a terminal manager that has a list of terminals running. It can create a new terminal, run a command on a terminal, delete a terminal, and list all terminals. When a new command is run, it would be added to the terminal's history as well as the output. The output is also sent to the agent.
"""