import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# --- Database Connection ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    # Set the client encoding to UTF-8 to handle a wide range of characters
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'), client_encoding='utf8')
    return conn


# --- Table Setup ---
def init_db():
    """Initializes and updates the database schema."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create places table if it does not exist
    cur.execute('''
        CREATE TABLE IF NOT EXISTS places (
            place_name VARCHAR(255) PRIMARY KEY,
            short_description TEXT,
            image_url VARCHAR(1024),
            detailed_description TEXT
        );
    ''')

    # Now safe to run ALTER commands
    cur.execute('''
        ALTER TABLE places ADD COLUMN IF NOT EXISTS short_description TEXT;
        ALTER TABLE places ADD COLUMN IF NOT EXISTS image_url VARCHAR(1024);
        ALTER TABLE places ALTER COLUMN detailed_description DROP NOT NULL;
    ''')

    # Create a new table to cache search results
    cur.execute('''
        CREATE TABLE IF NOT EXISTS search_cache (
            id SERIAL PRIMARY KEY,
            search_term VARCHAR(255) UNIQUE NOT NULL,
            result_place_names TEXT[] NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    conn.commit()
    cur.close()
    conn.close()
    print("Database schema updated.")

# --- Data Operations ---
def get_cached_search(search_term):
    """Retrieves a cached search result from the database."""
    conn = get_db_connection()
    # Use RealDictCursor to get results as dictionaries
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # First, find the cached search term
    cur.execute("SELECT result_place_names FROM search_cache WHERE search_term = %s", (search_term,))
    cache_result = cur.fetchone()
    
    if not cache_result:
        cur.close()
        conn.close()
        return None

    # If found, fetch all the associated places
    place_names = cache_result['result_place_names']
    query = "SELECT place_name, short_description, image_url, (detailed_description IS NOT NULL) as has_details FROM places WHERE place_name = ANY(%s)"
    cur.execute(query, (place_names,))
    places = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Preserve the order from the original search
    ordered_places = sorted(places, key=lambda p: place_names.index(p['place_name']))
    return ordered_places

def save_search_result(search_term, places):
    """Saves a new search result and the associated places to the database."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    place_names = [p['name'] for p in places]

    try:
        # Use a transaction to ensure both inserts succeed or fail together
        # 1. Insert or update the places themselves
        for place in places:
            cur.execute("""
                INSERT INTO places (place_name, short_description, image_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (place_name) DO UPDATE SET
                    short_description = EXCLUDED.short_description,
                    image_url = EXCLUDED.image_url;
            """, (place['name'], place['description'], place['image_url']))

        # 2. Insert the search term and the list of place names
        cur.execute("""
            INSERT INTO search_cache (search_term, result_place_names)
            VALUES (%s, %s)
            ON CONFLICT (search_term) DO NOTHING;
        """, (search_term, place_names))
        
        conn.commit()
    except Exception as e:
        print(f"Database save error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def get_place_details(place_name):
    """Retrieves detailed description for a place from the database."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT detailed_description FROM places WHERE place_name = %s", (place_name,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    # Return the description only if it exists and is not NULL
    return result[0] if result and result[0] is not None else None

def save_place_details(place_name, description):
    """Saves or updates the detailed description for a place."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # The place already exists from the initial search, so we UPDATE it.
        cur.execute(
            """
            UPDATE places 
            SET detailed_description = %s 
            WHERE place_name = %s
            """,
            (description, place_name)
        )
        conn.commit()
        print(f"Successfully cached detailed description for '{place_name}'")
    except Exception as e:
        print(f"Error saving detailed description for '{place_name}': {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# Initialize the database when the application starts
if __name__ == '__main__':
    load_dotenv()
    init_db()
