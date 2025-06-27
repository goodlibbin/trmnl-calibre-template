# TRMNL Calibre Library Plugin

Display your Calibre-web library status on TRMNL e-ink devices. Shows latest books, library stats, ratings, and tags with beautiful e-ink optimized design.

## Features

- 📚 **Latest Book Display**: Shows your most recently added book
- ⭐ **Rating Integration**: Displays book ratings from your library  
- 🏷️ **Tag Support**: Shows book categories and genres
- 📊 **Library Statistics**: Tracks total books and rating percentages
- ⚡ **Optimized for TRMNL**: Clean JSON data API designed for TRMNL's template system
- 🧠 **Intelligent Caching**: Reduces server load with 5-minute caching
- 📱 **Multiple Layouts**: Works with Full, Half-Horizontal, Half-Vertical, and Quadrant layouts

## Quick Setup

### 1. Deploy to Render/Railway

- Fork this repository
- Connect to [Render](https://render.com) or [Railway](https://railway.app)
- Create new Web Service from your fork
- Use `python app.py` as the start command

### 2. Configure Your Calibre-web Server

- Open `app.py` in your deployed repository
- Find the "USER CONFIGURATION" section at the top
- Replace the placeholder values:

```python
# USER CONFIGURATION - UPDATE THESE VALUES WITH YOUR OWN
# =======================================================
# Your Calibre-web server URL
CALIBRE_BASE_URL = "http://your-server:8083"
# Your library ID (usually "Calibre_Library")
LIBRARY_ID = "Calibre_Library" 
# =======================================================
```

- Save and redeploy your app

### 3. Test Your Setup

- Visit your deployed URL: `https://your-app.render.com/trmnl-data`
- You should see JSON data with your book information
- If you see errors, check the `/debug` endpoint for troubleshooting

### 4. Configure TRMNL

#### Option A: Use as Private Plugin
- Create a Private Plugin in TRMNL
- Set strategy to "Polling"
- Set polling URL to: `https://your-app.render.com/trmnl-data`
- Copy your preferred template markup from examples below
- Paste into markup editor and save

#### Option B: Install from TRMNL Store (if published)
- Install the "Calibre Library Status" plugin from TRMNL
- Enter your backend URL: `https://your-app.render.com`
- Choose your layout preference
- Save and enjoy!

## Template Examples

This backend provides clean JSON data that works with TRMNL's template system. Here are example templates for different layout sizes:

### Full Layout Template

```html
<div class="layout">
<div class="columns">
<div class="column">
<!-- Centered Title with Border -->
<div class="richtext richtext--center mb--3">
<div class="content content--large clamp--3 text--center p--2" data-pixel-perfect="true" style="font-weight: bold; border: 2px solid black;">{{ title }}</div>
</div>

<!-- Data Table -->
<table class="table">
<tbody>
<tr>
<td class="w--32"><span class="title title--medium">Author</span></td>
<td><span class="label clamp--1">{{ author }}</span></td>
</tr>
<tr>
<td><span class="title title--medium">Rating</span></td>
<td><span class="label">{{ rating }}</span></td>
</tr>
<tr>
<td><span class="title title--medium">Tags</span></td>
<td><span class="label clamp--1">{{ tags }}</span></td>
</tr>
<tr>
<td><span class="title title--medium">Library</span></td>
<td>
<span class="label">{{ total_books }} books</span>
<div style="width: 100%; height: 8px; border: 1px solid black; background: white; position: relative; margin-top: 3px;">
<div style="position: absolute; background: black; height: 100%; width: {{ rating_percentage }}%;"></div>
</div>
<span class="label" style="font-size: 0.8em;">{{ rated_books }} rated ({{ rating_percentage }}%)</span>
</td>
</tr>
<tr>
<td><span class="title title--medium">Status</span></td>
<td><span class="label">{{ server_status }}</span></td>
</tr>
</tbody>
</table>
</div>
</div>
</div>

<div class="title_bar">
<img class="image" src="https://usetrmnl.com/images/plugins/trmnl--render.svg">
<span class="title">Calibre Library</span>
<span class="instance">{{ current_time }}</span>
</div>
```

### Half Layout Template

```html
<div class="title_bar">
<img class="image" src="https://usetrmnl.com/images/plugins/trmnl--render.svg">
<span class="title">Calibre</span>
<span class="instance">{{ current_time }}</span>
</div>

<div class="layout layout--col layout--top gap--small">
<div class="w-full">
<!-- Centered Title -->
<div class="richtext richtext--center mb--2">
<div class="content content--medium clamp--2 text--center p--1" data-pixel-perfect="true" style="font-weight: bold; border: 1px solid black;">{{ title }}</div>
</div>

<!-- Compact Data -->
<table class="table">
<tbody>
<tr>
<td class="w--32"><span class="title title--small">Author</span></td>
<td><span class="label clamp--1">{{ author }}</span></td>
</tr>
<tr>
<td><span class="title title--small">Rating</span></td>
<td><span class="label">{{ rating }}</span></td>
</tr>
<tr>
<td><span class="title title--small">Library</span></td>
<td>
<span class="label">{{ total_books }} books</span>
<div style="width: 100%; height: 6px; border: 1px solid black; background: white; position: relative; margin-top: 2px;">
<div style="position: absolute; background: black; height: 100%; width: {{ rating_percentage }}%;"></div>
</div>
</td>
</tr>
</tbody>
</table>
</div>
</div>
```

## JSON Data Format

The `/trmnl-data` endpoint returns data in this format:

```json
{
  "title": "Feel-Good Productivity: How to Do More...",
  "author": "Ali Abdaal",
  "rating": "★★★★",
  "tags": "Business, Psychology",
  "total_books": 10,
  "rated_books": 8,
  "rating_percentage": 80,
  "server_status": "Connected",
  "last_update": "06/26 17:42",
  "current_time": "06/26 17:42"
}
```

## API Endpoints

- `/trmnl-data` - Main JSON data endpoint for TRMNL templates
- `/debug` - System diagnostics and data inspection  
- `/health` - Health check and connection status
- `/clear-cache` - Force fresh data fetch
- `/api/recent` - Legacy endpoint (backwards compatibility)

## Troubleshooting

### Plugin Shows "Library Offline"
- Ensure you've updated `CALIBRE_BASE_URL` in `app.py`
- Verify your Calibre-web server is accessible from the internet
- Check that your server URL format is correct (include http:// or https://)
- Test the `/debug` endpoint to see connection details

### No Books Showing
- Verify your Calibre library has books with recent additions
- Check that your `LIBRARY_ID` matches your Calibre-web setup
- Test the OPDS feed URL directly in your browser
- Use `/debug` endpoint to see what data is being found

### Template Not Displaying Correctly
- Verify your polling URL points to `/trmnl-data`
- Check the JSON response format matches expected template variables
- Test different layout templates to find what works best
- Ensure your TRMNL device has internet connectivity

## Updating Your Deployment

To update your deployment with the latest features:

- Check this repository for updates
- Compare with your deployed version  
- Update your `app.py` with new features (keep your personal configuration)
- Redeploy your app

## How It Works

- **OPDS Parsing**: Fetches your Calibre-web OPDS feed every 5 minutes
- **Data Extraction**: Parses book metadata, ratings, and tags
- **Smart Caching**: Caches data to reduce server load
- **JSON API**: Provides clean data for TRMNL's template system
- **Template Ready**: Optimized for e-ink display rendering

## Contributing

This is an open-source project! Feel free to:

- Report issues
- Suggest improvements  
- Submit pull requests
- Share your layout customizations

## License

MIT License - feel free to modify for your own use!

## Credits

- Built for the [TRMNL](https://usetrmnl.com) e-ink display community
- Inspired by beautiful, automated library tracking
- Thanks to Calibre and Calibre-web for providing excellent library management

Enjoy tracking your library! 📚✨

For more TRMNL templates and projects, visit the [TRMNL community](https://usetrmnl.com).
