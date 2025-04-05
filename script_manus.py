#!/usr/bin/env python3
"""
SHL Assessment Data Crawler

This script crawls SHL's product catalog to extract assessment information including:
- Assessment name and URL
- Remote Testing Support (Yes/No)
- Adaptive/IRT Support (Yes/No)
- Duration
- Test type (list)

The data is saved in JSON format.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import random
import os
import signal
import sys
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime

# Constants
BASE_URL = "https://www.shl.com"
CATALOG_URL = "https://www.shl.com/solutions/products/product-catalog/"
OUTPUT_FILE = "shl_assessments.json"
PARTIAL_OUTPUT_FILE = "shl_assessments_partial.json"
METADATA_FILE = "shl_crawl_state.json"

# Type parameters for different sections - CORRECTED
INDIVIDUAL_TYPE = "1"    # Individual Test Solutions
PRE_PACKAGED_TYPE = "2"  # Pre-packaged Job Solutions

# User agent to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Global variable to store all assessments
all_assessments = []
# Track processed URLs to avoid duplicates
processed_urls = set()
# Global crawl state to track progress
crawl_state = {
    "last_crawl_time": None,
    "pre_packaged_last_page": None,
    "pre_packaged_page_num": 1,
    "individual_last_page": None,
    "individual_page_num": 1,
    "completed": False
}

def save_crawl_state():
    """Save the current crawl state to a metadata file."""
    global crawl_state
    
    # Update the last crawl time
    crawl_state["last_crawl_time"] = datetime.now().isoformat()
    
    print(f"Saving crawl state to {METADATA_FILE}")
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(crawl_state, f, indent=2, ensure_ascii=False)
    print(f"Crawl state saved successfully.")

def load_crawl_state():
    """Load the previous crawl state if it exists."""
    global crawl_state
    
    if os.path.exists(METADATA_FILE):
        print(f"Found existing crawl state in {METADATA_FILE}. Loading...")
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                loaded_state = json.load(f)
                crawl_state.update(loaded_state)
                
            print(f"Loaded crawl state from {crawl_state['last_crawl_time']}")
            print(f"Pre-packaged last page: {crawl_state['pre_packaged_last_page']}")
            print(f"Pre-packaged page number: {crawl_state.get('pre_packaged_page_num', 1)}")
            print(f"Individual last page: {crawl_state['individual_last_page']}")
            print(f"Individual page number: {crawl_state.get('individual_page_num', 1)}")
            
            return True
        except Exception as e:
            print(f"Error loading crawl state: {e}")
            return False
    else:
        print(f"No existing crawl state found. Starting fresh crawl.")
        return False

def load_existing_assessments():
    """Load existing assessments from the output file if it exists."""
    global all_assessments, processed_urls
    
    if os.path.exists(OUTPUT_FILE):
        print(f"Found existing assessment data in {OUTPUT_FILE}. Loading...")
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_assessments = json.load(f)
                
            # Add existing assessments to the global list
            all_assessments = existing_assessments
            
            # Add all URLs to processed_urls set
            for assessment in existing_assessments:
                if 'url' in assessment:
                    processed_urls.add(assessment['url'])
                    
            print(f"Loaded {len(all_assessments)} existing assessments. Will skip these in the crawl.")
            return True
        except Exception as e:
            print(f"Error loading existing assessments: {e}")
            return False
    else:
        print(f"No existing assessment data found in {OUTPUT_FILE}. Starting fresh crawl.")
        return False

def save_partial_results():
    """Save the current results to a partial output file."""
    global all_assessments
    print(f"\nSaving partial results ({len(all_assessments)} assessments) to {PARTIAL_OUTPUT_FILE}")
    with open(PARTIAL_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_assessments, f, indent=2, ensure_ascii=False)
    print(f"Partial results saved successfully.")
    
    # Also save the current crawl state
    save_crawl_state()

def signal_handler(sig, frame):
    """Handle Ctrl+C and other termination signals."""
    print("\nCrawling interrupted. Saving partial results...")
    save_partial_results()
    sys.exit(0)

def get_page_content(url):
    """
    Fetch the content of a page and return a BeautifulSoup object.
    
    Args:
        url (str): The URL to fetch
        
    Returns:
        BeautifulSoup: Parsed HTML content
    """
    try:
        # Add a random delay to avoid being blocked
        time.sleep(random.uniform(1, 2))
        
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        return BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_assessment_links(soup, section_type):
    """
    Extract assessment links from the catalog page.
    
    Args:
        soup (BeautifulSoup): Parsed HTML of the catalog page
        section_type (str): Type of section ('pre-packaged' or 'individual')
        
    Returns:
        list: List of dictionaries with assessment names and URLs
    """
    assessments = []
    
    # Find the section header based on section type
    if section_type == 'pre-packaged':
        section_header = soup.find(string=re.compile('Pre-packaged Job Solutions', re.IGNORECASE))
    else:
        section_header = soup.find(string=re.compile('Individual Test Solutions', re.IGNORECASE))
    
    if not section_header:
        print(f"Warning: Could not find section header for {section_type} on the page")
        # Try to find assessment links directly if we're on a section-specific page
        if section_type == 'pre-packaged' and 'type=2' in soup.get_text():
            section = soup
        elif section_type == 'individual' and 'type=1' in soup.get_text():
            section = soup
        else:
            return assessments
    else:
        # Find the table rows containing assessments
        section = section_header.find_parent('div')
        if not section:
            print(f"Warning: Could not find section container for {section_type}")
            return assessments
    
    # Find all assessment links in this section
    assessment_links = section.find_all('a')
    
    for link in assessment_links:
        name = link.get_text(strip=True)
        url = urljoin(BASE_URL, link.get('href'))
        
        # Skip if it's not a valid assessment link
        if not name or not url or not url.startswith(BASE_URL):
            continue
            
        # Skip if we've already processed this URL
        if url in processed_urls:
            print(f"Skipping already processed URL: {url}")
            continue
            
        # Add to processed URLs
        processed_urls.add(url)
        
        # Find the row containing this assessment
        row = link.find_parent('tr') or link.find_parent('div')
        if not row:
            continue
        
        # Initialize assessment data
        assessment = {
            'name': name,
            'url': url,
            'remote_testing_support': 'No',
            'adaptive_irt_support': 'No',
            'duration': None,
            'test_types': [],
            'description': None
        }
        
        # Check for Remote Testing support (green circle)
        # The green dots are span elements with class "catalogue__circle -yes"
        remote_testing_cells = row.find_all('span', class_='catalogue__circle')
        if remote_testing_cells and len(remote_testing_cells) > 0:
            # First green circle is for Remote Testing
            if 'yes' in str(remote_testing_cells[0].get('class', [])) or '-yes' in str(remote_testing_cells[0].get('class', [])):
                assessment['remote_testing_support'] = 'Yes'
        
        # Check for Adaptive/IRT support (green circle)
        if remote_testing_cells and len(remote_testing_cells) > 1:
            # Second green circle is for Adaptive/IRT
            if 'yes' in str(remote_testing_cells[1].get('class', [])) or '-yes' in str(remote_testing_cells[1].get('class', [])):
                assessment['adaptive_irt_support'] = 'Yes'
        
        # Extract test types from the last column
        test_type_cell = row.find_all('div', class_='test-type') or row.find_all('td', class_='test-type')
        if not test_type_cell:
            # Try to find any element containing test type letters
            test_type_elements = row.find_all(string=re.compile('[ABCKPS]'))
            if test_type_elements:
                test_type_text = ''.join([elem.strip() for elem in test_type_elements if len(elem.strip()) <= 6])
            else:
                test_type_text = ''
        else:
            test_type_text = test_type_cell[0].get_text(strip=True)
        
        if test_type_text:
            # Map letter codes to test types
            type_mapping = {
                'A': 'Ability',
                'B': 'Behavioral',
                'C': 'Cognitive',
                'K': 'Knowledge',
                'P': 'Personality',
                'S': 'Situational'
            }
            
            for letter in test_type_text:
                if letter in type_mapping:
                    assessment['test_types'].append(type_mapping[letter])
        
        assessments.append(assessment)
    
    return assessments

def extract_assessment_details(assessment):
    """
    Extract detailed information from an individual assessment page.
    
    Args:
        assessment (dict): Assessment dictionary with name and URL
        
    Returns:
        dict: Updated assessment dictionary with all details
    """
    soup = get_page_content(assessment['url'])
    if not soup:
        return assessment
    
    # Extract Description from meta tag
    meta_description = soup.find('meta', attrs={'name': 'description'})
    if meta_description and 'content' in meta_description.attrs:
        assessment['description'] = meta_description['content'].strip()
        
    # Extract Duration from Assessment length section
    duration_section = soup.find(string=re.compile('Assessment length', re.IGNORECASE))
    if duration_section:
        section = duration_section.find_parent('div') or duration_section.find_parent('section')
        if section:
            # Look for text containing "minutes" or a time format
            duration_text = section.get_text()
            duration_match = re.search(r'(\d+)\s*minutes|time\s*=\s*(\d+)|time\s*in\s*minutes\s*=\s*(\d+)', duration_text, re.IGNORECASE)
            if duration_match:
                duration = duration_match.group(1) or duration_match.group(2) or duration_match.group(3)
                assessment['duration'] = f"{duration} minutes"
    
    # If we couldn't find duration in the Assessment length section, look elsewhere
    if not assessment['duration']:
        # Try to find any text containing duration information
        duration_match = re.search(r'(\d+)\s*minutes|time\s*=\s*(\d+)|time\s*in\s*minutes\s*=\s*(\d+)', soup.get_text(), re.IGNORECASE)
        if duration_match:
            duration = duration_match.group(1) or duration_match.group(2) or duration_match.group(3)
            assessment['duration'] = f"{duration} minutes"
    
    # Double-check Remote Testing Support if not already determined
    if assessment['remote_testing_support'] == 'No':
        remote_testing_text = soup.find(string=re.compile('Remote Testing', re.IGNORECASE))
        if remote_testing_text:
            # Check if there's a "Yes" nearby
            parent = remote_testing_text.find_parent()
            if parent:
                if re.search(r'yes', parent.get_text(), re.IGNORECASE):
                    assessment['remote_testing_support'] = 'Yes'
    
    # Double-check Adaptive/IRT Support if not already determined
    if assessment['adaptive_irt_support'] == 'No':
        adaptive_text = soup.find(string=re.compile('Adaptive|IRT', re.IGNORECASE))
        if adaptive_text:
            # Check if there's a "Yes" nearby
            parent = adaptive_text.find_parent()
            if parent:
                if re.search(r'yes', parent.get_text(), re.IGNORECASE):
                    assessment['adaptive_irt_support'] = 'Yes'
    
    # If test_types is empty, try to extract from the page
    if not assessment['test_types']:
        test_type_section = soup.find(string=re.compile('Test Type', re.IGNORECASE))
        if test_type_section:
            section = test_type_section.find_parent('div') or test_type_section.find_parent('section')
            if section:
                test_type_text = section.get_text(strip=True)
                # Map letter codes to test types
                type_mapping = {
                    'A': 'Ability',
                    'B': 'Behavioral',
                    'C': 'Cognitive',
                    'K': 'Knowledge',
                    'P': 'Personality',
                    'S': 'Situational'
                }
                
                for letter in test_type_text:
                    if letter in type_mapping and type_mapping[letter] not in assessment['test_types']:
                        assessment['test_types'].append(type_mapping[letter])
    
    return assessment

def extract_page_number(url):
    """
    Extract the page number from a URL.
    
    Args:
        url (str): URL to extract page number from
        
    Returns:
        int: Page number, or 1 if not found
    """
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    
    if 'start' in query_params:
        try:
            # SHL uses 'start' parameter with multiples of 12 (0, 12, 24, etc.)
            start = int(query_params['start'][0])
            return (start // 12) + 1
        except (ValueError, IndexError):
            pass
    
    return 1

def handle_pagination(soup, current_url, solution_type):
    """
    Check if there are more pages to crawl and return the next page URL.
    
    Args:
        soup (BeautifulSoup): Parsed HTML of the current page
        current_url (str): Current URL being processed
        solution_type (str): Type of solution ('1' for individual, '2' for pre-packaged)
        
    Returns:
        str or None: URL of the next page, or None if there are no more pages
    """
    # Look for "Next" link in pagination
    next_link = soup.find('a', string=re.compile('Next', re.IGNORECASE))
    if next_link and next_link.get('href'):
        next_url = urljoin(BASE_URL, next_link.get('href'))
        
        # Ensure the type parameter is preserved or added
        parsed_url = urlparse(next_url)
        query_params = parse_qs(parsed_url.query)
        
        # Set or update the type parameter
        query_params['type'] = [solution_type]
        
        # Reconstruct the URL with updated query parameters
        query_string = urlencode(query_params, doseq=True)
        parts = list(parsed_url)
        parts[4] = query_string
        
        next_url = urljoin(BASE_URL, urlunparse(parts))
        
        # Verify this is actually a new URL
        if next_url == current_url:
            print("Warning: Next URL is the same as current URL. Stopping pagination.")
            return None
            
        return next_url
    
    return None

def crawl_section(start_url, section_type, solution_type, max_pages=None):
    """
    Crawl a specific section (Pre-packaged or Individual) of the SHL catalog.
    
    Args:
        start_url (str): Starting URL for this section
        section_type (str): Type of section ('pre-packaged' or 'individual')
        solution_type (str): Type parameter value ('1' for individual, '2' for pre-packaged)
        max_pages (int, optional): Maximum number of pages to crawl. If None, crawl all pages.
    
    Returns:
        list: List of assessment dictionaries for this section
    """
    global all_assessments, crawl_state
    section_assessments = []
    
    # Check if we should resume from a previous page
    current_url = start_url
    page_num = 1
    
    if section_type == 'pre-packaged' and crawl_state['pre_packaged_last_page']:
        current_url = crawl_state['pre_packaged_last_page']
        page_num = crawl_state.get('pre_packaged_page_num', 1)
        print(f"Resuming {section_type} crawl from: {current_url} (page {page_num})")
    elif section_type == 'individual' and crawl_state['individual_last_page']:
        current_url = crawl_state['individual_last_page']
        page_num = crawl_state.get('individual_page_num', 1)
        print(f"Resuming {section_type} crawl from: {current_url} (page {page_num})")
    
    while current_url and (max_pages is None or page_num <= max_pages):
        print(f"Crawling {section_type} page {page_num}: {current_url}")
        
        # Update the crawl state with the current URL and page number
        if section_type == 'pre-packaged':
            crawl_state['pre_packaged_last_page'] = current_url
            crawl_state['pre_packaged_page_num'] = page_num
        else:
            crawl_state['individual_last_page'] = current_url
            crawl_state['individual_page_num'] = page_num
        save_crawl_state()
        
        soup = get_page_content(current_url)
        
        if not soup:
            print(f"Error: Failed to fetch content for {current_url}")
            break
        
        # Extract assessments from this page
        page_assessments = extract_assessment_links(soup, section_type)
        print(f"Found {len(page_assessments)} {section_type} solutions")
        
        if len(page_assessments) == 0:
            print(f"Warning: No assessments found on {section_type} page {page_num}. This might indicate an issue.")
            # Try to debug by checking the page content
            page_title = soup.title.string if soup.title else "No title"
            print(f"Page title: {page_title}")
            
            # Check if we're on the right type of page
            if section_type == 'pre-packaged' and 'type=2' not in current_url:
                print(f"Error: URL doesn't contain correct type parameter for {section_type}")
                # Fix the URL and try again
                fixed_url = f"{CATALOG_URL}?type={PRE_PACKAGED_TYPE}"
                if 'start=' in current_url:
                    start_match = re.search(r'start=(\d+)', current_url)
                    if start_match:
                        fixed_url += f"&start={start_match.group(1)}"
                print(f"Trying with fixed URL: {fixed_url}")
                current_url = fixed_url
                continue
            elif section_type == 'individual' and 'type=1' not in current_url:
                print(f"Error: URL doesn't contain correct type parameter for {section_type}")
                # Fix the URL and try again
                fixed_url = f"{CATALOG_URL}?type={INDIVIDUAL_TYPE}"
                if 'start=' in current_url:
                    start_match = re.search(r'start=(\d+)', current_url)
                    if start_match:
                        fixed_url += f"&start={start_match.group(1)}"
                print(f"Trying with fixed URL: {fixed_url}")
                current_url = fixed_url
                continue
        
        # Process each assessment to get detailed information
        for i, assessment in enumerate(page_assessments):
            print(f"Processing assessment {i+1}/{len(page_assessments)}: {assessment['name']}")
            updated_assessment = extract_assessment_details(assessment)
            section_assessments.append(updated_assessment)
            all_assessments.append(updated_assessment)
            
            # Save partial results every 10 assessments
            if (len(all_assessments) % 10) == 0:
                save_partial_results()
        
        # Check for next page
        next_url = handle_pagination(soup, current_url, solution_type)
        if not next_url:
            print(f"No more pages found for {section_type}. Ending pagination.")
            break
        
        current_url = next_url
        page_num += 1
        
        # Save partial results after each page
        save_partial_results()
    
    # Set this section as completed in crawl state
    if section_type == 'pre-packaged':
        crawl_state['pre_packaged_last_page'] = None  # Mark as completed
        crawl_state['pre_packaged_page_num'] = 1
    else:
        crawl_state['individual_last_page'] = None  # Mark as completed
        crawl_state['individual_page_num'] = 1
    save_crawl_state()
    
    return section_assessments

def crawl_shl_assessments(max_pages=None):
    """
    Main function to crawl SHL assessments and save data to JSON.
    
    Args:
        max_pages (int, optional): Maximum number of pages to crawl per section. If None, crawl all pages.
    
    Returns:
        list: List of assessment dictionaries with all details
    """
    global all_assessments, processed_urls, crawl_state
    
    # Load existing assessments or initialize empty containers
    if not load_existing_assessments():
        all_assessments = []
        processed_urls = set()
    
    # Load previous crawl state
    load_crawl_state()
    
    # Register signal handler for Ctrl+C and other termination signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Check if the crawl was already completed
        if crawl_state.get('completed', False):
            print("Previous crawl was completed. Starting a fresh crawl...")
            # Reset the crawl state
            crawl_state = {
                "last_crawl_time": datetime.now().isoformat(),
                "pre_packaged_last_page": None,
                "pre_packaged_page_num": 1,
                "individual_last_page": None,
                "individual_page_num": 1,
                "completed": False
            }
            save_crawl_state()
        
        # Main catalog page only needs to be crawled if this is a fresh start
        if not crawl_state.get('last_crawl_time'):
            print(f"Crawling main catalog page: {CATALOG_URL}")
            soup = get_page_content(CATALOG_URL)
            
            if soup:
                # Extract pre-packaged job solutions from main page
                pre_packaged_assessments = extract_assessment_links(soup, 'pre-packaged')
                print(f"Found {len(pre_packaged_assessments)} pre-packaged job solutions on main page")
                
                # Extract individual test solutions from main page
                individual_assessments = extract_assessment_links(soup, 'individual')
                print(f"Found {len(individual_assessments)} individual test solutions on main page")
                
                # Process assessments from main page
                for i, assessment in enumerate(pre_packaged_assessments + individual_assessments):
                    print(f"Processing assessment {i+1}/{len(pre_packaged_assessments) + len(individual_assessments)}: {assessment['name']}")
                    updated_assessment = extract_assessment_details(assessment)
                    all_assessments.append(updated_assessment)
                    
                    # Save partial results every 10 assessments
                    if (len(all_assessments) % 10) == 0:
                        save_partial_results()
        
        # Crawl Pre-packaged Job Solutions pages
        if crawl_state.get('pre_packaged_last_page') is not None or not crawl_state.get('last_crawl_time'):
            pre_packaged_url = f"{CATALOG_URL}?type={PRE_PACKAGED_TYPE}"
            crawl_section(pre_packaged_url, 'pre-packaged', PRE_PACKAGED_TYPE, max_pages)
        else:
            print("Skipping Pre-packaged Job Solutions section (already completed)")
        
        # Crawl Individual Test Solutions pages
        if crawl_state.get('individual_last_page') is not None or not crawl_state.get('last_crawl_time'):
            individual_url = f"{CATALOG_URL}?type={INDIVIDUAL_TYPE}"
            crawl_section(individual_url, 'individual', INDIVIDUAL_TYPE, max_pages)
        else:
            print("Skipping Individual Test Solutions section (already completed)")
        
        # Mark crawl as completed
        crawl_state['completed'] = True
        save_crawl_state()
        
        # Save the final data to the main output file
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_assessments, f, indent=2, ensure_ascii=False)
        
        print(f"Crawling complete. Found {len(all_assessments)} assessments. Data saved to {OUTPUT_FILE}")
        return all_assessments
    
    except Exception as e:
        print(f"Error during crawling: {e}")
        import traceback
        traceback.print_exc()
        save_partial_results()
        return all_assessments

if __name__ == "__main__":
    # Set max_pages to None to crawl all pages, or a number to limit pages per section
    crawl_shl_assessments(max_pages=None)
