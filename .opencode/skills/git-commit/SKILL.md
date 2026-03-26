---
name: git-commit
description: Create structured git commits with proper messages
---

## What I do

- Analyze staged and unstaged changes with `git status` and `git diff`
- Create commits with conventional commit format
- Verify the commit was successful

## When to use me

Use this skill when you need to commit changes to the repository. Call me with:

```
/commit
```

## Commit workflow

1. **Check changes**
   - Run `git status` to see all changes
   - Run `git diff` to see unstaged changes
   - Run `git diff --staged` to see staged changes

2. **Stage changes**
   - Stage relevant files with `git add`
   - Do NOT stage files that likely contain secrets (.env, credentials, etc.)

3. **Create commit**
   - Use conventional commit format: `<type>: <description>`
   - Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `style`
   - Description in Russian if project uses Russian

4. **Verify**
   - Run `git status` after commit to verify success

## Commit message format

```
<type>: <краткое описание>

<детальное описание если нужно>
```

### Examples

```
fix: исправлена работа прокси в Docker

- Добавлена поддержка AiohttpSession с параметром proxy
- Исправлен network_mode в docker-compose
```

```
feat: добавлена реферальная система
```

```
refactor: вынесен слой repositories
```

## Rules

- NEVER run `git config` commands
- NEVER use `--force` flags
- NEVER commit .env files or secrets
- Check that you're on the correct branch before committing
- One logical change per commit