import streamlit as st
import requests
import json
from datetime import datetime
from newspaper import Article
import time
import os

# API Keys (replace with your actual API keys)
BRAVE_API_KEY = "brave_api"
PERPLEXITY_API_KEY = "perplexity_api"

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
        'X-Subscription-Token': BRAVE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error during API request: {e}")
        return None

def save_results(data, query):
    filename = get_filename(query)
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return filename
    except IOError as e:
        st.error(f"Error saving results: {e}")
        return None

def get_text_from_url(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        return f"An error occurred while fetching the URL: {e}"

def generate_response(messages, prompt):
    url = "https://api.perplexity.ai/chat/completions"
    
    payload = {
        "model": "llama-3.1-8b-instruct",
        "messages": messages + [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "top_p": 0.9,
        "return_citations": True,
        "search_domain_filter": ["perplexity.ai"],
        "return_images": False,
        "return_related_questions": False,
        "search_recency_filter": "month",
        "top_k": 0,
        "stream": False,
        "presence_penalty": 0,
        "frequency_penalty": 1
    }
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        return response_data['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        st.error(f"Error generating response: {e}")
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
    if not filename:
        return None
    
    articles = results.get('results', [])
    for article in articles:
        article['scraped_text'] = get_text_from_url(article['url'])
        article['analysis'] = analyze_article(query, article)
        time.sleep(1)  # Be nice to the servers

    # Update the JSON file with scraped text and analyses
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
    except IOError as e:
        st.error(f"Error updating results file: {e}")

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
                    st.header(article.get('title', 'No title available'))
                    st.write(f"**Source:** [{article.get('url', '#')}]({article.get('url', '#')})")
                    
                    if 'thumbnail' in article and article['thumbnail'].get('src'):
                        try:
                            st.image(article['thumbnail']['src'], width=200)
                        except Exception as e:
                            st.warning(f"Unable to load image: {e}")
                    else:
                        st.info("No thumbnail available for this article.")
                    
                    st.subheader("Analysis")
                    st.write(article.get('analysis', 'No analysis available'))
                    
                    with st.expander("Show full scraped text"):
                        st.write(article.get('scraped_text', 'No scraped text available'))
        else:
            st.error("No articles found or an error occurred during the search.")

if __name__ == "__main__":
    main()