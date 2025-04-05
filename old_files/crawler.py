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
MAX_PAGE_RETRIES = 3
RETRY_DELAY_SECONDS = 5

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
    "individual_last_page": None,
    "completed": False
}

def save_crawl_state():
    """Save the current crawl state to a metadata file."""
    global crawl_state
    
    # Update the last crawl time
    crawl_state["last_crawl_time"] = datetime.now().isoformat()
    
    print(f"Saving crawl state to {METADATA_FILE}")
    try:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(crawl_state, f, indent=2, ensure_ascii=False)
        print(f"Crawl state saved successfully.")
    except IOError as e:
        print(f"Error saving crawl state: {e}")

def load_crawl_state():
    """Load the previous crawl state if it exists."""
    global crawl_state
    
    if os.path.exists(METADATA_FILE):
        print(f"Found existing crawl state in {METADATA_FILE}. Loading...")
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                loaded_state = json.load(f)
                crawl_state.update(loaded_state)
                
            print(f"Loaded crawl state from {crawl_state.get('last_crawl_time', 'N/A')}")
            print(f"Pre-packaged last page: {crawl_state.get('pre_packaged_last_page')}")
            print(f"Individual last page: {crawl_state.get('individual_last_page')}")
            
            return True
        except Exception as e:
            print(f"Error loading crawl state: {e}")
            # Reset state if loading fails to avoid using corrupted data
            crawl_state = { "last_crawl_time": None, "pre_packaged_last_page": None, "individual_last_page": None, "completed": False }
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
            # Don't prevent crawling, just start fresh if load fails
            all_assessments = []
            processed_urls = set()
            return False
    else:
        print(f"No existing assessment data found in {OUTPUT_FILE}. Starting fresh crawl.")
        return False

def save_partial_results():
    """Save the current results to a partial output file."""
    global all_assessments
    print(f"\nSaving partial results ({len(all_assessments)} assessments) to {PARTIAL_OUTPUT_FILE}")
    try:
        with open(PARTIAL_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_assessments, f, indent=2, ensure_ascii=False)
        print(f"Partial results saved successfully.")
    except IOError as e:
        print(f"Error saving partial results: {e}")
    
    # Also save the current crawl state
    save_crawl_state()

def signal_handler(sig, frame):
    """Handle Ctrl+C and other termination signals."""
    print("\nCrawling interrupted. Saving partial results and state...")
    save_partial_results()
    sys.exit(0)

