# Xorial Skills — Global

Skills in this directory are injected into agents across all projects using this Xorial installation.

Project-specific skills live in `.xorial/context/skills/`. A project skill with the same filename overrides a core skill.

---

## How to write a skill

```markdown
# Skill: <title>

**Applies to**: all | orchestrator, critic, implementer, reviewer, behavior-reviewer

<instructions for the agent — one clear rule or procedure, max ~200 words>
```

**Rules:**
- `Applies to` is optional — omit it or write `all` to apply to every role
- Multiple roles: comma-separated
- One skill = one concern. Keep it under ~200 words (~300 tokens).
- Filename: kebab-case, e.g. `no-mocks.md`, `commit-style.md`

---

## Install skills from the internet

```bash
# Single skill from raw URL
./.xorial/run.sh skills install https://raw.githubusercontent.com/user/repo/main/skills/skill-name.md

# Full skill pack from a GitHub repo (reads its skills/ directory)
./.xorial/run.sh skills install github:user/repo

# Single skill from a GitHub repo
./.xorial/run.sh skills install github:user/repo/skills/skill-name.md

# List all active skills
./.xorial/run.sh skills list

# Remove a skill
./.xorial/run.sh skills remove skill-name

# Re-download all remotely installed skills
./.xorial/run.sh skills update
```

Installed skills land in `.xorial/context/skills/`.  
A `manifest.json` in that directory tracks sources for updates.

---

## Skill pack convention (for publishing on GitHub)

```
your-xorial-skills/
  skills/
    skill-one.md
    skill-two.md
  README.md
```

Users install it with: `./.xorial/run.sh skills install github:you/your-xorial-skills`
