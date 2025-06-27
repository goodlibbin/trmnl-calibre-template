#!/usr/bin/env python3
"""
TRMNL Calibre-web Plugin
Display your Calibre library status on TRMNL e-ink devices
"""

from flask import Flask, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import random
import os

app = Flask(__name__)

# USER CONFIGURATION - UPDATE THESE VALUES WITH YOUR OWN
# =======================================================
# Your Calibre-web server URL (update with your actual server)
CALIBRE_BASE_URL = "http://[::1]:8080"
# Your library ID (usually "Calibre_Library")  
LIBRARY_ID = "Calibre_Library"

# TESTING MODE - Set to False when connecting to real Calibre server
USE_MOCK_DATA = True
# =======================================================

# Cache to avoid hitting server too frequently
CACHE = {
    'books': None,
    'books_timestamp': None,
    'cache_duration': 300  # 5 minutes
}

def is_cache_valid():
    """Check if cached data is still valid"""
    if CACHE['books_timestamp'] is None:
        return False
    
    time_diff = (datetime.now() - CACHE['books_timestamp']).total_seconds()
    return time_diff < CACHE['cache_duration']

def get_newest_books():
    """Get newest books from Calibre-web with caching"""
    
    # MOCK DATA FOR TESTING - Remove this when connecting to real Calibre server
    if USE_MOCK_DATA:
        today = datetime.now()
        this_week = today - timedelta(days=2)
        last_week = today - timedelta(days=8)
        
        mock_books = [
            {
                'title': 'Feel-Good Productivity: How to Do More of What Matters to You',
                'author': 'Ali Abdaal',
                'rating': '★★★★',
                'tags': ['Business', 'Psychology', 'Self Help'],
                'published': this_week.isoformat(),
                'date_added': this_week
            },
            {
                'title': 'Storytelling with Data',
                'author': 'Cole Nussbaumer Knaflic',
                'rating': '★★★★',
                'tags': ['Business', 'Reference', 'Science'],
                'published': this_week.isoformat(),
                'date_added': this_week
            },
            {
                'title': 'How to Take Smart Notes',
                'author': 'Sönke Ahrens',
                'rating': '★★★★',
                'tags': ['Business', 'Non-Fiction', 'Psychology'],
                'published': this_week.isoformat(),
                'date_added': this_week
            },
            {
                'title': 'The Attachment Theory Workbook',
                'author': 'Annie Chen LMFT',
                'rating': '★★★★★',
                'tags': ['Psychology', 'Self Help', 'Relationships'],
                'published': this_week.isoformat(),
                'date_added': this_week
            },
            {
                'title': 'The Water Dancer',
                'author': 'Ta-Nehisi Coates',
                'rating': 'Not rated',
                'tags': ['Fiction', 'Historical', 'African American'],
                'published': last_week.isoformat(),
                'date_added': last_week
            },
            {
                'title': 'The Shyness and Social Anxiety Workbook',
                'author': 'Martin M. Antony PhD',
                'rating': '★★★★',
                'tags': ['Non-Fiction', 'Psychology', 'Self Help'],
                'published': last_week.isoformat(),
                'date_added': last_week
            },
            {
                'title': 'The CBT Workbook for Perfectionism',
                'author': 'Sharon Martin DSW',
                'rating': '★★★★',
                'tags': ['Psychology', 'Self Help'],
                'published': last_week.isoformat(),
                'date_added': last_week
            },
            {
                'title': 'Man\'s Search for Meaning',
                'author': 'Viktor E. Frankl',
                'rating': '★★★★',
                'tags': ['Biography', 'Philosophy', 'Psychology'],
                'published': (today - timedelta(days=20)).isoformat(),
                'date_added': today - timedelta(days=20)
            },
            {
                'title': 'Atomic Habits',
                'author': 'James Clear',
                'rating': '★★★★★',
                'tags': ['Self Help', 'Psychology', 'Business'],
                'published': (today - timedelta(days=25)).isoformat(),
                'date_added': today - timedelta(days=25)
            },
            {
                'title': 'The 7 Habits of Highly Effective People',
                'author': 'Stephen R. Covey',
                'rating': '★★★★★',
                'tags': ['Self Help', 'Business', 'Leadership'],
                'published': (today - timedelta(days=30)).isoformat(),
                'date_added': today - timedelta(days=30)
            },
            {
                'title': 'Sapiens: A Brief History of Humankind',
                'author': 'Yuval Noah Harari',
                'rating': '★★★★',
                'tags': ['History', 'Philosophy', 'Science'],
                'published': (today - timedelta(days=35)).isoformat(),
                'date_added': today - timedelta(days=35)
            }
        ]
        
        # Cache the mock results
        CACHE['books'] = mock_books
        CACHE['books_timestamp'] = datetime.now()
        
        return CACHE['books']
    
    # REAL CALIBRE-WEB CONNECTION - This will be used when USE_MOCK_DATA = False
    # Return cached data if valid
    if is_cache_valid() and CACHE['books']:
        return CACHE['books']
    
    try:
        url = f"{CALIBRE_BASE_URL}/opds/navcatalog/4f6e6577657374?library_id={LIBRARY_ID}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse the XML feed
        root = ET.fromstring(response.content)
        books = []
        
        # Extract book information
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title_elem = entry.find('.//{http://www.w3.org/2005/Atom}title')
            author_elem = entry.find('.//{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name')
            content_elem = entry.find('.//{http://www.w3.org/2005/Atom}content')
            published_elem = entry.find('.//{http://www.w3.org/2005/Atom}published')
            
            if title_elem is not None and title_elem.text:
                book_info = {
                    'title': title_elem.text,
                    'author': author_elem.text if author_elem is not None else 'Unknown Author',
                    'published': published_elem.text if published_elem is not None else '',
                }
                
                # Parse published date for grouping
                if published_elem is not None and published_elem.text:
                    try:
                        book_info['date_added'] = datetime.fromisoformat(published_elem.text.replace('Z', '+00:00'))
                    except:
                        book_info['date_added'] = datetime.now()
                else:
                    book_info['date_added'] = datetime.now()
                
                # Extract rating and tags from content if available
                if content_elem is not None and content_elem.text:
                    content = content_elem.text
                    
                    # Extract rating
                    if 'RATING:' in content:
                        rating_start = content.find('RATING:') + 8
                        rating_end = content.find('<br/>', rating_start)
                        if rating_end > rating_start:
                            book_info['rating'] = content[rating_start:rating_end].strip()
                    
                    # Extract tags
                    if 'TAGS:' in content:
                        tags_start = content.find('TAGS:') + 6
                        tags_end = content.find('<br/>', tags_start)
                        if tags_end > tags_start:
                            tags = content[tags_start:tags_end].strip()
                            book_info['tags'] = tags.split(', ')[:3]  # First 3 tags
                
                books.append(book_info)
                
        # Cache the results
        CACHE['books'] = books[:15]  # Keep top 15
        CACHE['books_timestamp'] = datetime.now()
        
        return CACHE['books']
        
    except Exception as e:
        print(f"Error getting books from Calibre-web: {e}")
        # Return cached data if available, even if expired
        return CACHE['books'] if CACHE['books'] else []