def get_page_content(url):
    """
    Fetch the content of a page and return a BeautifulSoup object. Includes basic retry logic.
    
    Args:
        url (str): The URL to fetch
        
    Returns:
        BeautifulSoup or None: Parsed HTML content or None if fetching fails after retries.
    """
    attempts = 0
    while attempts < MAX_PAGE_RETRIES:
        try:
            # Add a random delay to avoid being blocked
            delay = random.uniform(1, 3)
            print(f"Waiting {delay:.2f}s before fetching {url} (Attempt {attempts + 1}/{MAX_PAGE_RETRIES})")
            time.sleep(delay)
            
            response = requests.get(url, headers=HEADERS, timeout=30) # Added timeout
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            
            # Check for empty response
            if not response.text:
                 print(f"Warning: Received empty response from {url}. Retrying...")
                 attempts += 1
                 time.sleep(RETRY_DELAY_SECONDS)
                 continue

            return BeautifulSoup(response.text, 'html.parser')
        
        except requests.exceptions.Timeout:
            print(f"Timeout error fetching {url}. Retrying...")
            attempts += 1
            time.sleep(RETRY_DELAY_SECONDS)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}. Retrying...")
            attempts += 1
            time.sleep(RETRY_DELAY_SECONDS)

    print(f"Failed to fetch {url} after {MAX_PAGE_RETRIES} attempts.")
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
        print(f"Warning: Could not find section header for '{section_type}'. Assessment links might be missed.")
        # Try finding links broadly if header is missing
        container = soup.find('div', class_=re.compile('catalogue|product-list')) # Example classes, adjust if needed
        if not container:
             container = soup # Fallback to whole soup
    else:
        # Find the container (e.g., table, div) holding the links for this section
        section = section_header.find_parent('div', class_=re.compile('section|container')) # More robust parent finding
        if not section:
            print(f"Warning: Could not find parent container for '{section_type}' header. Searching broadly.")
            section = soup # Fallback

    # Find all assessment links within the determined container
    assessment_links = section.find_all('a', href=re.compile('/solutions/products/')) # More specific href pattern

    if not assessment_links:
         print(f"Warning: No assessment links found in the expected section for '{section_type}'.")

    processed_in_batch = set() # Track URLs processed in this specific call to avoid duplicates within the same page parse

    for link in assessment_links:
        name = link.get_text(strip=True)
        href = link.get('href')
        
        # Basic validation of the link
        if not name or not href or not href.startswith('/'):
            continue

        url = urljoin(BASE_URL, href)
        
        # Skip if it's not a valid assessment link (heuristic: check URL path)
        if not url.startswith(BASE_URL + "/solutions/products/"):
             continue
             
        # Skip if we've already processed this URL globally or in this batch
        if url in processed_urls or url in processed_in_batch:
            # print(f"Skipping already processed URL: {url}") # Reduce noise
            continue
            
        # Add to processed URLs
        processed_urls.add(url)
        processed_in_batch.add(url)
        
        # Find the row/container containing this assessment for icons
        row = link.find_parent('tr') or link.find_parent('div', class_=re.compile('item|row|entry'))
        if not row:
            # print(f"Warning: Could not find parent row/container for assessment: {name}") # Reduce noise
            # Initialize with defaults if row not found
             assessment = {
                'name': name, 'url': url, 'remote_testing_support': 'Unknown', 
                'adaptive_irt_support': 'Unknown', 'duration': None, 
                'test_types': [], 'description': None
             }
             assessments.append(assessment)
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
            if 'yes' in remote_testing_cells[0].get('class', []) or '-yes' in remote_testing_cells[0].get('class', []):
                assessment['remote_testing_support'] = 'Yes'
        
        # Check for Adaptive/IRT support (green circle)
        if remote_testing_cells and len(remote_testing_cells) > 1:
            # Second green circle is for Adaptive/IRT
            if 'yes' in remote_testing_cells[1].get('class', []) or '-yes' in remote_testing_cells[1].get('class', []):
                assessment['adaptive_irt_support'] = 'Yes'
        
        # Extract test types from the last column/div
        test_type_container = row.find(['td', 'div'], class_=re.compile('test-type', re.IGNORECASE))
        test_type_text = ''
        if test_type_container:
            test_type_text = test_type_container.get_text(strip=True)
        else:
            # Fallback: Look for likely test type abbreviations in the row text
            row_text = row.get_text(separator=' ', strip=True)
            found_types = re.findall(r'\b([ABCKPS])\b', row_text) # Find standalone letters
            if found_types:
                test_type_text = "".join(found_types)

        if test_type_text:
            # Map letter codes to test types
            type_mapping = {
                'A': 'Ability', 'B': 'Behavioral', 'C': 'Cognitive',
                'K': 'Knowledge', 'P': 'Personality', 'S': 'Situational'
            }
            seen_types = set()
            for letter in test_type_text:
                if letter in type_mapping and type_mapping[letter] not in seen_types:
                    assessment['test_types'].append(type_mapping[letter])
                    seen_types.add(type_mapping[letter])
        
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
    print(f"Fetching details for: {assessment['name']} at {assessment['url']}")
    soup = get_page_content(assessment['url'])
    if not soup:
        print(f"Failed to get details for {assessment['name']}. Skipping detail extraction.")
        # Keep existing data, maybe mark as incomplete?
        assessment['details_extracted'] = False 
        return assessment

    assessment['details_extracted'] = True

    # Extract Description from meta tag
    meta_description = soup.find('meta', attrs={'name': 'description'})
    if meta_description and 'content' in meta_description.attrs:
        assessment['description'] = meta_description['content'].strip()
        
    # Extract Duration - Look for more patterns
    duration_found = False
    duration_patterns = [
        re.compile(r'(\d+)\s*(?:-|to)\s*(\d+)\s*minutes', re.IGNORECASE), # Range e.g. 15-20 minutes
        re.compile(r'approx(?:imately)?\s*(\d+)\s*minutes', re.IGNORECASE), # Approx X minutes
        re.compile(r'(\d+)\s*minutes', re.IGNORECASE), # X minutes
        re.compile(r'assessment length:?\s*([\w\s]+)', re.IGNORECASE), # Section header
        re.compile(r'duration:?\s*([\w\s]+)', re.IGNORECASE) # Duration label
    ]
    
    # Search specific sections first
    length_section_header = soup.find(string=re.compile('Assessment length', re.IGNORECASE))
    if length_section_header:
        section = length_section_header.find_parent(['div', 'section', 'p'])
        if section:
            section_text = section.get_text(" ", strip=True)
            for pattern in duration_patterns:
                match = pattern.search(section_text)
                if match:
                    if len(match.groups()) == 2: # Range found
                         assessment['duration'] = f"{match.group(1)}-{match.group(2)} minutes"
                    else: # Single value or text
                         duration_val = match.group(1).strip()
                         if duration_val.isdigit():
                              assessment['duration'] = f"{duration_val} minutes"
                         elif 'minute' in duration_val.lower(): # Text like "Varies" or "Untimed" might be here
                              assessment['duration'] = duration_val
                    duration_found = True
                    break

    # If not found in specific section, search whole page text
    if not duration_found:
        page_text = soup.get_text(" ", strip=True)
        for pattern in duration_patterns:
             match = pattern.search(page_text)
             if match:
                 if len(match.groups()) == 2:
                      assessment['duration'] = f"{match.group(1)}-{match.group(2)} minutes"
                 else:
                      duration_val = match.group(1).strip()
                      if duration_val.isdigit():
                           assessment['duration'] = f"{duration_val} minutes"
                      elif 'minute' in duration_val.lower() or len(duration_val) < 20 : # Capture short texts like "Varies"
                           assessment['duration'] = duration_val
                 duration_found = True
                 break

    # Double-check Remote Testing Support if not already determined ('No' or 'Unknown')
    if assessment.get('remote_testing_support', 'Unknown') != 'Yes':
        # Look for explicit indicators
        remote_keywords = ['remote proctoring available', 'remotely proctored', 'online invigilation']
        page_text_lower = soup.get_text(" ", strip=True).lower()
        if any(keyword in page_text_lower for keyword in remote_keywords):
             assessment['remote_testing_support'] = 'Yes'
        # Fallback: Check near "Remote Testing" text if present
        elif assessment.get('remote_testing_support') == 'No': # Only upgrade 'No' if we have weak evidence
             remote_testing_text = soup.find(string=re.compile('Remote Testing', re.IGNORECASE))
             if remote_testing_text:
                 parent = remote_testing_text.find_parent()
                 if parent and re.search(r'\byes\b|available', parent.get_text(), re.IGNORECASE):
                     assessment['remote_testing_support'] = 'Yes'
    
    # Double-check Adaptive/IRT Support if not already determined ('No' or 'Unknown')
    if assessment.get('adaptive_irt_support', 'Unknown') != 'Yes':
        adaptive_keywords = ['adaptive', 'computer adaptive test', 'cat', 'item response theory', 'irt']
        page_text_lower = soup.get_text(" ", strip=True).lower()
        # Check specific common phrases first
        if 'computer adaptive' in page_text_lower:
             assessment['adaptive_irt_support'] = 'Yes'
        # Then check broader keywords
        elif any(keyword in page_text_lower for keyword in adaptive_keywords):
             assessment['adaptive_irt_support'] = 'Yes'
        # Fallback: Check near "Adaptive" or "IRT" text if present
        elif assessment.get('adaptive_irt_support') == 'No': # Only upgrade 'No' if weak evidence
             adaptive_text = soup.find(string=re.compile('Adaptive|IRT', re.IGNORECASE))
             if adaptive_text:
                 parent = adaptive_text.find_parent()
                 if parent and re.search(r'\byes\b|true|enabled', parent.get_text(), re.IGNORECASE):
                     assessment['adaptive_irt_support'] = 'Yes'
    
    # If test_types is empty, try to extract from the page (e.g., from a "Measures:" section)
    if not assessment['test_types']:
        measures_header = soup.find(['h2','h3','strong'], string=re.compile('Measures:|What it measures', re.IGNORECASE))
        test_type_section = soup.find(string=re.compile('Test Type', re.IGNORECASE))
        search_area = None

        if measures_header:
            search_area = measures_header.find_parent()
        elif test_type_section:
            search_area = test_type_section.find_parent()
        
        if search_area:
            search_text = search_area.get_text(" ", strip=True).lower()
            # Map keywords to test types
            keyword_mapping = {
                'ability': 'Ability', 'cognitive': 'Cognitive', 'reasoning': 'Ability',
                'behavioral': 'Behavioral', 'behavioural': 'Behavioral', 'work style': 'Behavioral', 'competencies': 'Behavioral',
                'knowledge': 'Knowledge', 'skills': 'Knowledge', 'technical': 'Knowledge',
                'personality': 'Personality', 'motivation': 'Personality', 'preferences': 'Personality',
                'situational judgment': 'Situational', 'scenario': 'Situational'
            }
            seen_types = set()
            for keyword, type_name in keyword_mapping.items():
                 if keyword in search_text and type_name not in seen_types:
                     assessment['test_types'].append(type_name)
                     seen_types.add(type_name)

    # Cleanup empty lists
    if not assessment['test_types']:
         del assessment['test_types'] # Remove if still empty after trying

    return assessment

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
    # Look for "Next" link in pagination (common patterns)
    next_link = soup.find(['a', 'button'], {'rel': 'next'}) or \
                soup.find(['a', 'button'], string=re.compile(r'Next\b', re.IGNORECASE)) or \
                soup.find(['a', 'button'], class_=re.compile(r'next', re.IGNORECASE))

    if next_link and next_link.get('href'):
        # Check if the link is disabled (sometimes done with classes or attributes)
        if 'disabled' in next_link.get('class', []) or next_link.get('disabled'):
             print("Found 'Next' link, but it appears disabled.")
             return None

        next_href = next_link.get('href')
        # Avoid javascript links or empty hrefs
        if not next_href or next_href.startswith(('javascript:', '#')):
             print(f"Found 'Next' link, but href is invalid: {next_href}")
             return None

        next_url = urljoin(BASE_URL, next_href)
        
        # Basic check to prevent immediate loops
        if next_url == current_url:
            print(f"Warning: Next URL is the same as current URL ({current_url}). Stopping pagination.")
            return None

        # Ensure the type parameter is preserved or added
        parsed_url = urlparse(next_url)
        query_params = parse_qs(parsed_url.query)
        query_params['type'] = [solution_type] # Ensure correct type is set
        
        # Reconstruct the URL
        query_string = urlencode(query_params, doseq=True)
        parts = list(parsed_url)
        parts[4] = query_string
        final_next_url = urlunparse(parts) # Use urlunparse which handles base correctly

        print(f"Found next page link: {final_next_url}")
        return final_next_url
    
    print("No 'Next' page link found or link is invalid.")
    return None

