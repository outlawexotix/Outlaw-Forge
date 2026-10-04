# Safety Rails & Guard Protocol

Safety policies, destructive command detection, and freeze-mode execution guidelines for AI agents working in Outlaw Forge.

---

## 1. Destructive Command Detection & Guard

AI agents must classify shell and database actions before executing them. Destructive commands that cause irreversible data loss require explicit user confirmation.

### 🔴 CRITICAL - Block and Require Explicit User Confirmation
| Pattern | Risk Description |
| :--- | :--- |
| `rm -rf data/uploads/` | Irreversible loss of raw user 3D models |
| `DROP TABLE`, `DROP DATABASE`, `TRUNCATE` | Deletion of SQLite project history and model revisions |
| `git reset --hard` | Discards uncommitted agent and user modifications |
| `git push --force` to `main` / `master` | Overwrites shared repository history |
| `git clean -fd` | Deletes untracked working files permanently |

---

## 2. Freeze Mode for Delicate Debugging

When troubleshooting complex geometry pipelines, matrix transforms, or Three.js scene synchronization, activate **Freeze Mode**:

### Rules in Freeze Mode:
1. **Scope Lockdown**: Edits are restricted only to the specified module or directory (e.g., `apps/api/app/services/mesh_repair.py`).
2. **Blast Radius Control**: If edits exceed $>3$ files or $>50$ lines, pause immediately and justify the scope expansion to the user.
3. **No Drift in Types**: Do not refactor `packages/shared/` or Pydantic schemas during a bugfix unless the contract itself was the bug.

---

## 3. Pre-Commit Safety Checks

Before suggesting or staging a commit:
1. **Scan for Secrets**: Ensure no API keys, tokens, or local credentials exist in staged code.
2. **Scan for Debug Artifacts**: Remove `console.log`, temporary `print()` statements, and scratch files.
3. **Lockfile Integrity**: If `package.json` was modified, verify `package-lock.json` is updated in sync.
4. **Data Directory Cleanliness**: Ensure no test STL files or SQLite databases in `data/` are staged into Git.
