import os
import sqlite3
import random
from datetime import datetime, timedelta
from flask import Flask, jsonify

app = Flask(__name__)

def get_calibre_db_path():
    """Get the path to the Calibre database"""
    # Common Calibre database locations
    possible_paths = [
        os.path.expanduser("~/Calibre Library/metadata.db"),
        os.path.expanduser("~/Documents/Calibre Library/metadata.db"),
        "/Users/Shared/Calibre Library/metadata.db",
        # Add more paths as needed
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # If not found, return the most common default
    return os.path.expanduser("~/Calibre Library/metadata.db")

def get_books_from_calibre():
    """Get books from Calibre database"""
    db_path = get_calibre_db_path()
    
    if not os.path.exists(db_path):
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query to get books with page count from Count Pages plugin
        query = """
        SELECT 
            b.id,
            b.title,
            GROUP_CONCAT(a.name, ' & ') as authors,
            b.timestamp,
            r.rating,
            c.text as description,
            cp.value as page_count
        FROM books b
        LEFT JOIN books_authors_link bal ON b.id = bal.book
        LEFT JOIN authors a ON bal.author = a.id
        LEFT JOIN books_ratings_link brl ON b.id = brl.book
        LEFT JOIN ratings r ON brl.rating = r.id
        LEFT JOIN comments c ON b.id = c.book
        LEFT JOIN books_custom_column_links ccl ON b.id = ccl.book
        LEFT JOIN custom_columns cc ON ccl.column = cc.id AND cc.lookup_name = '#pages'
        LEFT JOIN custom_column_text cp ON ccl.value = cp.id
        GROUP BY b.id, b.title, b.timestamp, r.rating, c.text, cp.value
        ORDER BY b.timestamp DESC
        """
        
        cursor.execute(query)
        books = cursor.fetchall()
        conn.close()
        
        return books
    except Exception as e:
        print(f"Error reading Calibre database: {e}")
        return []

def get_book_tags(book_id):
    """Get tags for a specific book"""
    db_path = get_calibre_db_path()
    
    if not os.path.exists(db_path):
        return ""
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = """
        SELECT GROUP_CONCAT(t.name, ', ') as tags
        FROM books_tags_link btl
        JOIN tags t ON btl.tag = t.id
        WHERE btl.book = ?
        """
        
        cursor.execute(query, (book_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else ""
    except Exception as e:
        print(f"Error getting tags: {e}")
        return ""

@app.route('/calibre-status')
def calibre_status():
    try:
        books = get_books_from_calibre()
        
        if not books:
            return jsonify({
                "empty_library": True,
                "message": "No books found in your Calibre library. Add some books to get started!",
                "current_time": datetime.now().strftime("%m/%d %H:%M")
            })
        
        # Process books and categorize by date
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        
        this_week_books = []
        last_week_books = []
        earlier_books = []
        
        for i, book in enumerate(books, 1):
            book_id, title, authors, timestamp_str, rating, description, page_count_str = book
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('T', ' ').split('+')[0])
            except:
                timestamp = datetime.now() - timedelta(days=30)  # Default to old
            
            # Get tags
            tags = get_book_tags(book_id)
            
            # Parse page count from Count Pages plugin
            page_count = None
            if page_count_str:
                try:
                    page_count = int(page_count_str)
                except (ValueError, TypeError):
                    page_count = None
            
            # Format rating
            stars = "★" * rating if rating else ""
            
            # Clean up description (remove HTML if present)
            clean_description = ""
            if description:
                # Basic HTML tag removal
                import re
                clean_description = re.sub('<[^<]+?>', '', description).strip()
                # Limit length for display
                if len(clean_description) > 200:
                    clean_description = clean_description[:197] + "..."
            
            book_data = {
                "index": i,
                "title": title or "Unknown Title",
                "author": authors or "Unknown Author",
                "tags": tags,
                "rating": stars,
                "has_rating": bool(rating),
                "description": clean_description,
                "page_count": page_count
            }
            
            # Categorize by date
            if timestamp >= one_week_ago:
                this_week_books.append(book_data)
            elif timestamp >= two_weeks_ago:
                last_week_books.append(book_data)
            else:
                earlier_books.append(book_data)
        
        # Limit to reasonable display numbers
        this_week_books = this_week_books[:10]
        last_week_books = last_week_books[:10]
        earlier_books = earlier_books[:10]
        
        # Select a random book for the roulette
        all_books = this_week_books + last_week_books + earlier_books
        book_suggestion = random.choice(all_books) if all_books else None
        
        return jsonify({
            "empty_library": False,
            "this_week_books": this_week_books,
            "last_week_books": last_week_books,
            "earlier_books": earlier_books,
            "this_week_count": len(this_week_books),
            "last_week_count": len(last_week_books),
            "earlier_count": len(earlier_books),
            "book_suggestion": book_suggestion,
            "current_time": now.strftime("%m/%d %H:%M")
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to read Calibre library: {str(e)}",
            "empty_library": True,
            "message": "Error accessing your Calibre library. Please check the database path.",
            "current_time": datetime.now().strftime("%m/%d %H:%M")
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
