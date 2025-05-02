FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Streamlit app
COPY . .

# Create .streamlit directory and config
RUN mkdir -p .streamlit
RUN echo '[server]\nenableCORS = false\nenableXsrfProtection = false\n\n[browser]\nserverAddress = "0.0.0.0"\nserverPort = 8501\ngatherUsageStats = false' > .streamlit/config.toml

# Expose the port Streamlit runs on
EXPOSE 8501

# Command to run the Streamlit app
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
