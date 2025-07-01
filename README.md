# TRMNL Calibre Library Plugin

Display your Calibre library on TRMNL e-ink devices. Shows recently added books with ratings, tags, and page counts, plus a random book suggestion.

## Overview

This plugin syncs your local Calibre library to a cloud service (Railway/Render), then displays it on your TRMNL device. Most Calibre users keep their libraries local and secured, so this plugin uses a sync approach rather than direct OPDS access.

**What you'll see on your TRMNL:**
- Recently added books with metadata
- Star ratings and page counts
- Book tags/genres
- Random book suggestion ("Book Roulette")
- Total library statistics

## Requirements

- [TRMNL device](https://usetrmnl.com) with Developer Edition
- Local [Calibre](https://calibre-ebook.com) installation
- Cloud hosting account (Railway, Render, or similar)
- Python 3.x on your local machine

## Installation Guide

### Step 1: Fork the Recipe on TRMNL

1. Go to [TRMNL Recipes](https://usetrmnl.com/recipes)
2. Find "Calibre Library Status" 
3. Click **Fork** (not Install) to create an editable copy
4. You'll be redirected to your Private Plugin settings

### Step 2: Deploy the Cloud Service

#### Option A: Railway (Recommended)

1. Fork this repository to your GitHub account
2. Sign up for [Railway](https://railway.app)
3. Create a new project from your forked repo
4. Set these environment variables in Railway:
   ```
   SYNC_TOKEN=choose-a-secure-token-here
   USE_MOCK_DATA=false
   PORT=5000
   ```
5. Deploy the service
6. Copy your Railway URL (format: `https://your-app.up.railway.app`)

#### Option B: Render

1. Fork this repository
2. Sign up for [Render](https://render.com)
3. Create new Web Service from your fork
4. Add the same environment variables as above
5. Deploy with start command: `python app.py`

### Step 3: Configure the Sync Script

1. Download `sync_to_railway.py` from this repository
2. Open it in a text editor
3. Update these lines at the top:
   ```python
   RAILWAY_URL = "https://your-app.up.railway.app"  # Your Railway URL
   SYNC_TOKEN = "choose-a-secure-token-here"        # Same as Railway env
   CALIBRE_LIBRARY_PATH = os.path.expanduser("~/Calibre Library")
   ```
4. Save the file

### Step 4: Run Initial Sync

1. Install required Python packages:
   ```bash
   pip install requests schedule
   ```

2. Run the sync script:
   ```bash
   python sync_to_railway.py
   ```

3. Choose option 1 for a one-time sync to test
4. Verify success message shows your books synced

### Step 5: Configure TRMNL Plugin

1. Return to your forked plugin on TRMNL
2. In the configuration form, set:
   - **Polling URL**: `https://your-app.up.railway.app/trmnl-recent`
   - **Method**: GET
   - **Headers**: (leave empty)
3. Click "Force Refresh" to test
4. If successful, save the plugin

### Step 6: Set Up Automatic Sync

Run the sync script in daemon mode:
```bash
python sync_to_railway.py
```
Choose option 2 (every 30 minutes) or 3 (every hour)

**For permanent sync**, use your system's service manager:
- **Linux**: Create a systemd service
- **macOS**: Use launchd
- **Windows**: Use Task Scheduler

## Configuration

### Environment Variables (Railway/Render)

| Variable | Required | Description |
|----------|----------|-------------|
| `SYNC_TOKEN` | Yes | Authentication token (choose any secure string) |
| `USE_MOCK_DATA` | No | Set to `false` for production |
| `PORT` | No | Default: 5000 |

### Sync Script Settings

Edit these in `sync_to_railway.py`:
- `RAILWAY_URL`: Your deployed service URL
- `SYNC_TOKEN`: Must match Railway/Render setting
- `CALIBRE_LIBRARY_PATH`: Path to your Calibre library

## Troubleshooting

### No books showing on TRMNL

1. Check sync script output for errors
2. Visit `https://your-app.up.railway.app/health` to verify deployment
3. Check `https://your-app.up.railway.app/debug` for configuration status
4. Ensure sync completed successfully

### Sync script can't find Calibre database

The script searches common locations. If not found, update `CALIBRE_LIBRARY_PATH` to your exact path.

### "Authentication required" error

Verify `SYNC_TOKEN` matches in both the sync script and Railway/Render environment variables.

### Books missing page counts

Install the Count Pages plugin in Calibre for automatic page count detection.

## How It Works

1. **Local sync script** reads your Calibre database directly
2. **Extracts metadata** including ratings, tags, page counts
3. **Syncs to cloud** via authenticated POST request
4. **TRMNL polls** your cloud service for updates
5. **Displays** formatted data on your e-ink screen

## API Endpoints

Your deployed service provides:
- `/health` - Service health check
- `/debug` - Configuration and sample data
- `/trmnl-recent` - Book data for TRMNL (requires sync)
- `/sync` - Receives data from sync script (authenticated)

## Support

- TRMNL Help: [help.usetrmnl.com](https://help.usetrmnl.com)
- Calibre Documentation: [manual.calibre-ebook.com](https://manual.calibre-ebook.com)
- Issues: Use the GitHub issues tab

## License

MIT License - See LICENSE file