def get_random_book_suggestion():
    """Get a random book suggestion for 'Try This Next'"""
    books = get_newest_books()
    if not books:
        return None
    
    # Filter for books that aren't marked as "currently reading" 
    # For now, we'll just pick a random book from the collection
    available_books = [book for book in books if book.get('rating') != 'Currently Reading']
    
    if not available_books:
        available_books = books  # Fallback to all books
    
    suggestion = random.choice(available_books)
    return {
        'title': suggestion['title'][:35] + ('...' if len(suggestion['title']) > 35 else ''),
        'author': suggestion['author'][:20] + ('...' if len(suggestion['author']) > 20 else ''),
        'tags': ', '.join(suggestion.get('tags', [])[:2]) if suggestion.get('tags') else 'No tags'
    }

def group_books_by_week():
    """Group books by week for list display"""
    books = get_newest_books()
    if not books:
        return {}
    
    today = datetime.now()
    this_week_start = today - timedelta(days=7)
    last_week_start = today - timedelta(days=14)
    
    groups = {
        'this_week': [],
        'last_week': [],
        'earlier': []
    }
    
    for book in books:
        book_date = book.get('date_added', datetime.now())
        if isinstance(book_date, str):
            book_date = datetime.fromisoformat(book_date.replace('Z', '+00:00'))
        
        if book_date >= this_week_start:
            groups['this_week'].append(book)
        elif book_date >= last_week_start:
            groups['last_week'].append(book)
        else:
            groups['earlier'].append(book)
    
    return groups

