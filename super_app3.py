import streamlit as st
import requests
import json
from datetime import datetime
from newspaper import Article
import time
import ollama
import os

# API Key (replace with your actual Brave API key)
API_KEY = "api_key"

# Default search parameters
COUNTRY = "us"
SEARCH_LANG = "en"
COUNT = 5
SAFESEARCH = "strict"
FRESHNESS = None
EXTRA_SNIPPETS = False

def get_filename(query):
    date = datetime.now().strftime("%Y%m%d")
    return f"{date}_{query.replace(' ', '_')}.json"

def brave_news_search(query):
    url = "https://api.search.brave.com/res/v1/news/search"
    
    params = {
        'q': query,
        'country': COUNTRY,
        'search_lang': SEARCH_LANG,
        'count': COUNT,
        'safesearch': SAFESEARCH,
        'spellcheck': 1,
    }
    
    if FRESHNESS:
        params['freshness'] = FRESHNESS
    if EXTRA_SNIPPETS:
        params['extra_snippets'] = EXTRA_SNIPPETS
    
    headers = {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'X-Subscription-Token': API_KEY
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return None

def save_results(data, query):
    filename = get_filename(query)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return filename

def get_text_from_url(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        return f"An error occurred while fetching the URL: {e}"

def generate_response(messages, prompt):
    try:
        full_messages = messages + [{'role': 'user', 'content': prompt}]
        
        response = ollama.chat(
            model='llama3.1',
            messages=full_messages
        )
        
        return response['message']['content']
    except ollama.ResponseError as e:
        return None

def analyze_article(keyword, article):
    backstory = f"""
    Your role is to report all text related to: {keyword}.
    Provide a concise summary of the article's content related to this keyword.
    Include any relevant facts, figures, or key points mentioned.
    """

    messages = [
        {'role': 'system', 'content': backstory},
    ]

    scraped_text = article.get('scraped_text', '')
    if not scraped_text:
        return "No scraped text available for this article."

    prompt = f"Analyze the following article text in relation to '{keyword}':\n\n{scraped_text}"
    return generate_response(messages, prompt)

def process_query(query):
    results = brave_news_search(query)
    if not results:
        return None

    filename = save_results(results, query)
    
    articles = results.get('results', [])
    for article in articles:
        article['scraped_text'] = get_text_from_url(article['url'])
        article['analysis'] = analyze_article(query, article)
        time.sleep(1)  # Be nice to the servers

    # Update the JSON file with scraped text and analyses
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    return articles, filename

def main():
    st.set_page_config(page_title="AI News Summary", layout="wide")

    st.title("AI News Summary")
    st.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    query = st.text_input("Enter your news search query:")
    if st.button("Search and Analyze"):
        with st.spinner("Searching and analyzing articles..."):
            result = process_query(query)
            if result:
                articles, filename = result
            else:
                articles, filename = None, None

        if articles:
            st.success(f"Analysis complete. Found {len(articles)} articles. Results saved to {filename}")

            # Display results in tabs
            tabs = st.tabs([f"Article {i+1}" for i in range(len(articles))])

            for tab, article in zip(tabs, articles):
                with tab:
                    st.header(article['title'])
                    st.write(f"**Source:** [{article['url']}]({article['url']})")
                    
                    if 'thumbnail' in article and 'src' in article['thumbnail']:
                        st.image(article['thumbnail']['src'], width=200)
                    
                    st.subheader("Analysis")
                    st.write(article['analysis'])
                    
                    with st.expander("Show full scraped text"):
                        st.write(article['scraped_text'])
        else:
            st.error("No articles found or an error occurred during the search.")

if __name__ == "__main__":
    main()