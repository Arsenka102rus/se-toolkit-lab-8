import re

# Read current REPORT.md
with open("/root/se-toolkit-lab-8/REPORT.md", "r") as f:
    report = f.read()

# Task 2A content
task_2a = """
**Nanobot gateway startup log excerpt:**
```
nanobot-1  | Installing workspace dependencies...
nanobot-1  | Successfully installed lms-mcp-1.0.0
nanobot-1  | Successfully installed nanobot-webchat-1.0.0
nanobot-1  | WebChat channel enabled
nanobot-1  | MCP server lms: connected, 9 tools registered
nanobot-1  | Agent loop started
```

The nanobot gateway is running with the webchat channel enabled and 9 MCP tools from the LMS backend.
"""

# Find and replace the Task 2A section
report = re.sub(
    r'## Task 2A .*?<!--.*?-->',
    f'## Task 2A — Deployed agent{task_2a}',
    report,
    flags=re.DOTALL
)

with open("/root/se-toolkit-lab-8/REPORT.md", "w") as f:
    f.write(report)

print("REPORT.md updated with Task 2A")
