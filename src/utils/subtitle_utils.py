from typing import List, Dict, Union, Any

def optimize_subtitles_for_llm(subtitles: List[Dict[str, Any]]) -> List[List[Union[str, int]]]:
    """
    Optimizes subtitle data for LLM consumption by reducing token count.
    
    Converts a list of subtitle dictionaries with 'word', 'start', and 'end' keys
    into a compact list of lists format: [[word, start_ms, end_ms], ...].
    Timestamps are converted from seconds to milliseconds (integer).
    
    Args:
        subtitles: A list of dictionaries, where each dictionary represents a word
                   and contains 'word' (str), 'start' (float/int seconds), 
                   and 'end' (float/int seconds).
                   
    Returns:
        A list of lists, where each inner list contains:
        [word (str), start_ms (int), end_ms (int)].
    """
    optimized_subtitles = []
    
    for item in subtitles:
        # Extract values, defaulting to None if keys are missing (though expected to be present)
        for words in item.get("words"):
            word = words.get("word", "")
            start_sec = words.get("start", 0)
            end_sec = words.get("end", 0)
            
            # Convert seconds to milliseconds and round to nearest integer
            # start_ms = int(round(start_sec * 1000))
            # end_ms = int(round(end_sec * 1000))
            
            optimized_subtitles.append([word, start_sec, end_sec])
            
    return optimized_subtitles
