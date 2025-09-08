import os
import json
import requests
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import database
import prompts

# --- Initialization ---
load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
# Configure Gemini API
try:
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    model = None

# --- CORS Helper Function ---
def handle_preflight():
    """Handle CORS preflight requests by returning appropriate headers."""
    response = jsonify({})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

# --- Helper Functions ---
def get_wikipedia_image_url(place_name):
    """Fetches the main image URL for a place from Wikipedia."""
    session = requests.Session()
    url = "https://en.wikipedia.org/w/api.php"
    
    # Add a User-Agent header to identify our script, as required by many APIs.
    headers = {
        'User-Agent': 'AITravelPlanner/1.0 (MyCoolApp; myemail@example.com)'
    }

    params = {
        "action": "query",
        "format": "json",
        "titles": place_name,
        "prop": "pageimages",
        "pithumbsize": 500, # Image width in pixels
        "pilicense": "any"
    }
    try:
        response = session.get(url=url, params=params, headers=headers)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        pages = data["query"]["pages"]
        for page_id in pages:
            if "thumbnail" in pages[page_id]:
                return pages[page_id]["thumbnail"]["source"]
    except Exception as e:
        print(f"Wikipedia API error for {place_name}: {e}")
    return None # Return None if no image is found or an error occurs

# --- API Endpoints ---
@app.route('/search-places', methods=['POST', 'OPTIONS'])
def search_places():
    """
    Endpoint to get a list of 10 famous places.
    Checks the database for a cached search before calling the LLM.
    """
    if request.method == 'OPTIONS':
        return handle_preflight()
        
    if not model:
        return jsonify({"error": "AI Model not configured"}), 500

    data = request.get_json()
    if not data or 'location' not in data:
        return jsonify({"error": "Location not provided"}), 400

    location = data['location'].strip().lower()

    # 1. Check for a cached search result first
    cached_places = database.get_cached_search(location)
    if cached_places:
        print(f"Cache hit for search term: '{location}'")
        # Standardize the keys to match what the frontend expects
        standardized_places = [
            {
                "name": p["place_name"],
                "description": p["short_description"],
                "image_url": p["image_url"],
                "has_details": p["has_details"]
            }
            for p in cached_places
        ]
        return jsonify({"places": standardized_places, "token_count": 0})

    # 2. If not cached, call LLM
    print(f"Cache miss for search term: '{location}'. Calling LLM.")
    prompt = prompts.get_initial_search_prompt(location)
    try:
        response = model.generate_content(prompt)
        token_count = response.usage_metadata.total_token_count
        print(f"Search places token count: {token_count}")

        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        places_from_llm = json.loads(clean_response)

        # Fetch images and add to the objects
        for place in places_from_llm:
            place['image_url'] = get_wikipedia_image_url(place['name'])

        # Add 'has_details' flag for consistent response format
        for place in places_from_llm:
            place['has_details'] = False
            # Rename 'description' to 'short_description' for consistency before saving
            place['short_description'] = place['description']

        # 3. Save the new result to the database for future requests
        database.save_search_result(location, places_from_llm)

        return jsonify({"places": places_from_llm, "token_count": token_count})

    except Exception as e:
        print(f"Error during place search: {e}")
        return jsonify({"error": "Failed to fetch places from AI model."}), 500

@app.route('/place-details', methods=['POST', 'OPTIONS'])
def get_place_details():
    """
    Endpoint to get detailed, conversational info about a single place.
    Checks the database first before making the second, more expensive LLM call.
    """
    if request.method == 'OPTIONS':
        return handle_preflight()
        
    if not model:
        return jsonify({"error": "AI Model not configured"}), 500

    data = request.get_json()
    if not data or 'place_name' not in data:
        return jsonify({"error": "Place name not provided"}), 400

    place_name = data['place_name']

    # 1. Check database first
    cached_details = database.get_place_details(place_name)
    if cached_details:
        print(f"Cache hit for {place_name}")
        return jsonify({"description": cached_details, "token_count": 0})

    # 2. If not in DB, call LLM
    print(f"Cache miss for {place_name}. Calling LLM.")
    prompt = prompts.get_detailed_description_prompt(place_name)
    try:
        response = model.generate_content(prompt)
        token_count = response.usage_metadata.total_token_count
        print(f"Place details token count: {token_count}")
        detailed_description = response.text

        # 3. Save to database for future requests
        database.save_place_details(place_name, detailed_description)

        return jsonify({"description": detailed_description, "token_count": token_count})
    except Exception as e:
        print(f"Error during detail generation: {e}")
        return jsonify({"error": "Failed to generate details from AI model."}), 500

# --- Regenerate Section Endpoint ---
@app.route('/regenerate-section', methods=['POST', 'OPTIONS'])
def regenerate_section():
    # Handle preflight CORS requests for the regenerate-section endpoint
    if request.method == 'OPTIONS':
        return handle_preflight()
        
    print("\n--- REGENERATE SECTION CALLED ---")
    if not model:
        print("Error: AI Model not configured")
        return jsonify({"error": "AI Model not configured"}), 500
    
    print("Parsing request data...")
    data = request.get_json()
    print(f"Request data: {data}")
    
    place_name = data.get('place_name')
    section_title = data.get('section_title')
    current_text = data.get('current_text')
    user_instruction = data.get('user_instruction', '').strip()

    print(f"Place name: {place_name}")
    print(f"Section title: {section_title}")
    print(f"Current text length: {len(current_text) if current_text else 0}")
    print(f"User instruction: {user_instruction}")

    if not (place_name and section_title and current_text):
        missing = []
        if not place_name: missing.append('place_name')
        if not section_title: missing.append('section_title')
        if not current_text: missing.append('current_text')
        print(f"Error: Missing required fields: {', '.join(missing)}")
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    print("Generating prompt...")
    prompt = prompts.get_regenerate_section_prompt(place_name, section_title, current_text, user_instruction)
    print(f"Prompt generated (length: {len(prompt)})")

    try:
        print("Calling Gemini API...")
        response = model.generate_content(prompt)
        regenerated_content = response.text.strip()
        print(f"Response received. Content length: {len(regenerated_content)}")
        print("First 100 chars:", regenerated_content[:100])
        return jsonify({"regenerated_content": regenerated_content})
    except Exception as e:
        print(f"Error during section regeneration: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to regenerate section: {str(e)}"}), 500

# --- Save Detailed Description Endpoint ---
@app.route('/save-detailed-description', methods=['POST', 'OPTIONS'])
def save_detailed_description():
    # Handle preflight CORS requests for the save-detailed-description endpoint
    if request.method == 'OPTIONS':
        return handle_preflight()
        
    print("\n--- SAVE DETAILED DESCRIPTION CALLED ---")
    data = request.get_json()
    place_name = data.get('place_name')
    description = data.get('description')
    
    print(f"Place name: {place_name}")
    print(f"Description length: {len(description) if description else 0}")
    
    if not (place_name and description):
        missing = []
        if not place_name: missing.append('place_name')
        if not description: missing.append('description')
        print(f"Error: Missing required fields: {', '.join(missing)}")
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    
    try:
        database.save_place_details(place_name, description)
        print("Successfully saved to database")
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error saving detailed description: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to save description: {str(e)}"}), 500

# --- Run Application ---
if __name__ == '__main__':
    # Initialize the database (creates table if it doesn't exist)
    database.init_db()
    # Run the Flask app
    app.run(debug=True, port=5000)