def crawl_section(start_url, section_type, solution_type, max_pages=None):
    """
    Crawl a specific section (Pre-packaged or Individual) of the SHL catalog.
    Handles retries and robust completion checking.
    
    Args:
        start_url (str): Starting URL for this section
        section_type (str): Type of section ('pre-packaged' or 'individual')
        solution_type (str): Type parameter value ('1' for individual, '2' for pre-packaged)
        max_pages (int, optional): Maximum number of pages to crawl. If None, crawl all pages.
    
    Returns:
        list: List of assessment dictionaries added in this run for this section
    """
    global all_assessments, crawl_state
    section_assessments_this_run = []
    
    # Determine starting URL based on saved state
    current_url = start_url
    state_key = f"{section_type.replace('-', '_')}_last_page" # e.g., pre_packaged_last_page
    if crawl_state.get(state_key):
        current_url = crawl_state[state_key]
        print(f"Resuming {section_type} crawl from saved state: {current_url}")
    else:
        print(f"Starting {section_type} crawl from: {current_url}")
    
    page_num = 1
    section_completed_normally = False
    max_retries_reached_on_page = False

    while current_url and (max_pages is None or page_num <= max_pages):
        print(f"\n--- Crawling {section_type} page {page_num} ---")
        print(f"URL: {current_url}")
        
        # Update the crawl state *before* attempting to fetch
        crawl_state[state_key] = current_url
        save_crawl_state() # Save progress before potentially failing
        
        soup = get_page_content(current_url)
        
        if not soup:
            print(f"Failed to fetch content for {current_url} after retries. Stopping crawl for this section.")
            max_retries_reached_on_page = True
            break # Exit the while loop for this section

        # Extract assessments from this page
        page_assessments = extract_assessment_links(soup, section_type)
        print(f"Found {len(page_assessments)} new {section_type} solutions on this page.")
        
        # --- Empty Page / Rate Limit Handling ---
        # If page loaded but no assessments found, check for pagination.
        # If pagination exists, it's likely a rate-limit/partial load issue. Retry the *same* URL.
        # If no pagination exists, it *might* be the true end, but could also be an error.
        # We rely on get_page_content retries for fetch issues. Here we handle logical emptiness.
        if not page_assessments:
            temp_next_url = handle_pagination(soup, current_url, solution_type)
            if temp_next_url:
                print(f"Warning: Page {current_url} loaded but no assessments found, but a 'Next' link exists. Assuming temporary issue. Retrying same URL soon.")
                # The loop will continue, and get_page_content will handle retries/delays for the *next* fetch (which will be the same URL if next_url isn't updated)
                # Let's add an extra delay here before attempting the next page (which might be the same one)
                time.sleep(RETRY_DELAY_SECONDS * 2)
                # We don't advance to next_url yet, letting the main loop retry current_url implicitly
                # Note: This doesn't implement an explicit retry count *here*, relying on the overall structure
            else:
                print(f"Page {current_url} loaded with no assessments and no 'Next' link found. Assuming end of section or error.")
                # Proceed to check pagination formally below, which should return None
                pass # Let the normal pagination check handle the exit condition

        # Process each assessment found on this page
        for i, assessment in enumerate(page_assessments):
            # Check again if URL already processed (e.g., added during detail fetch of another)
            if assessment['url'] in processed_urls and any(a['url'] == assessment['url'] for a in all_assessments):
                 # print(f"Skipping already globally processed assessment: {assessment['name']}") # Reduce noise
                 continue

            print(f"Processing assessment {i+1}/{len(page_assessments)}: {assessment['name']}")
            updated_assessment = extract_assessment_details(assessment)
            
            # Add to global list only if details were extracted or if it's truly new
            # Avoid duplicates if extract_assessment_links found it but load_existing already had it
            if not any(a['url'] == updated_assessment['url'] for a in all_assessments):
                 all_assessments.append(updated_assessment)
                 section_assessments_this_run.append(updated_assessment) # Track additions in this run
                 processed_urls.add(updated_assessment['url']) # Ensure added URL is marked processed

                 # Save partial results periodically
                 if (len(all_assessments) % 10) == 0:
                      save_partial_results()
            elif updated_assessment.get('details_extracted', False):
                 # Update existing entry if we got new details
                 for idx, existing_assessment in enumerate(all_assessments):
                      if existing_assessment['url'] == updated_assessment['url']:
                           all_assessments[idx] = updated_assessment
                           print(f"Updated details for existing assessment: {assessment['name']}")
                           break


        # Check for the actual next page URL
        next_url = handle_pagination(soup, current_url, solution_type)
        
        if next_url == current_url: # Should be caught by handle_pagination, but double-check
            print("Error: Pagination returned the same URL. Stopping section crawl to prevent loop.")
            break 
        
        current_url = next_url # Move to the next URL for the next iteration
        
        if not current_url:
            # This means handle_pagination returned None, indicating the end of pagination
            print(f"No more pages found for {section_type} section.")
            section_completed_normally = True
            break # Exit the while loop cleanly

        page_num += 1
        
        # Save partial results after each *successful* page processing cycle
        save_partial_results()
    
    # --- Post-Loop Completion Logic ---
    if section_completed_normally:
        print(f"Successfully completed crawling all pages for {section_type}.")
        crawl_state[state_key] = None  # Mark as completed by setting state to None
        print(f"Marking {section_type} as complete in crawl state.")
    elif max_retries_reached_on_page:
         print(f"Stopped crawling {section_type} due to max retries reached on URL: {crawl_state[state_key]}")
         # State already points to the failed URL, so it will retry next time
    elif max_pages is not None and page_num > max_pages:
         print(f"Stopped crawling {section_type} after reaching max_pages limit ({max_pages}).")
         # State points to the *next* page that *would* have been crawled
    else:
         print(f"Stopped crawling {section_type} for an unknown reason. Last attempted URL: {crawl_state.get(state_key)}")
         # State should point to the last attempted URL

    save_crawl_state() # Save the final state for this section (completed or last attempted URL)
    
    return section_assessments_this_run

