# Quick Setup Guide

## 5-Minute Setup

### 1️⃣ Fork the TRMNL Recipe
- Go to https://usetrmnl.com/recipes
- Find "Calibre Library Status"
- Click **Fork** (requires Developer Edition)

### 2️⃣ Deploy to Railway
- Fork this GitHub repo
- Sign up at https://railway.app
- New Project → Deploy from GitHub repo
- Add environment variable: `SYNC_TOKEN=mysecrettoken123`
- Deploy → Copy your app URL

### 3️⃣ Configure Sync Script
- Download `sync_to_cloud.py`
- Edit these 3 lines:
  ```python
  CLOUD_URL = "https://your-app.up.railway.app"
  SYNC_TOKEN = "mysecrettoken123"
  CALIBRE_PATH = "~/Calibre Library"
  ```

### 4️⃣ Run First Sync
```bash
python sync_to_cloud.py
```

### 5️⃣ Configure TRMNL
- Go back to your forked plugin
- Set Polling URL: `https://your-app.up.railway.app/trmnl-recent`
- Click "Force Refresh"
- Save

## That's it! 🎉

Your books should now appear on your TRMNL device.

![TRMNL Calibre Display MockUp](https://github.com/goodlibbin/trmnl-calibre-template/blob/main/calibrelive.jpeg)

## Next Steps

For automatic syncing every 30 minutes:
```bash
# Install dependencies
pip install requests schedule

# Run the full sync script
python sync_to_railway.py
# Choose option 2
```

## Troubleshooting

**No books showing?**
- Check: `https://your-app.up.railway.app/health`
- Verify sync script shows "✅ Sync successful!"

**Can't find Calibre database?**
- Update `CALIBRE_PATH` to your exact library location
- Common locations:
  - Windows: `C:\Users\YourName\Calibre Library`
  - macOS: `/Users/YourName/Calibre Library`
  - Linux: `/home/YourName/Calibre Library`

**Need help?**
- Check the full README.md
