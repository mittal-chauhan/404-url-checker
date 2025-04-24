import streamlit as st
import aiohttp
import asyncio
from urllib.parse import urlparse
from googlesearch import search
import warnings

# Suppress deprecation warnings
warnings.filterwarnings("ignore")

st.set_page_config(page_title="404 URL Checker", layout="centered")

st.title("⚡ 404 URL Checker from Google Search")
query = st.text_input("Enter search query (e.g., site:example.com)", placeholder="site:example.com")
num_urls = st.slider("Number of URLs to check", 10, 100, 50)
submit = st.button("Check for 404s")

async def check_url(session, url):
    try:
        # First try GET request
        async with session.get(url, allow_redirects=True, timeout=10) as response:
            if response.status == 404:
                return (url, 404)
            if response.status >= 400:
                return (url, f"HTTP {response.status}")
            
            # Verify by checking content
            content = await response.read()
            if len(content) < 100:
                return (url, "Suspiciously small response")
            
            return None
            
    except aiohttp.ClientError:
        # Retry once
        try:
            async with session.get(url, allow_redirects=True, timeout=15) as response:
                if response.status >= 400:
                    return (url, f"HTTP {response.status} (retry)")
                return None
        except Exception as retry_error:
            return (url, f"Connection Error: {str(retry_error)}")
            
    except Exception as e:
        return (url, f"Error: {str(e)}")

async def check_urls(urls):
    broken = []
    connector = aiohttp.TCPConnector(limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_url(session, url) for url in urls]
        for i, future in enumerate(asyncio.as_completed(tasks)):
            result = await future
            if result:
                broken.append(result)
            st.session_state.progress = (i + 1) / len(urls)
    return broken

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_google_results(query, num_results):
    try:
        return list(set([  # Remove duplicates
            url for url in search(
                query,
                num_results=num_results,
                advanced=False,
                sleep_interval=2
            )
            if is_valid_url(url)
        ]))[:num_results]  # Ensure we don't exceed requested number
    except Exception as e:
        st.error(f"Search error: {str(e)}")
        return []

if submit and query:
    if not query.strip():
        st.error("Please enter a valid search query")
        st.stop()

    # Initialize session state
    if 'progress' not in st.session_state:
        st.session_state.progress = 0
    
    progress_bar = st.progress(st.session_state.progress)
    status_text = st.empty()

    # Step 1: Get URLs
    status_text.text("🔍 Searching Google...")
    urls = get_google_results(query, num_urls)
    
    if not urls:
        st.error("No valid URLs found. Try a different query.")
        st.stop()

    st.success(f"✅ Found {len(urls)} URLs. Now checking status...")
    
    # Step 2: Check URLs
    broken_urls = asyncio.run(check_urls(urls))
    
    # Display results
    st.success(f"Completed! Checked {len(urls)} URLs.")
    
    # Filter out false positives
    true_broken = [
        (url, code) for url, code in broken_urls 
        if "404" in str(code) or "HTTP 40" in str(code) or "HTTP 50" in str(code)
    ]
    other_issues = [
        (url, code) for url, code in broken_urls 
        if (url, code) not in true_broken
    ]

    st.subheader(f"Found {len(true_broken)} truly broken URLs")
    if true_broken:
        st.markdown("### ❌ Broken URLs (confirmed 404):")
        for url, code in sorted(true_broken, key=lambda x: x[1]):
            st.markdown(f"- `{code}` - [{url}]({url})")
    
    if other_issues:
        st.subheader(f"{len(other_issues)} URLs with potential issues")
        st.markdown("### ⚠️ Check these manually:")
        for url, code in other_issues:
            st.markdown(f"- `{code}` - [{url}]({url})")
    elif not true_broken:
        st.balloons()
        st.success("🎉 No broken links found!")

    progress_bar.empty()
    status_text.empty()