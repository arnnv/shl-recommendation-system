import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup

# Custom CSS for styling
st.markdown(
    """
    <style>
    .dataframe th, .dataframe td {
        padding: 10px;
        text-align: left;
    }
    .dataframe th {
        # background-color: #f4f4f4;
    }
    .dataframe td a {
        # color: #007BFF;
        text-decoration: none;
    }
    .dataframe td a:hover {
        text-decoration: underline;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("SHL Assessment Recommender")

st.write("Enter a job description or provide a URL to get the most relevant SHL assessments.")

# Create tabs for input methods
job_description_tab, url_tab = st.tabs(["Job Description", "Job URL"])

job_description = ""
url = ""

with job_description_tab:
    job_description = st.text_area("Job Description:")

with url_tab:
    url = st.text_input("Job Description URL:")
    if url:
        try:
            page = requests.get(url)
            soup = BeautifulSoup(page.content, 'html.parser')
            job_description = soup.get_text().strip()  # Directly use the parsed job description
        except Exception as e:
            st.error(f"Failed to parse job description from URL: {e}")

if st.button("Get Recommendations"):
    # Proceed if either job_description is filled or a URL is provided and parsed
    if not job_description.strip() and not url.strip():
        st.error("Please enter a job description or provide a valid URL.")
    else:
        with st.spinner('Fetching recommendations...'):
            response = requests.post("http://localhost:8000/recommend", json={"job_description": job_description})
            if response.status_code == 200:
                recommendations = response.json().get("recommendations", [])
                if recommendations:
                    df = pd.DataFrame(recommendations)
                    # Assign correct column names
                    df = df.rename(columns={
                        "name": "Assessment Name",
                        "url": "URL",
                        "remote_testing_support": "Remote Testing Support",
                        "adaptive_irt_support": "Adaptive/IRT Support",
                        "duration": "Duration",
                        "test_types": "Test Types"
                    })
                    # Drop the 'description' column if it exists
                    df = df.drop(columns=['description'], errors='ignore')
                    # Make URLs clickable
                    df['URL'] = df['URL'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>')
                    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
                else:
                    st.write("No recommendations found.")
            else:
                st.error("Error fetching recommendations.") 