def get_library_stats():
    """Get library statistics"""
    books = get_newest_books()
    
    if not books:
        return None
    
    # Count books with actual ratings (not "Not rated")
    rated_books = len([book for book in books if book.get('rating') and book.get('rating') != 'Not rated'])
    total_books = len(books)
    
    # Get the most recent book
    latest_book = books[0] if books else None
    
    return {
        'total_recent_books': total_books,
        'rated_books': rated_books,
        'latest_book': latest_book,
        'server_status': 'Connected (Mock Data)' if USE_MOCK_DATA else 'Connected',
        'last_update': datetime.now().strftime('%m/%d %H:%M')
    }

@app.route('/trmnl-data')
def trmnl_data():
    """Main TRMNL data endpoint - returns JSON for template system"""
    
    try:
        books = get_newest_books()
        book_groups = group_books_by_week()
        stats = get_library_stats()
        
        # Handle empty library case
        if not books:
            return jsonify({
                'empty_library': True,
                'message': 'Start adding books to your Calibre library to get started!',
                'title': 'Empty Library',
                'current_time': datetime.now().strftime('%m/%d %H:%M')
            })
        
        if not stats:
            return jsonify({
                'error': 'Unable to fetch library data',
                'title': 'Library Offline',
                'status': 'error',
                'current_time': datetime.now().strftime('%m/%d %H:%M')
            })
        
        # Format books for list display
        def format_book_for_display(book, index):
            return {
                'index': index,
                'title': book['title'],
                'author': book['author'],
                'rating': book.get('rating', 'Not rated'),
                'tags': ', '.join(book.get('tags', [])[:2]) if book.get('tags') else 'No tags',
                'has_rating': book.get('rating') and book.get('rating') != 'Not rated'
            }
        
        # Check if we have any books to show
        has_recent_books = len(book_groups['this_week']) > 0 or len(book_groups['last_week']) > 0
        
        # Get book suggestion for Try This Next
        book_suggestion = get_random_book_suggestion()
        
        # Format the response for TRMNL templates
        response_data = {
            'empty_library': False,
            'has_recent_books': has_recent_books,
            'this_week_books': [format_book_for_display(book, i+1) for i, book in enumerate(book_groups['this_week'])],
            'last_week_books': [format_book_for_display(book, i+1) for i, book in enumerate(book_groups['last_week'])],
            'earlier_books': [format_book_for_display(book, i+1) for i, book in enumerate(book_groups['earlier'][:6])],  # Limit to 6 earlier books
            'this_week_count': len(book_groups['this_week']),
            'last_week_count': len(book_groups['last_week']),
            'earlier_count': len(book_groups['earlier']),
            'total_books': stats['total_recent_books'],
            'rated_books': stats['rated_books'],
            'rating_percentage': round((stats['rated_books'] / stats['total_recent_books']) * 100) if stats['total_recent_books'] > 0 else 0,
            'server_status': stats['server_status'],
            'current_time': datetime.now().strftime('%m/%d %H:%M'),
            'book_suggestion': book_suggestion
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'title': 'Error',
            'status': 'error',
            'current_time': datetime.now().strftime('%m/%d %H:%M')
        }), 500

