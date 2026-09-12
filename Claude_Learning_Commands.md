# MCP Server Setup

## Local Database in MCP

### 1. Add SQLite MCP

Run:

```powershell
claude mcp add --transport stdio sqlite -- npx -y @executeautomation/database-server E:\Self-Learning\Claude\expense-tracker\expense_tracker.db
```

### 2. Verify

```powershell
claude mcp list
```

Expected:

```text
sqlite · ✓ connected
```

---

## GitHub MCP Server

### 1. Create GitHub Token

Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.

Set repository access and grant the required permissions:

* **Contents** → Read and write
* **Issues** → Read and write
* **Pull requests** → Read and write
* **Actions** → Read and write
* **Metadata** → Read-only

Copy the token after generating it.

### 2. Set Token

```powershell
$env:PAT="YOUR_GITHUB_TOKEN"
```

### 3. Add GitHub MCP

```powershell
claude mcp add --transport http github https://api.githubcopilot.com/mcp -H "Authorization: Bearer $env:PAT"
```

### 4. Verify

```powershell
claude mcp list
```

Expected:

```text
github · ✓ connected
```

---

## Figma MCP Server

### 1. Install Figma MCP

```powershell
claude plugin install figma@claude-plugins-official
```

### 2. Verify

```powershell
claude plugin list
```

Confirm that the Figma plugin is installed.

---

## Verify All MCP Servers

```powershell
claude mcp list
```

Check that the required servers show:

```text
sqlite · ✓ connected
github · ✓ connected
```

Then start Claude Code:

```powershell
claude
```
