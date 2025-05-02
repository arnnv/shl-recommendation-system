import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
import os

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
        with st.spinner('Analyzing job description and fetching recommendations...'):
            api_url = os.environ.get("API_URL", "http://localhost:8000")
            
            try:
                # Add timeout to prevent hanging
                response = requests.post(
                    f"{api_url}/recommend", 
                    json={"job_description": job_description},
                    timeout=120  # 2 minute timeout since LLM processing can take time
                )
                
                if response.status_code == 200:
                    try:
                        response_json = response.json()
                        recommendations = response_json.get("recommendations", [])
                        
                        if recommendations:
                            st.success(f"Found {len(recommendations)} relevant SHL assessments!")
                            
                            # Convert to DataFrame for display
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
                            
                            # Format test_types as comma-separated string if it's a list
                            if 'test_types' in df.columns:
                                df['Test Types'] = df['Test Types'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
                            
                            # Make URLs clickable
                            df['URL'] = df['URL'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>')
                            
                            # Display the recommendations in a nice table
                            st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
                            
                            # Add a download button for CSV export
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="Download recommendations as CSV",
                                data=csv,
                                file_name="shl_recommendations.csv",
                                mime="text/csv",
                            )
                        else:
                            st.warning("No matching assessments found for this job description. Try providing more details about the role and required skills.")
                    except Exception as e:
                        st.error(f"Error processing recommendations. Please try again or contact support.")
                else:
                    st.error(f"Error: Unable to get recommendations. Please try again later.")
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: Unable to reach the recommendation service. Please try again later.")
            except Exception as e:
                st.error(f"An unexpected error occurred. Please try again or contact support.")

