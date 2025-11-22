# core/tools/search.py
from googlesearch import search

def google_search(query, num_results=3):
    try:
        results = list(search(query, num_results=num_results, advanced=True))
        context = ""
        for res in results:
            context += f"Source: {res.title} - {res.description}\n"
        return context
    except:
        return "No internet connection or search failed."