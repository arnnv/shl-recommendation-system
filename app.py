import streamlit as st
import requests
import pandas as pd

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
                    # Make URLs clickable
                    df['URL'] = df['URL'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>')
                    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
                else:
                    st.write("No recommendations found.")
            else:
                st.error("Error fetching recommendations.") 