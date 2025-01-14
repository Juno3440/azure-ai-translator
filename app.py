import os
import requests
import streamlit as st
from dotenv import load_dotenv
from azure.ai.translation.text import TextTranslationClient
from azure.ai.translation.text.models import InputTextItem
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

# Load environment variables
load_dotenv("azure.env")

azure_ai_translator_key = os.getenv("AZURE_AI_TRANSLATION_KEY")
azure_ai_translator_endpoint = os.getenv("AZURE_AI_TRANSLATION_ENDPOINT")
azure_ai_translator_region = os.getenv("AZURE_AI_TRANSLATION_REGION")

# Check if environment variables are loaded
if not azure_ai_translator_key or not azure_ai_translator_endpoint or not azure_ai_translator_region:
    st.error("Azure Translator API credentials are missing. Please check azure.env file.")
    st.stop()

# Create credential and TextTranslationClient
credential = AzureKeyCredential(azure_ai_translator_key)
text_translator = TextTranslationClient(
    endpoint=azure_ai_translator_endpoint,
    credential=credential
)

@st.cache_data
def fetch_languages():
    """
    Fetch supported languages via a direct REST call to Azure Translator.
    This endpoint is documented here:
    https://learn.microsoft.com/en-us/azure/cognitive-services/translator/reference/v3-0-languages
    """
    try:
        path = "/languages"
        params = {
            "api-version": "3.0",
            "scope": "translation"
        }
        # Be sure to strip any trailing slash from endpoint to avoid double-slash
        url = azure_ai_translator_endpoint.rstrip("/") + path
        headers = {
            "Ocp-Apim-Subscription-Key": azure_ai_translator_key,
            "Ocp-Apim-Subscription-Region": azure_ai_translator_region,
            "Content-type": "application/json",
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        languages = {}
        for lang_code, details in data["translation"].items():
            # details['name'] is the readable language name, e.g. "English", "French", etc.
            languages[details["name"]] = lang_code

        return languages
    except Exception as e:
        st.error(f"Error fetching supported languages: {e}")
        return {}

languages = fetch_languages()
language_names = list(languages.keys())

def translate_text(input_text, source_language_name, target_language_name):
    """
    Translates text using Azure AI Translator via direct REST API call,
    using the existing endpoint and credentials.
    """
    source_lang_code = languages.get(source_language_name)
    target_lang_code = languages.get(target_language_name)

    if not source_lang_code or not target_lang_code:
        return "Invalid language selection."

    try:
        # Use the existing endpoint from the environment
        path = "/translate"
        params = {
            "api-version": "3.0",
            "from": source_lang_code,
            "to": target_lang_code
        }
        
        # Build URL from existing endpoint
        url = azure_ai_translator_endpoint.rstrip("/") + path

        # Use existing credentials
        headers = {
            "Ocp-Apim-Subscription-Key": azure_ai_translator_key,
            "Ocp-Apim-Subscription-Region": azure_ai_translator_region,
            "Content-type": "application/json"
        }

        response = requests.post(
            url,
            headers=headers,
            params=params,
            json=[{"Text": input_text}]
        )
        response.raise_for_status()
        data = response.json()
        
        return data[0]["translations"][0]["text"]
    except Exception as e:
        st.error(f"Translation error: {e}")
        return "Error during translation."

# Streamlit UI
st.title("Azure AI Translator")
st.write("Translate text using Azure AI Translator.")

input_text = st.text_area("Enter text to translate:", height=100)

col1, col2 = st.columns(2)
with col1:
    # Default to "English" if present in language_names
    source_language_index = language_names.index("English") if "English" in language_names else 0
    source_language = st.selectbox("Source Language", language_names, index=source_language_index)

with col2:
    # Default to "French" if present in language_names
    target_language_index = language_names.index("French") if "French" in language_names else 0
    target_language = st.selectbox("Target Language", language_names, index=target_language_index)

if st.button("Translate"):
    if input_text.strip():
        translation = translate_text(input_text, source_language, target_language)
        st.subheader("Translated Text:")
        st.write(translation)
    else:
        st.warning("Please enter text to translate.")