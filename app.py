import streamlit as st
import requests
import pandas as pd

st.title("SHL Assessment Recommender")

st.write("Enter a job description to get the most relevant SHL assessments.")

job_description = st.text_area("Job Description:")

if st.button("Get Recommendations"):
    if job_description.strip() == "":
        st.error("Please enter a job description.")
    else:
        with st.spinner('Fetching recommendations...'):
            response = requests.post("http://localhost:8000/recommend", json={"job_description": job_description})
            if response.status_code == 200:
                recommendations = response.json().get("recommendations", [])
                if recommendations:
                    df = pd.DataFrame(recommendations)
                    df.columns = ["Assessment Name", "URL", "Remote Testing Support", "Adaptive/IRT Support", "Duration", "Test Types"]
                    st.dataframe(df)
                else:
                    st.write("No recommendations found.")
            else:
                st.error("Error fetching recommendations.") 