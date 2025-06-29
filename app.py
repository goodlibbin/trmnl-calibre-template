"""
TRMNL Calibre Library Plugin - Cloud Service

A cloud-hosted service that syncs with your local Calibre library
and provides formatted book data for TRMNL e-ink displays.
"""

import os
import json
import random
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from flask import Flask, jsonify, request

app = Flask(__name__)

# Configuration
SYNC_TOKEN = os.environ.get('SYNC_TOKEN', 'your-secret-sync-token-here')
BOOKS_FILE = 'books_data.json'
CALIBRE_WEB_URL = os.environ.get('CALIBRE_WEB_URL', '')  # Optional for direct OPDS access

def load_books_data():
    """Load book data from persistent storage."""
    try:
        if os.path.exists(BOOKS_FILE):
            with open(BOOKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading books data: {e}")
    
    return {
        "books": [],
        "last_updated": None,
        "total_books": 0,
        "source": "none"
    }

def save_books_data(data):
    """Save book data to persistent storage."""
    try:
        with open(BOOKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving books data: {e}")
        return False

def fetch_opds_books(base_url, library_id="Calibre_Library"):
    """Fetch books directly from Calibre-web OPDS feed if configured."""
    if not base_url:
        return None
    
    try:
        # Try to get the newest books feed
        newest_url = f"{base_url}/opds/navcatalog/4f6e6577657374?library_id={library_id}"
        
        response = requests.get(newest_url, timeout=10)
        response.raise_for_status()
        
        # Parse OPDS XML
        root = ET.fromstring(response.content)
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'dc': 'http://purl.org/dc/terms/'
        }
        
        books = []
        entries = root.findall('atom:entry', namespaces)
        
        for entry in entries:
            try:
                # Skip navigation entries
                if entry.find('.//atom:link[@type="application/atom+xml;type=feed;profile=opds-catalog"]', namespaces):
                    continue
                
                title = entry.find('atom:title', namespaces)
                title = title.text if title is not None else "Unknown"
                
                author = entry.find('atom:author/atom:name', namespaces)
                author = author.text if author is not None else "Unknown"
                
                updated = entry.find('atom:updated', namespaces)
                timestamp = updated.text if updated is not None else datetime.now().isoformat()
                
                # Extract rating from content if available
                rating = 0
                content = entry.find('atom:content', namespaces)
                if content is not None and content.text:
                    if 'Rating:' in content.text:
                        try:
                            rating_text = content.text.split('Rating:')[1].split('<')[0].strip()
                            rating = int(float(rating_text))
                        except:
                            pass
                
                # Get tags from categories
                categories = entry.findall('atom:category', namespaces)
                tags = [cat.get('label', '') for cat in categories if cat.get('label')]
                
                books.append({
                    'title': title,
                    'author': author,
                    'timestamp': timestamp,
                    'rating': rating,
                    'tags': ', '.join(tags[:3]),
                    'description': '',
                    'page_count': None
                })
                
            except Exception as e:
                continue
        
        return books
        
    except Exception as e:
        print(f"OPDS fetch error: {e}")
        return None

@app.route('/')
def home():
    """Service information and status."""
    books_data = load_books_data()
    
    return jsonify({
        "service": "TRMNL Calibre Library Plugin",
        "version": "3.0.0",
        "description": "Cloud service for syncing Calibre library data to TRMNL displays",
        "status": {
            "operational": True,
            "total_books": books_data.get("total_books", 0),
            "last_updated": books_data.get("last_updated"),
            "data_source": books_data.get("source", "none")
        },
        "endpoints": {
            "/calibre-status": "Book data for TRMNL display",
            "/sync": "Sync endpoint for local library updates",
            "/health": "Service health check"
        }
    })

@app.route('/health')
def health():
    """Health check endpoint for monitoring."""
    books_data = load_books_data()
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "total_books": books_data.get("total_books", 0),
            "last_sync": books_data.get("last_updated"),
            "data_source": books_data.get("source", "none")
        }
    })

@app.route('/sync', methods=['POST'])
def sync_books():
    """Receive book data from local Calibre sync script."""
    # Verify authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {SYNC_TOKEN}":
        return jsonify({"error": "Unauthorized"}), 401

    try:
        sync_data = request.get_json()
        if not sync_data or 'books' not in sync_data:
            return jsonify({"error": "Invalid data format"}), 400

        # Store synced data
        books_data = {
            "books": sync_data['books'],
            "last_updated": datetime.now().isoformat(),
            "total_books": len(sync_data['books']),
            "source": sync_data.get('source', 'local_sync')
        }

        if save_books_data(books_data):
            return jsonify({
                "success": True,
                "message": "Books synced successfully",
                "books_synced": len(sync_data['books']),
                "timestamp": books_data['last_updated']
            })
        else:
            return jsonify({"error": "Failed to save book data"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/calibre-status', methods=['GET', 'POST'])
@app.route('/trmnl-data', methods=['GET', 'POST'])
def calibre_status():
    """Provide formatted book data for TRMNL display."""
    try:
        # Load stored book data
        books_data = load_books_data()
        books = books_data.get('books', [])
        
        # Optionally try OPDS if no local data
        if not books and CALIBRE_WEB_URL:
            opds_books = fetch_opds_books(CALIBRE_WEB_URL)
            if opds_books:
                books = opds_books
                books_data['source'] = 'opds_direct'

        # Calculate library statistics
        total_books = len(books)
        rated_books = sum(1 for book in books if book.get('rating', 0) > 0)
        rating_percentage = int((rated_books / total_books * 100)) if total_books > 0 else 0

        # Get display data from latest book
        if books:
            latest = books[0]
            display_data = {
                "title": latest.get('title', 'Unknown')[:50],
                "author": latest.get('author', 'Unknown'),
                "rating": "★" * int(latest.get('rating', 0)) if latest.get('rating') else "Not rated",
                "tags": latest.get('tags', 'No tags')[:40],
                "total_books": total_books,
                "rated_books": rated_books,
                "rating_percentage": rating_percentage,
                "server_status": "Connected",
                "current_time": datetime.now().strftime("%m/%d %H:%M"),
                "last_update": books_data.get('last_updated', 'Never')
            }
        else:
            # Empty library state
            display_data = {
                "title": "No Books Found",
                "author": "Sync your Calibre library",
                "rating": "",
                "tags": "",
                "total_books": 0,
                "rated_books": 0,
                "rating_percentage": 0,
                "server_status": "No Data",
                "current_time": datetime.now().strftime("%m/%d %H:%M"),
                "last_update": "Never"
            }

        return jsonify(display_data)

    except Exception as e:
        return jsonify({
            "title": "Service Error",
            "author": "Please check configuration",
            "rating": "",
            "tags": "",
            "total_books": 0,
            "rated_books": 0,
            "rating_percentage": 0,
            "server_status": "Error",
            "current_time": datetime.now().strftime("%m/%d %H:%M"),
            "error": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting TRMNL Calibre Library service on port {port}")
    app.run(host='0.0.0.0', port=port)
