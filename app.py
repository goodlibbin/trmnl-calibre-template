"""
TRMNL Calibre Library Plugin - Railway Cloud Component

This runs on Railway and serves book data to TRMNL.
Book metadata is synced from your local machine via the /sync endpoint.
"""

import os
import json
import random
from datetime import datetime, timedelta
from flask import Flask, jsonify, request

app = Flask(__name__)

# Configuration
SYNC_TOKEN = os.environ.get('SYNC_TOKEN', 'your-secret-sync-token-here')
BOOKS_FILE = 'books_data.json'

def load_books_data():
    """Load book data from JSON file."""
    try:
        if os.path.exists(BOOKS_FILE):
            with open(BOOKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading books data: {e}")
    
    # Return empty structure if no data
    return {
        "books": [],
        "last_updated": None,
        "total_books": 0
    }

def save_books_data(data):
    """Save book data to JSON file."""
    try:
        with open(BOOKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving books data: {e}")
        return False

def categorize_books(books, book_limit=10):
    """Categorize books by date and format for TRMNL."""
    now = datetime.now()
    one_week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    this_week_books = []
    last_week_books = []
    earlier_books = []

    for book in books:
        # Parse timestamp
        try:
            if isinstance(book['timestamp'], str):
                timestamp_str = book['timestamp']
                if '+' in timestamp_str:
                    timestamp_str = timestamp_str.split('+')[0]
                if 'T' in timestamp_str:
                    timestamp_str = timestamp_str.replace('T', ' ')
                timestamp = datetime.fromisoformat(timestamp_str)
            else:
                timestamp = datetime.fromisoformat(str(book['timestamp']).replace('T', ' ').split('+')[0])
        except Exception as e:
            print(f"⚠️  Error parsing timestamp for {book.get('title', 'Unknown')}: {e}")
            timestamp = datetime.now() - timedelta(days=30)  # Default to older

        # Format rating as stars
        stars = "★" * int(book['rating']) if book['rating'] else ""

        # Create book data for TRMNL
        book_data = {
            "index": len(this_week_books) + len(last_week_books) + len(earlier_books) + 1,
            "title": book['title'],
            "author": book['author'],
            "tags": book['tags'],
            "rating": stars,
            "has_rating": bool(book['rating']),
            "description": book['description'],
            "page_count": book['page_count']
        }

        # Categorize by date
        if timestamp >= one_week_ago:
            if len(this_week_books) < book_limit:
                this_week_books.append(book_data)
        elif timestamp >= two_weeks_ago:
            if len(last_week_books) < book_limit:
                last_week_books.append(book_data)
        else:
            if len(earlier_books) < book_limit:
                earlier_books.append(book_data)

    return this_week_books, last_week_books, earlier_books

@app.route('/')
def home():
    """API information."""
    books_data = load_books_data()
    
    return jsonify({
        "name": "TRMNL Calibre Library Plugin - Railway Cloud",
        "version": "3.0.0",
        "description": "Cloud-hosted Calibre library API for TRMNL e-ink devices",
        "status": "✅ Cloud service ready",
        "total_books": books_data.get("total_books", 0),
        "last_updated": books_data.get("last_updated"),
        "endpoints": {
            "/calibre-status": "Main data endpoint for TRMNL",
            "/sync": "Book data sync endpoint (POST with token)",
            "/health": "Service health check"
        },
        "data_source": "Railway Cloud + Local Sync"
    })

@app.route('/health')
def health():
    """Health check endpoint."""
    books_data = load_books_data()
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "total_books": books_data.get("total_books", 0),
        "last_updated": books_data.get("last_updated"),
        "service": "Railway Cloud"
    })

@app.route('/sync', methods=['POST'])
def sync_books():
    """Endpoint for local script to sync book data."""
    # Verify sync token
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {SYNC_TOKEN}":
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # Get book data from request
        sync_data = request.get_json()
        if not sync_data or 'books' not in sync_data:
            return jsonify({"error": "Invalid data format"}), 400

        # Add metadata
        books_data = {
            "books": sync_data['books'],
            "last_updated": datetime.now().isoformat(),
            "total_books": len(sync_data['books']),
            "sync_source": sync_data.get('source', 'local')
        }

        # Save to file
        if save_books_data(books_data):
            print(f"✅ Synced {len(sync_data['books'])} books at {books_data['last_updated']}")
            return jsonify({
                "message": "Books synced successfully",
                "books_count": len(sync_data['books']),
                "timestamp": books_data['last_updated']
            })
        else:
            return jsonify({"error": "Failed to save book data"}), 500

    except Exception as e:
        print(f"❌ Sync error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/calibre-status', methods=['GET', 'POST'])
def calibre_status():
    """Main endpoint for TRMNL integration."""
    try:
        # Load book data
        books_data = load_books_data()
        books = books_data.get('books', [])

        if not books:
            return jsonify({
                "empty_library": True,
                "server_connected": True,
                "message": "No book data available. Sync from your local Calibre library.",
                "this_week_books": [],
                "last_week_books": [],
                "earlier_books": [],
                "this_week_count": 0,
                "last_week_count": 0,
                "earlier_count": 0,
                "book_suggestion": None,
                "total_books_found": 0,
                "current_time": datetime.now().strftime("%m/%d %H:%M"),
                "last_sync": books_data.get('last_updated', 'Never'),
                "data_source": "Railway Cloud"
            })

        # Extract configuration
        book_limit = 10
        if request.method == 'POST':
            data = request.get_json() or {}
            book_limit = int(data.get('book_limit', 10))
        else:
            book_limit = int(request.args.get('book_limit', 10))

        book_limit = max(1, min(book_limit, 50))

        # Categorize books
        this_week_books, last_week_books, earlier_books = categorize_books(books, book_limit)

        # Random book suggestion
        all_books = this_week_books + last_week_books + earlier_books
        book_suggestion = random.choice(all_books) if all_books else None

        result = {
            "empty_library": False,
            "server_connected": True,
            "this_week_books": this_week_books,
            "last_week_books": last_week_books,
            "earlier_books": earlier_books,
            "this_week_count": len(this_week_books),
            "last_week_count": len(last_week_books),
            "earlier_count": len(earlier_books),
            "book_suggestion": book_suggestion,
            "total_books_found": len(books),
            "current_time": datetime.now().strftime("%m/%d %H:%M"),
            "last_sync": books_data.get('last_updated'),
            "data_source": "Railway Cloud"
        }

        return jsonify(result)

    except Exception as e:
        print(f"❌ Error in calibre_status: {str(e)}")
        return jsonify({
            "error": f"Service error: {str(e)}",
            "empty_library": True,
            "server_connected": True,
            "message": "Service error occurred. Check logs.",
            "current_time": datetime.now().strftime("%m/%d %H:%M")
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