@app.route('/trmnl-data-empty')
def trmnl_data_empty():
    """Mock empty library for testing the welcome state"""
    return jsonify({
        'empty_library': True,
        'message': 'Start adding books to your Calibre library to get started!',
        'title': 'Empty Library',
        'current_time': datetime.now().strftime('%m/%d %H:%M')
    })

@app.route('/trmnl-data-simple')
def trmnl_data_simple():
    """Simple single-book display for comparison"""
    
    try:
        books = get_newest_books()
        stats = get_library_stats()
        
        if not books or not stats:
            return jsonify({
                'error': 'Unable to fetch library data',
                'title': 'Library Offline',
                'status': 'error',
                'current_time': datetime.now().strftime('%m/%d %H:%M')
            })
        
        latest_book = stats['latest_book']
        
        # Format the response for TRMNL templates (original format)
        response_data = {
            'title': latest_book['title'][:50] + ('...' if len(latest_book['title']) > 50 else ''),
            'author': latest_book['author'],
            'rating': latest_book.get('rating', 'Not rated'),
            'tags': ', '.join(latest_book.get('tags', [])[:2]) if latest_book.get('tags') else 'No tags',
            'total_books': stats['total_recent_books'],
            'rated_books': stats['rated_books'],
            'rating_percentage': round((stats['rated_books'] / stats['total_recent_books']) * 100) if stats['total_recent_books'] > 0 else 0,
            'server_status': stats['server_status'],
            'last_update': stats['last_update'],
            'current_time': datetime.now().strftime('%m/%d %H:%M')
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'title': 'Error',
            'status': 'error',
            'current_time': datetime.now().strftime('%m/%d %H:%M')
        }), 500

@app.route('/api/recent')
def api_recent():
    """Legacy endpoint for backwards compatibility"""
    books = get_newest_books()
    
    if not books:
        return jsonify({
            'success': False,
            'error': 'Could not fetch books from Calibre-web'
        })
    
    content = []
    content.append("📚 Recently Added Books")
    content.append("")
    
    # Show top 5 recent books
    for i, book in enumerate(books[:5], 1):
        title = book['title']
        if len(title) > 35:
            title = title[:32] + "..."
        
        author = book['author']
        if len(author) > 25:
            author = author[:22] + "..."
            
        rating = book.get('rating', '')
        rating_display = f" {rating}" if rating and rating != 'Not rated' else ""
        
        content.append(f"{i}. {title}")
        content.append(f"   by {author}{rating_display}")
        if i < 5:
            content.append("")
    
    return jsonify({
        'success': True,
        'data': {
            'title': 'Recent Additions',
            'content': content
        }
    })

@app.route('/debug')
def debug():
    """Debug endpoint to see raw data"""
    books = get_newest_books()
    book_groups = group_books_by_week()
    stats = get_library_stats()
    
    return jsonify({
        'books_count': len(books) if books else 0,
        'latest_books': books[:3] if books else [],
        'book_groups': book_groups,
        'book_suggestion': get_random_book_suggestion(),
        'stats': stats,
        'cache_status': {
            'is_valid': is_cache_valid(),
            'timestamp': CACHE['books_timestamp'].isoformat() if CACHE['books_timestamp'] else None
        },
        'config': {
            'calibre_url': CALIBRE_BASE_URL,
            'library_id': LIBRARY_ID,
            'use_mock_data': USE_MOCK_DATA
        },
        'mode': 'mock_data' if USE_MOCK_DATA else 'live_calibre'
    })

