def get_initial_search_prompt(location):
    """
    Creates the prompt to get a list of 10 famous places for a given location.
    Asks the LLM to return a valid JSON string.
    """
    return f"""
    You are a travel expert. Your task is to identify the 9 most famous and must-see tourist attractions in or very near '{location}'.
    If the location itself is a specific landmark (like 'Eiffel Tower'), list it first, followed by 9 other famous places nearby.

    Provide the output as a single, minified JSON array of objects. Do not include any text before or after the JSON array.
    Each object in the array must have two keys:
    1. "name": The name of the attraction.
    2. "description": A brief, engaging 3-4 sentence summary for a tourist.

    Example format:
    [{{"name":"Louvre Museum","description":"The Louvre is the world's largest art museum and a historic monument in Paris, France. It is best known for being the home of the Mona Lisa. A central landmark of the city, it is located on the Right Bank of the Seine."}}]
    """

def get_detailed_description_prompt(place_name):
    """
    Creates the prompt for a detailed, conversational guide-style description of a place.
    This is intended to be read aloud.
    """
    return f"""
    You are a world-class travel writer and guide. Write an extremely detailed, comprehensive, and engaging travel guide for "{place_name}" in 8 sections, each clearly marked with a markdown heading (e.g., ## Introduction, ## History and Significance, etc.). Each section should be thorough, and the total length should be at least 10,000 words.
    Generate a captivating and comprehensive travel guide for them, written in a conversational and engaging tone, as if you are speaking to them directly. The total length should be between 800 and 1000 words.

    Your response must be a single block of text with words ranging from 2000 to 5000, perfect for a text-to-speech service.
    You should not give puncuation such as '*' , '```'in output as I am going to use this output for for a text-to-speech service.

    Structure your guide like this:
    1.  **Introduction:** Start with a warm welcome. Greet the traveler and introduce "{place_name}" in an exciting way.
    2.  **History and Significance:** Briefly share the story behind the place. Make it interesting, like telling a story, not like a dry history lesson.
    3.  **What to See and Do:** Describe the main highlights. What are the must-see things inside or around? What activities can they do? Use vivid language.
    4.  **Fascinating Facts:** Fun, quirky, or little-known facts that surprise travelers.                                                                                                               
    5.  **Best Photo Spots:** Tell them where they can get the best photos. Be specific, like "For a stunning sunset shot, stand on the western corner...".
    6.  **Local Cuisine and Food:** Recommend nearby food or specific dishes they should try that are famous in the area.
    7.  **Best Time to Visit:** Advise on the best season, day of the week, or time of day to visit to avoid crowds or to get the best experience.
    8.  **Parting Tip:** End with a friendly closing remark or a final insider tip to make their visit memorable.

    Do not include any text outside these sections. Each section should be long, detailed, and engaging, as if for a book chapter. Return only the markdown-formatted guide.
    Remember, speak directly to the user (e.g., "You'll want to...", "Imagine yourself..."). Your tone should be cheerful and passionate about the location.
    """

def get_regenerate_section_prompt(place_name, section_title, current_text, user_instruction=None):
    """
    Creates a prompt for regenerating a specific section of a travel guide, with optional user instruction.
    """
    clean_title = section_title.replace('##', '').strip()
    instruction_text = f"\n\nThe user has requested the following changes or focus: {user_instruction}" if user_instruction else ""
    return f"""
    You are a world-class travel writer and guide. You are helping to improve a specific section of a travel guide for \"{place_name}\".
    The section is titled \"{clean_title}\" and currently contains the following text:
    {current_text}
    {instruction_text}
    Please rewrite this section with the following improvements:
    1.Focus on user input what user wants from instruction_text.
    2. Keep the same conversational, friendly tone as if speaking directly to the traveler
    3. Add more vivid details and specific recommendations 
    4. Make it more engaging and informative
    5. Ensure the content remains factually accurate about {place_name}
    Return ONLY the new content for this section, without any additional formatting or notes.
    Do not include the section title or any markdown heading in your response.
    """
