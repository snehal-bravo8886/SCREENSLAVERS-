# Team collaboration

Use **one shared GitHub repository**. Keep `main` as the stable branch; each team member works in a separate branch and opens a pull request.

| Owner | Suggested branch | Paths |
|---|---|---|
| Member 1 | `member1-detection` | `member1/`, root `src/` (coordinate importer changes) |
| Member 2 | `member2-cases` | `member_b/`, relevant tests |
| Member 3 | `member3-frontend` | `frontend/` |
| Member 4 | `member4-api` | `backend/`, `scripts/`, root integration tests |

```bash
git checkout main
git pull origin main
git checkout -b member3-frontend
# make changes, then:
git add frontend/
git commit -m "Improve investigation dashboard"
git push -u origin member3-frontend
```

Create a Pull Request on GitHub; ask another teammate to review it. Merge only after tests pass. To get merged changes locally: `git checkout main && git pull origin main`.

**Never commit** `.env`, API tokens, `.venv/`, `node_modules/`, or real personal/banking records. Use only the documented synthetic dataset. Do not rewrite commit history to suggest work was performed during an event when it was not. Follow event rules on prebuilt code and AI assistance.