@app.route('/clear-cache')
def clear_cache():
    """Clear cache to force fresh data"""
    CACHE['books'] = None
    CACHE['books_timestamp'] = None
    return jsonify({'status': 'Cache cleared', 'note': 'Using mock data - cache will reload with same data'})

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        books = get_newest_books()
        is_healthy = len(books) > 0 if books else False
        
        return jsonify({
            'status': 'healthy' if is_healthy else 'unhealthy',
            'calibre_url': CALIBRE_BASE_URL,
            'library_id': LIBRARY_ID,
            'books_found': len(books) if books else 0,
            'mode': 'mock_data' if USE_MOCK_DATA else 'live_calibre',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/')
def index():
    """Index page with setup instructions"""
    mock_status = "Using Mock Data for Testing" if USE_MOCK_DATA else "Connected to Calibre-web"
    mock_warning = """
    <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 10px 0;">
        <strong>🧪 Testing Mode:</strong> Currently using mock data. 
        To connect to your real Calibre server:
        <ol>
            <li>Set <code>USE_MOCK_DATA = False</code> in app.py</li>
            <li>Update <code>CALIBRE_BASE_URL</code> to your server URL</li>
            <li>Redeploy the app</li>
        </ol>
    </div>
    """ if USE_MOCK_DATA else ""
    
    return f"""
    <h1>TRMNL Calibre Plugin</h1>
    <p>Your Calibre-web TRMNL plugin is running!</p>
    
    <h2>Status: {mock_status}</h2>
    <p style="color: green;"><strong>✅ Ready for TRMNL integration!</strong></p>
    
    {mock_warning}
    
    <h2>Endpoints:</h2>
    <ul>
        <li><a href="/trmnl-data">/trmnl-data</a> - Main TRMNL template data (Book Lists)</li>
        <li><a href="/trmnl-data-simple">/trmnl-data-simple</a> - Simple single book display</li>
        <li><a href="/trmnl-data-empty">/trmnl-data-empty</a> - Test empty library state</li>
        <li><a href="/debug">/debug</a> - Debug information</li>
        <li><a href="/health">/health</a> - Health check</li>
        <li><a href="/clear-cache">/clear-cache</a> - Clear cache</li>
        <li><a href="/api/recent">/api/recent</a> - Legacy format</li>
    </ul>
    
    <h2>Configuration:</h2>
    <p>Current Calibre URL: <code>{CALIBRE_BASE_URL}</code></p>
    <p>Current Library ID: <code>{LIBRARY_ID}</code></p>
    <p><strong>Mode: {"Mock Data (Testing)" if USE_MOCK_DATA else "Live Calibre Connection"}</strong></p>
    
    <h2>Display Options:</h2>
    <ol>
        <li><strong>Book Lists</strong>: Use <code>/trmnl-data</code> with the new list template</li>
        <li><strong>Single Book</strong>: Use <code>/trmnl-data-simple</code> with your current template</li>
        <li><strong>Empty State</strong>: Use <code>/trmnl-data-empty</code> to test welcome message</li>
    </ol>
    """

if __name__ == '__main__':
    # Get port from environment variable for deployment compatibility
    port = int(os.environ.get('PORT', 5000))
    
    print("🚀 Starting TRMNL Calibre Plugin...")
    print(f"📚 Calibre-web URL: {CALIBRE_BASE_URL}")
    print(f"📖 Library: {LIBRARY_ID}")
    print(f"🌐 Server starting on port {port}")
    print(f"📝 Mode: {'Mock Data (Testing)' if USE_MOCK_DATA else 'Live Calibre Connection'}")
    
    if USE_MOCK_DATA:
        print("🧪 TESTING MODE: Using mock data for demonstration")
        print("   Set USE_MOCK_DATA = False to connect to real Calibre server")
    
    # Test connection on startup
    print("🔍 Loading data...")
    test_books = get_newest_books()
    if test_books:
        print(f"✅ Success! Loaded {len(test_books)} books")
        groups = group_books_by_week()
        print(f"📅 This week: {len(groups['this_week'])} books")
        print(f"📅 Last week: {len(groups['last_week'])} books")
        print(f"📅 Earlier: {len(groups['earlier'])} books")
        
        suggestion = get_random_book_suggestion()
        if suggestion:
            print(f"🎲 Try This Next: {suggestion['title']}")
    else:
        print("❌ Could not load data")
    
    print("🎯 Ready for TRMNL integration!")
    app.run(host='0.0.0.0', port=port, debug=False)
