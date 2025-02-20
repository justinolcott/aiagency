from git import Repo

# repo = Repo.init('/mnt/pccfs2/backed_up/justinolcott/aiagency/agent_workspace', )
repo = Repo('/mnt/pccfs2/backed_up/justinolcott/aiagency/agent_workspace', )
import subprocess

subprocess.run([
    "git", "config", "--global", "--add", "safe.directory",
    "/mnt/pccfs2/backed_up/justinolcott/aiagency/agent_workspace"
])

# make a new file
with open('/mnt/pccfs2/backed_up/justinolcott/aiagency/agent_workspace/test.txt', 'w') as f:
    f.write('hello world')
    
# add the file to the repo
repo.index.add(['test.txt'])
repo.index.commit('added test.txt')

print(repo.head.commit.message)

first_commit = list(repo.iter_commits(all=True))[-1]
diffs = repo.head.commit.diff(first_commit)
for diff in diffs:
    print(diff.a_blob.data_stream.read().decode('utf-8'))
    
    
from langchain_community.document_loaders import GitLoader

branch = repo.head.reference
loader = GitLoader(repo_path='/mnt/pccfs2/backed_up/justinolcott/aiagency/agent_workspace', branch=branch)
data = loader.load()

print(data)
print(data[0].page_content)

# e.g. loading only python files
# loader = GitLoader(
#     repo_path="./example_data/test_repo1/",
#     file_filter=lambda file_path: file_path.endswith(".py"),
# )
