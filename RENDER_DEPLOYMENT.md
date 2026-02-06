# Render Deployment Guide for LifeTrack

## Step 1: Initialize Git Repository Locally

Open PowerShell in your project folder and run:

```powershell
cd C:\Users\Luka\Desktop\LifeTrack
git init
git add .
git commit -m "Initial commit - ready for Render deployment"
```

## Step 2: Create GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Create a new repository called `lifetrack` (or similar)
3. **DO NOT** add README, .gitignore, or license (you already have these)
4. Click "Create repository"

## Step 3: Connect Local Git to GitHub

After creating the repository, GitHub will show commands. In your PowerShell:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/lifetrack.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

## Step 4: Deploy to Render

1. Go to [render.com](https://render.com) and sign up (or login)
2. Click "New +" → "Web Service"
3. Select "Connect a repository"
4. Authorize Render to access your GitHub account
5. Select your `lifetrack` repository
6. Fill in the settings:
   - **Name**: `lifetrack` (or similar)
   - **Environment**: `Python 3`
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

7. **IMPORTANT - For Persistent Data Storage:**
   - Scroll to "Disks" section
   - Click "Add Disk"
   - **Mount Path**: `/app/data`
   - **Disk Size**: 512 MB (free tier can handle this)
   - Click "Create"

8. **Add Environment Variables:**
   - Click "Environment"
   - Add these variables:
     ```
     FLASK_SECRET_KEY = <generate a random string at https://randomkeygen.com/ - copy the "CodeIgniter Encryption Keys" value>
     FLASK_ENV = production
     ```

9. Click "Create Web Service"

Render will automatically:
- Build your app
- Deploy it
- Provide you with a live URL

## Step 5: Enable Auto-Deployment from GitHub

Once deployed, Render automatically watches your GitHub repository. This means:
- ✅ Every time you push to GitHub, Render automatically deploys the latest version
- ✅ Your data persists in the `/data` directory (mapped to the Render disk)
- ✅ Users registered on the live site stay registered

## Step 6: Workflow for Future Updates

1. **Make changes locally** in VS Code
2. **Commit and push to GitHub**:
   ```powershell
   git add .
   git commit -m "Your commit message"
   git push
   ```
3. **Check Render dashboard** - deployment starts automatically
4. **See live site** at your deployed URL

## Important Notes

### Data Persistence
- The `/data` folder is mounted to a persistent Render disk
- User data (users.json, entries.json, etc.) will **NOT** be lost between deployments
- Each time you deploy, your data carries over

### Environment Variables
- Store the `FLASK_SECRET_KEY` in Render environment variables, NOT in your code
- Users with free tier: You'll get one free instance, free PostgreSQL database (100MB), and free disk storage

### Troubleshooting

**Check deployment logs**: In Render dashboard, click your service → "Logs" tab

**Common issues:**
- `ModuleNotFoundError`: Missing dependency in requirements.txt
- `gunicorn not found`: Run `pip install gunicorn` locally, then `pip freeze > requirements.txt`
- Port issues: The Procfile uses `gunicorn app:app` which is correct

## Manual Git Commands Reference

```powershell
# Check status
git status

# Add all changes
git add .

# Commit with message
git commit -m "Your message"

# Push to GitHub (Render auto-deploys)
git push

# Check logs
git log --oneline
```

---
**After first deployment**, your app will be live at something like: `https://lifetrack-xxxx.onrender.com`
