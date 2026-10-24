# Publish Screenslavers to GitHub and invite teammates

## One-time setup (repository owner)

1. Sign into https://github.com and select **+ → New repository**.
2. Name it `screenslavers`. Select **Private** initially, unless your competition requires public. **Do not initialize** it with README, .gitignore or license: those are already in this folder.
3. From macOS Terminal, `cd` into the extracted `screenslavers` folder and run:

```bash
git init
git branch -M main
git add .
git status
git commit -m "Initial Screenslavers prototype repository"
git remote add origin https://github.com/YOUR_USERNAME/screenslavers.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username. GitHub requires authentication: GitHub CLI (`gh auth login`), a configured credential manager, or SSH is recommended; GitHub account passwords are not accepted for HTTPS Git pushes.

## Invite teammates

On the GitHub repository page, open **Settings → Collaborators and teams → Add people** and invite each teammate by their GitHub username. They must accept the invitation.

## Teammates clone and work

```bash
git clone https://github.com/YOUR_USERNAME/screenslavers.git
cd screenslavers
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./start_backend.sh
```

Open a **second Terminal** and run `./start_frontend.sh`, then visit http://127.0.0.1:5173/.

## Common Git issues

- `remote origin already exists`: run `git remote -v` to check the existing URL; update it with `git remote set-url origin URL` if appropriate.
- `src refspec main does not match any`: make sure the first commit succeeded (`git log -1`).
- `Permission denied` / `403`: check repository access and your GitHub authentication.
- `rejected (fetch first)`: another person pushed first; run `git pull --rebase origin main` and resolve any conflicts.

**Competition rule reminder:** If the event requires all submitted code to be written during the event, do not submit this pre-event prototype or disguise its history. Confirm what GitHub material may be used and submit only compliant work.