def crawl_shl_assessments(max_pages=None):
    """
    Main function to crawl SHL assessments and save data to JSON.
    
    Args:
        max_pages (int, optional): Maximum number of pages to crawl per section. If None, crawl all pages.
    
    Returns:
        list: List of assessment dictionaries with all details
    """
    global all_assessments, processed_urls, crawl_state
    start_time = datetime.now()
    
    # Load existing assessments AND crawl state first
    load_existing_assessments() # Populates all_assessments and processed_urls
    load_crawl_state() # Populates crawl_state

    # Reset completion flag if forcing a full recrawl (e.g., by deleting state file)
    if not crawl_state.get("last_crawl_time"):
        crawl_state["completed"] = False
        
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Check if the crawl was already fully completed
        if crawl_state.get('completed', False):
            print("\n>>> Previous crawl reported as fully completed. <<<")
            print(f">>> Found {len(all_assessments)} assessments in {OUTPUT_FILE}. <<<")
            print(">>> To re-run the full crawl, delete the state file: " + METADATA_FILE + " <<<")
            return all_assessments # Exit early if completed

        # --- Main Page Crawl (Less critical now with state, but good for initial seed) ---
        # Only run if BOTH sections haven't even been started yet according to state.
        if not crawl_state.get('pre_packaged_last_page') and not crawl_state.get('individual_last_page') and not crawl_state.get('last_crawl_time'):
            print("\n--- Crawling Main Catalog Page (Initial Seed) ---")
            soup = get_page_content(CATALOG_URL)
            
            if soup:
                # Extract links - handle potential overlap by checking processed_urls
                main_page_assessments = []
                main_page_assessments.extend(extract_assessment_links(soup, 'pre-packaged'))
                main_page_assessments.extend(extract_assessment_links(soup, 'individual'))
                
                print(f"Found {len(main_page_assessments)} potential new assessments on main page.")
                
                # Process assessments found on main page
                for i, assessment in enumerate(main_page_assessments):
                     if assessment['url'] in processed_urls and any(a['url'] == assessment['url'] for a in all_assessments):
                          continue # Skip if already loaded or processed

                     print(f"Processing main page assessment {i+1}/{len(main_page_assessments)}: {assessment['name']}")
                     updated_assessment = extract_assessment_details(assessment)
                     if not any(a['url'] == updated_assessment['url'] for a in all_assessments):
                          all_assessments.append(updated_assessment)
                          processed_urls.add(updated_assessment['url'])
                          if (len(all_assessments) % 10) == 0:
                              save_partial_results()
                     elif updated_assessment.get('details_extracted', False):
                          for idx, existing_assessment in enumerate(all_assessments):
                              if existing_assessment['url'] == updated_assessment['url']:
                                   all_assessments[idx] = updated_assessment
                                   break
                save_partial_results() # Save after processing main page
            else:
                 print("Failed to fetch main catalog page. Skipping initial seed.")
        else:
             print("\nSkipping main catalog page crawl (state indicates progress or prior run).")


        # --- Crawl Pre-packaged Job Solutions section ---
        pre_packaged_state_key = 'pre_packaged_last_page'
        # Crawl if state exists (resume) OR if it's None (start fresh/section not completed)
        # but only if the overall crawl isn't marked completed yet.
        if not crawl_state.get('completed', False) and crawl_state.get(pre_packaged_state_key, 0) is not None:
            print("\n--- Starting/Resuming Pre-packaged Job Solutions Section ---")
            pre_packaged_url = f"{CATALOG_URL}?type={PRE_PACKAGED_TYPE}"
            crawl_section(pre_packaged_url, 'pre-packaged', PRE_PACKAGED_TYPE, max_pages)
        else:
            print("\nSkipping Pre-packaged Job Solutions section (marked as completed in state).")
        
        # --- Crawl Individual Test Solutions section ---
        individual_state_key = 'individual_last_page'
        # Logic same as above
        if not crawl_state.get('completed', False) and crawl_state.get(individual_state_key, 0) is not None:
            print("\n--- Starting/Resuming Individual Test Solutions Section ---")
            individual_url = f"{CATALOG_URL}?type={INDIVIDUAL_TYPE}"
            crawl_section(individual_url, 'individual', INDIVIDUAL_TYPE, max_pages)
        else:
            print("\nSkipping Individual Test Solutions section (marked as completed in state).")
        
        # --- Final Check for Completion ---
        # Mark overall crawl as completed ONLY if both sections are marked complete (state is None)
        if crawl_state.get(pre_packaged_state_key) is None and crawl_state.get(individual_state_key) is None:
            print("\nBoth sections reported as complete.")
            crawl_state['completed'] = True
            save_crawl_state() # Save the final completed state
        else:
             print("\nCrawl finished, but one or both sections may be incomplete or pending retry.")
             crawl_state['completed'] = False # Ensure it's marked as not fully complete
             save_crawl_state()

        # Save the final consolidated data
        print(f"\nSaving final results ({len(all_assessments)} assessments) to {OUTPUT_FILE}")
        try:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_assessments, f, indent=2, ensure_ascii=False)
            print(f"Final data saved successfully to {OUTPUT_FILE}")
        except IOError as e:
             print(f"Error saving final data: {e}")

        end_time = datetime.now()
        print(f"\nCrawling finished at: {end_time}")
        print(f"Total duration: {end_time - start_time}")
        print(f"Total assessments found: {len(all_assessments)}")
        
        return all_assessments
    
    except Exception as e:
        print(f"\n--- An unexpected error occurred during crawling ---")
        import traceback
        print(traceback.format_exc())
        print(f"Error: {e}")
        print("Attempting to save partial results before exiting...")
        save_partial_results()
        return all_assessments

if __name__ == "__main__":
    # Set max_pages to None to crawl all pages, or a number to limit pages per section
    crawl_shl_assessments(max_pages=None)
