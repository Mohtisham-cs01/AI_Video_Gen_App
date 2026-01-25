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

def float_to_srt_time_format(d_seconds: float) -> str:
    """
    Convert seconds (float) to SRT time format: HH:MM:SS,mmm
    """
    seconds = int(d_seconds)
    microseconds = int((d_seconds - seconds) * 1000)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{microseconds:03d}"

def segments_to_srt(segments: List[Dict[str, Any]]) -> str:
    """
    Convert a list of segment dicts to SRT formatted string.
    Each segment is expected to have 'start', 'end', and 'text'.
    """
    srt_content = ""
    for i, segment in enumerate(segments, start=1):
        start_time = float_to_srt_time_format(segment.get('start', 0))
        end_time = float_to_srt_time_format(segment.get('end', 0))
        text = segment.get('text', '').strip()
        
        srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
    
    return srt_content
