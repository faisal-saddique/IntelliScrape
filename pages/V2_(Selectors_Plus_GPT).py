import streamlit as st
import requests
from bs4 import BeautifulSoup
import html2text
from openai import OpenAI
from dotenv import load_dotenv
import validators
from urllib.parse import urlsplit
import json
from bs4 import BeautifulSoup
from utils.prompts import (SYSTEM_PROMPT_FOR_GETTING_JSON_SCHEMA,
                           SYSTEM_PROMPT_FOR_DATA_EXTRACTION_ACCORDING_TO_THE_JSON_SCHEMA, SYSTEM_PROMPT_DEFAULT, USER_REQUEST_FOR_JSON_SCHEMA, USER_REQUEST_FOR_STRUCTURED_CONTENT,
                           SYSTEM_PROMPT_FOR_GETTING_THE_DESIRED_SELECTORS,
                           USER_REQUEST_FOR_GETTING_THE_DESIRED_SELECTORS)

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI()

# Set page title and icon
st.set_page_config(
    page_title="Intelli Scrape - Approach 2",
    page_icon=":robot_face:"
)

def scrape_content_using_selectors(html_content, selectors):
    """
    Scrape content from HTML using the provided list of selectors.

    Parameters:
    - html_content (str): The HTML content to scrape.
    - selectors (list): List of CSS selectors.

    Returns:
    - dict: A dictionary containing the scraped content with selectors as keys.
    """
    # Initialize BeautifulSoup with the HTML content
    soup = BeautifulSoup(html_content, 'html.parser')

    # Dictionary to store scraped content
    scraped_content = {}

    # Iterate through each selector and extract content
    for name, selector in selectors.items():
        st.write(f"{name} => {selector}")
        elements = soup.select(selector)
        # Extract text content from each selected element
        content = [element.get_text(strip=True) for element in elements]
        # Store the content in the dictionary with the selector as the key
        scraped_content[name] = content

    return scraped_content

def truncate_text(text):
    return text[:70]

def process_tag(tag, result_dict):
    # Remove empty lines
    for element in tag.find_all():
        if element.attrs:
            # Keep only class, id, and href attributes
            element_attrs = {
                key: value
                for key, value in element.attrs.items()
                if key in ['class', 'id'] and ('nav' not in value if isinstance(value, str) else all('nav' not in v for v in value))
            }
            class_name = element_attrs.get('class')
            if class_name and tuple(class_name) not in result_dict:
                key = ' '.join(class_name)
                result_dict[key] = truncate_text(element.get_text(strip=True))

        if element.name in ['img','table', 'iframe', 'input', 'script', 'style', 'meta', 'link', 'comment', 'head', 'footer', 'nav', 'form', 'noscript']:
            element.decompose()
        elif element.string:
            element.string.replace_with(truncate_text(element.string.strip()))
        elif element.string and not len(element.string.strip()):
            element.decompose()

def summarize_body(html_content):
    result_dict = {}
    process_tag(html_content, result_dict)
    return result_dict

# @st.cache_data
def extract_base_url(url):
    parsed_url = urlsplit(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return base_url

# @st.cache_data
def validate_url(url):
    return validators.url(url)

def scrape_body_from_html(html_content_raw):
    soup = BeautifulSoup(html_content_raw, 'html.parser')
    # Extract content within the <body> tag
    body_content = soup.body if soup.body else soup
    return body_content

# @st.cache_data
def scrape_body_from_url(url):
    # Use requests to get HTML content
    html_content_scrapped = requests.get(url).content
    soup = BeautifulSoup(html_content_scrapped, 'html.parser')
    # Extract content within the <body> tag
    body_content = soup.body if soup.body else soup
    return html_content_scrapped, body_content

# Function to scrape and convert HTML to Markdown
@st.cache_data
def scrape_and_convert(html_content, base_url=None):
    soup = BeautifulSoup(html_content, 'html.parser')
    # Extract content within the <body> tag
    body_content = soup.body if soup.body else soup
    markdown_content = html2text.html2text(str(body_content), baseurl=base_url)
    return markdown_content

@st.cache_data
def get_gpt_response(user_request: str, system_prompt: str = SYSTEM_PROMPT_DEFAULT, model: str = "gpt-4-1106-preview"):
    result = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request}
        ],
        model=model,
        response_format={"type": "json_object"}
    )
    return json.loads(result.choices[0].message.content.strip())

# Streamlit App
def main():

    # Page layout with title
    st.title("Intelli Scrape - CSS Selectors Approach")

    # Input for URL or File Upload
    url_or_file = st.radio("Choose Input Type:", ("URL", "Upload HTML File"))

    if url_or_file == "URL":
        url = st.text_input(
            "Enter URL:", placeholder="https://books.toscrape.com")
    else:
        uploaded_file = st.file_uploader("Upload HTML file", type=["html"])

    # Input for instructions
    instruction = st.text_area(
        "Enter Instructions:", placeholder="I need a list of all the books and their respective prices on this page.")

    if st.button("Scrape and Analyze"):
        if url_or_file == "URL":
            if url:
                if validate_url(url):
                    base_url = extract_base_url(url)
                    html_content_raw, html_content = scrape_body_from_url(url=url)
                else:
                    st.error("Invalid URL. Please enter a valid URL.")
                    return
            else:
                st.error("Please enter a URL.")
                return
        elif url_or_file == "Upload HTML File" and uploaded_file:
            if uploaded_file.name.endswith(".html") or uploaded_file.name.endswith(".htm"):
                # Read HTML content from the uploaded file
                html_content_raw = uploaded_file.read()
                html_content = scrape_body_from_html(html_content_raw=html_content_raw)
            else:
                st.error("Please enter upload a valid HTML file.")
                return
        else:
            st.error("Please enter a URL or upload an HTML file.")
            return

        with st.expander(label="Raw HTML Content"):
            st.markdown(html_content)

        summarized_dict = summarize_body(html_content)

        user_request_for_desired_selectors = USER_REQUEST_FOR_GETTING_THE_DESIRED_SELECTORS.replace(
            "<<INSTRUCTION>>", instruction).replace("<<SELECTORS_TO_CONTENT_MAPPING>>", json.dumps(summarized_dict))

        with st.expander(label="Summarized Selectors"):
            st.markdown(summarized_dict)

        desired_selectors = get_gpt_response(
            user_request=user_request_for_desired_selectors, system_prompt=SYSTEM_PROMPT_FOR_GETTING_THE_DESIRED_SELECTORS)

        with st.expander(label="Desired Selectors GPT"):
            st.markdown(desired_selectors)

        scraped_content_after_applying_selectors = scrape_content_using_selectors(html_content=html_content_raw, selectors=desired_selectors)

        st.markdown(scraped_content_after_applying_selectors)
        # user_request_for_structured_content = USER_REQUEST_FOR_STRUCTURED_CONTENT.replace(
        #     "<<JSON_SCHEMA>>", str(json_schema)).replace("<<INSTRUCTION>>", instruction).replace("<<SCRAPED_CONTENT>>", markdown_content)

        # extracted_structured_content = get_gpt_response(
        #     user_request=user_request_for_structured_content, system_prompt=SYSTEM_PROMPT_FOR_DATA_EXTRACTION_ACCORDING_TO_THE_JSON_SCHEMA)



if __name__ == "__main__":
    main()