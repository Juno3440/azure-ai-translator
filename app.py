import os
import requests
import streamlit as st
from dotenv import load_dotenv
from azure.ai.translation.text import TextTranslationClient
from azure.ai.translation.text.models import InputTextItem
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from time import sleep

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
language_names = ["Detect"] + list(languages.keys())  # Add "Detect" as first option

def translate_text(input_text, source_language_name, target_language_name):
    """
    Translates text using Azure AI Translator via direct REST API call,
    using the existing endpoint and credentials.
    """
    target_lang_code = languages.get(target_language_name)
    
    if not target_lang_code:
        return "Invalid target language selection."

    try:
        # Use the existing endpoint from the environment
        path = "/translate"
        params = {
            "api-version": "3.0",
            "to": target_lang_code
        }
        
        # Only add 'from' parameter if a specific source language is selected
        if source_language_name != "Detect":
            source_lang_code = languages.get(source_language_name)
            if source_lang_code:
                params["from"] = source_lang_code

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
        
        result = data[0]["translations"][0]["text"]
        
        # If source language was auto-detected, show it to the user
        if source_language_name == "Detect" and "detectedLanguage" in data[0]:
            detected_lang_code = data[0]["detectedLanguage"]["language"]
            confidence = data[0]["detectedLanguage"]["score"]
            # Find the language name from the code
            detected_lang_name = next(
                (name for name, code in languages.items() if code == detected_lang_code),
                detected_lang_code  # fallback to code if name not found
            )
            st.info(f"Detected language: {detected_lang_name} (confidence: {confidence:.2%})")
        
        return result

    except Exception as e:
        st.error(f"Translation error: {e}")
        return "Error during translation."

def detect_language(input_text):
    """
    Detects the language of input text using Azure AI Translator.
    Returns the detected language name and confidence score.
    """
    if not input_text.strip():
        return None, None

    try:
        path = "/detect"
        url = azure_ai_translator_endpoint.rstrip("/") + path
        
        headers = {
            "Ocp-Apim-Subscription-Key": azure_ai_translator_key,
            "Ocp-Apim-Subscription-Region": azure_ai_translator_region,
            "Content-type": "application/json"
        }
        
        response = requests.post(
            url,
            headers=headers,
            params={"api-version": "3.0"},
            json=[{"Text": input_text}]
        )
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            detected_lang_code = data[0]["language"]
            confidence = data[0]["score"]
            # Find the language name from the code
            detected_lang_name = next(
                (name for name, code in languages.items() if code == detected_lang_code),
                detected_lang_code  # fallback to code if name not found
            )
            return detected_lang_name, confidence
    except Exception as e:
        st.error(f"Language detection error: {e}")
    
    return None, None

# Streamlit UI
st.title("Azure AI Translator")
st.write("Translate text using Azure AI Translator.")

input_text = st.text_area("Enter text to translate:", height=100, key="input_text")

# Initialize detected language variables
detected_lang = None
confidence = None

# Detect language as user types (with debouncing)
if input_text:
    # Add a small delay to avoid too frequent API calls
    sleep(0.5)  # 500ms delay
    
    # Clear previous detection if input is different
    if 'previous_input' not in st.session_state or st.session_state.previous_input != input_text:
        detected_lang, confidence = detect_language(input_text)
        if detected_lang and confidence:
            st.info(f"Detected language: {detected_lang} (confidence: {confidence:.2%})")
            st.session_state.previous_input = input_text

col1, col2 = st.columns(2)
with col1:
    # Set detected language as default if available, otherwise use "Detect"
    default_index = (
        language_names.index(detected_lang) 
        if detected_lang and detected_lang in language_names 
        else 0
    )
    source_language = st.selectbox(
        "Source Language",
        language_names,
        index=default_index,
        key="source_language"  # Add key for state management
    )

with col2:
    # Default to "English" if present in language_names (skip "Detect")
    target_language_index = language_names.index("English") if "English" in language_names else 1
    target_language = st.selectbox(
        "Target Language", 
        language_names[1:],  # Exclude "Detect"
        index=target_language_index-1,
        key="target_language"  # Add key for state management
    )

if st.button("Translate"):
    if input_text.strip():
        translation = translate_text(input_text, source_language, target_language)
        st.subheader("Translated Text:")
        st.write(translation)
    else:
        st.warning("Please enter text to translate.")