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
import hashlib

# Add Rich library for beautiful terminal output
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

# Initialize Rich console
console = Console()

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
# Track processed page URLs to avoid re-processing pages
processed_pages = set()
# Global crawl state to track progress
crawl_state = {
    "last_crawl_time": None,
    "pre_packaged_last_page": None,
    "pre_packaged_page_num": 1,
    "individual_last_page": None,
    "individual_page_num": 1,
    "completed": False,
    "processed_pages": []  # Store processed page URLs in state
}

def display_assessments_table(assessments, title="Assessments Found"):
    """Display assessments in a beautiful table format using Rich."""
    if not assessments:
        console.print("[yellow]No assessments to display[/yellow]")
        return
        
    # Create a table
    table = Table(title=title, show_header=True, header_style="bold magenta")
    
    # Add columns
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Remote", justify="center", style="green")
    table.add_column("Adaptive", justify="center", style="green")
    table.add_column("Duration", justify="center", style="blue")
    table.add_column("Test Types", style="yellow")
    table.add_column("Description", style="white", max_width=50, overflow="fold")
    
    # Add rows - limit to 20 most recent for display clarity
    display_count = min(len(assessments), 20)
    for assessment in assessments[-display_count:]:
        name = assessment.get('name', 'N/A')
        remote = assessment.get('remote_testing_support', 'No')
        adaptive = assessment.get('adaptive_irt_support', 'No')
        duration = assessment.get('duration', 'N/A')
        
        # Format test types
        test_types = assessment.get('test_types', [])
        if isinstance(test_types, list):
            test_types_str = ", ".join(test_types) if test_types else "N/A"
        else:
            test_types_str = str(test_types)
            
        description = assessment.get('description', 'N/A')
        if description and len(description) > 50:
            description = description[:47] + "..."
            
        table.add_row(
            name,
            "[green]Yes[/green]" if remote == "Yes" else "[red]No[/red]",
            "[green]Yes[/green]" if adaptive == "Yes" else "[red]No[/red]",
            duration or "N/A",
            test_types_str,
            description
        )
        
    console.print(table)
    
    if len(assessments) > display_count:
        console.print(f"[i]Showing {display_count} of {len(assessments)} assessments[/i]")

def generate_page_fingerprint(url, assessment_urls):
    """Generate a unique fingerprint for a page based on its URL and assessment URLs."""
    # Create a string representation of the assessment URLs
    assessment_str = ",".join(sorted(assessment_urls))
    # Combine with the page URL
    combined = f"{url}|{assessment_str}"
    # Generate a hash
    return hashlib.md5(combined.encode()).hexdigest()

def save_crawl_state():
    """Save the current crawl state to a metadata file."""
    global crawl_state, processed_pages
    
    # Update the last crawl time
    crawl_state["last_crawl_time"] = datetime.now().isoformat()
    
    # Save processed pages to state
    crawl_state["processed_pages"] = list(processed_pages)
    
    with console.status("[bold green]Saving crawl state...[/bold green]"):
        try:
            with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(crawl_state, f, indent=2, ensure_ascii=False)
            console.print("[green]✓[/green] Crawl state saved successfully.")
        except Exception as e:
            console.print(f"[bold red]✗ Error saving crawl state: {e}[/bold red]")

def load_crawl_state():
    """Load the previous crawl state if it exists."""
    global crawl_state, processed_pages
    
    if os.path.exists(METADATA_FILE):
        with console.status("[bold blue]Loading existing crawl state...[/bold blue]"):
            try:
                with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                    loaded_state = json.load(f)
                    crawl_state.update(loaded_state)
                
                # Load processed pages from state
                if "processed_pages" in crawl_state:
                    processed_pages = set(crawl_state["processed_pages"])
                    
                # Display crawl state information in a panel
                state_panel = Panel.fit(
                    f"[bold]Last crawl:[/bold] {crawl_state.get('last_crawl_time', 'N/A')}\n"
                    f"[bold]Pre-packaged page:[/bold] {crawl_state.get('pre_packaged_page_num', 1)}\n"
                    f"[bold]Individual page:[/bold] {crawl_state.get('individual_page_num', 1)}\n"
                    f"[bold]Completed:[/bold] {'Yes' if crawl_state.get('completed', False) else 'No'}\n"
                    f"[bold]Processed pages:[/bold] {len(processed_pages)}",
                    title="[bold]Crawl State[/bold]",
                    border_style="blue"
                )
                console.print(state_panel)
                
                return True
            except Exception as e:
                console.print(f"[bold red]✗ Error loading crawl state: {e}[/bold red]")
                return False
    else:
        console.print("[yellow]No existing crawl state found. Starting fresh crawl.[/yellow]")
        return False

def load_existing_assessments():
    """Load existing assessments from the output file if it exists."""
    global all_assessments, processed_urls
    
    if os.path.exists(OUTPUT_FILE):
        with console.status("[bold blue]Loading existing assessment data...[/bold blue]"):
            try:
                with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                    existing_assessments = json.load(f)
                    
                # Add existing assessments to the global list
                all_assessments = existing_assessments
                
                # Add all URLs to processed_urls set
                for assessment in existing_assessments:
                    if 'url' in assessment:
                        processed_urls.add(assessment['url'])
                
                console.print(f"[green]✓[/green] Loaded [bold]{len(all_assessments)}[/bold] existing assessments.")
                
                # Display a sample of existing assessments
                display_assessments_table(
                    all_assessments[:10], 
                    f"Sample of Existing Assessments (Total: {len(all_assessments)})"
                )
                
                return True
            except Exception as e:
                console.print(f"[bold red]✗ Error loading existing assessments: {e}[/bold red]")
                return False
    else:
        console.print("[yellow]No existing assessment data found. Starting fresh collection.[/yellow]")
        return False

def save_partial_results():
    """Save the current results to a partial output file."""
    global all_assessments
    
    with console.status(f"[bold green]Saving partial results ({len(all_assessments)} assessments)...[/bold green]"):
        try:
            with open(PARTIAL_OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_assessments, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✓[/green] Partial results saved to [bold]{PARTIAL_OUTPUT_FILE}[/bold]")
        except Exception as e:
            console.print(f"[bold red]✗ Error saving partial results: {e}[/bold red]")
    
    # Also save the current crawl state
    save_crawl_state()

def signal_handler(sig, frame):
    """Handle Ctrl+C and other termination signals."""
    console.print("\n[bold yellow]⚠ Crawling interrupted. Saving partial results...[/bold yellow]")
    save_partial_results()
    
    # Display summary before exit
    console.print(Panel.fit(
        f"[bold]Total assessments collected:[/bold] {len(all_assessments)}\n"
        f"[bold]Last URL processed:[/bold] {crawl_state.get('pre_packaged_last_page') or crawl_state.get('individual_last_page')}\n"
        f"[bold]Data saved to:[/bold] {PARTIAL_OUTPUT_FILE}",
        title="[bold red]Crawl Interrupted[/bold red]",
        border_style="red"
    ))
    
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
        # Add a short random delay to avoid being blocked
        delay = random.uniform(0.3, 0.8)
        with console.status(f"[bold cyan]Waiting {delay:.2f}s before fetching...[/bold cyan]"):
            time.sleep(delay)
        
        with console.status(f"[bold cyan]Fetching {url}...[/bold cyan]"):
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            console.print(f"[green]✓[/green] Fetched page [dim]{url}[/dim] [green]({len(response.text)} bytes)[/green]")
            return BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]✗ Error fetching {url}: {e}[/bold red]")
        return None

def extract_assessment_links(soup, section_type):
    """
    Extract assessment links from the catalog page.
    
    Args:
        soup (BeautifulSoup): Parsed HTML of the catalog page
        section_type (str): Type of section ('pre-packaged' or 'individual')
        
    Returns:
        list: List of dictionaries with assessment names and URLs
        list: List of all assessment URLs found on page (for page fingerprinting)
    """
    assessments = []
    all_found_urls = []  # Track all URLs found on this page
    
    # Find the section header based on section type
    if section_type == 'pre-packaged':
        section_header = soup.find(string=re.compile('Pre-packaged Job Solutions', re.IGNORECASE))
    else:
        section_header = soup.find(string=re.compile('Individual Test Solutions', re.IGNORECASE))
    
    if not section_header:
        console.print(f"Warning: Could not find section header for {section_type} on the page")
        # Try to find assessment links directly if we're on a section-specific page
        if section_type == 'pre-packaged' and 'type=2' in soup.get_text():
            section = soup
        elif section_type == 'individual' and 'type=1' in soup.get_text():
            section = soup
        else:
            return assessments, all_found_urls
    else:
        # Find the table rows containing assessments
        section = section_header.find_parent('div')
        if not section:
            console.print(f"Warning: Could not find section container for {section_type}")
            return assessments, all_found_urls
    
    # Find all assessment links in this section
    assessment_links = section.find_all('a')
    
    for link in assessment_links:
        name = link.get_text(strip=True)
        href = link.get('href')
        
        if not href:
            continue
            
        url = urljoin(BASE_URL, href)
        
        # Skip if it's not a valid assessment link
        if not name or not url or not url.startswith(BASE_URL):
            continue
            
        # Add to all found URLs for page fingerprinting
        all_found_urls.append(url)
            
        # Skip if we've already processed this URL
        if url in processed_urls:
            console.print(f"Skipping already processed URL: {url}")
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
    
    return assessments, all_found_urls

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
    # First try to find the h4 Description heading and its sibling p tag
    description_heading = soup.find('h4', string=re.compile('Description', re.IGNORECASE))
    if description_heading:
        # Find the sibling paragraph tag that contains the full description
        description_p = description_heading.find_next_sibling('p')
        if description_p:
            assessment['description'] = description_p.get_text().strip()
    
    # If no description found via h4+p, fallback to meta tag
    if not assessment['description']:
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
    # Debug section: inspect pagination area if possible
    pagination_area = soup.find('div', class_=re.compile('pagination|paging'))
    if pagination_area:
        console.print(f"Found pagination area with {len(pagination_area.find_all('a'))} links")
    else:
        console.print("No pagination div found, searching broadly for Next link")
    
    # Look for "Next" link in pagination (try multiple approaches)
    next_link = None
    
    # Method 1: Standard link with "Next" text
    next_candidates = soup.find_all('a', string=re.compile('Next', re.IGNORECASE))
    if next_candidates:
        console.print(f"Found {len(next_candidates)} 'Next' text links")
        next_link = next_candidates[0]
    
    # Method 2: Link with a next/arrow class
    if not next_link:
        next_candidates = soup.find_all('a', class_=re.compile('next|arrow|forward', re.IGNORECASE))
        if next_candidates:
            console.print(f"Found {len(next_candidates)} links with next/arrow class")
            next_link = next_candidates[0]
    
    # Method 3: Look for pagination elements and find the one after current
    if not next_link:
        # Try to find the current page marker and get the next sibling
        current_page = soup.find('a', class_=re.compile('active|current', re.IGNORECASE))
        if current_page:
            next_sibling = current_page.find_next_sibling('a')
            if next_sibling:
                console.print("Found next page link via current page sibling")
                next_link = next_sibling
    
    # Method 4: Find "start" parameter in URL and increment it
    if not next_link:
        parsed_url = urlparse(current_url)
        query_params = parse_qs(parsed_url.query)
        
        if 'start' in query_params:
            try:
                # SHL uses 'start' parameter with multiples of 12 (0, 12, 24, etc.)
                start = int(query_params['start'][0])
                
                # Check if there might be a last page condition
                # If we're already at a high start value and found no assessments, assume end
                if start > 500:
                    # This might be the last page, look for content indicators
                    last_page_indicators = [
                        "end of results", "last page", "no more results", "no more products"
                    ]
                    page_text = soup.get_text().lower()
                    if any(indicator in page_text for indicator in last_page_indicators):
                        console.print("[yellow]End of pagination detected based on page content and high start value.[/yellow]")
                        return None
                
                # Create a new URL with incremented start parameter
                query_params['start'] = [str(start + 12)]
                query_params['type'] = [solution_type]  # Ensure type parameter
                
                # Reconstruct URL
                query_string = urlencode(query_params, doseq=True)
                parts = list(parsed_url)
                parts[4] = query_string
                
                next_url = urlunparse(parts)
                
                # Check if we'd be creating the same URL as current (which would create a loop)
                if next_url == current_url:
                    console.print("[yellow]Generated next URL would be identical to current URL. Stopping pagination.[/yellow]")
                    return None
                    
                console.print(f"Created next URL by incrementing start parameter: {next_url}")
                return next_url
            except (ValueError, IndexError):
                pass
        elif 'start' not in query_params and 'page=1' in current_url:
            # If we're on page 1 but no start parameter, add it
            query_params['start'] = ['12']  # Move to items 13-24
            query_params['type'] = [solution_type]
            
            query_string = urlencode(query_params, doseq=True)
            parts = list(parsed_url)
            parts[4] = query_string
            
            next_url = urlunparse(parts)
            console.print(f"Created first pagination URL with start=12: {next_url}")
            return next_url
        elif 'start' not in query_params:
            # If we're on first page with no parameters yet
            base_url = f"{CATALOG_URL}?type={solution_type}&start=12"
            console.print(f"Created first pagination URL: {base_url}")
            return base_url
    
    # Process the next link if found by any method
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
            console.print("Warning: Next URL is the same as current URL. Stopping pagination.")
            return None
            
        console.print(f"Found valid next page URL: {next_url}")
        return next_url
    
    # If we're on a URL without start parameter, add it for the first pagination
    if 'start=' not in current_url:
        next_url = f"{current_url}{'&' if '?' in current_url else '?'}start=12"
        console.print(f"No explicit next link found, trying basic pagination: {next_url}")
        return next_url
    
    console.print("No next page found after trying all methods")
    return None

def crawl_section(start_url, section_type, solution_type, max_pages=None):
    """
    Crawl a specific section (Pre-packaged or Individual) of the SHL catalog.
    Uses direct pagination with start=12, start=24, etc. instead of looking for next buttons.
    
    Args:
        start_url (str): Starting URL for this section (containing type parameter)
        section_type (str): Type of section ('pre-packaged' or 'individual')
        solution_type (str): Type parameter value ('1' for individual, '2' for pre-packaged)
        max_pages (int, optional): Maximum number of pages to crawl. If None, crawl all pages.
    
    Returns:
        list: List of assessment dictionaries for this section
    """
    global all_assessments, crawl_state, processed_pages
    section_assessments = []
    
    # Create a section header panel
    header_style = "green" if section_type == 'pre-packaged' else "blue"
    section_title = "Pre-packaged Job Solutions" if section_type == 'pre-packaged' else "Individual Test Solutions"
    console.print(Panel.fit(
        f"[bold]Type ID:[/bold] {solution_type}\n"
        f"[bold]Starting URL:[/bold] {start_url}\n"
        f"[bold]Maximum Pages:[/bold] {'Unlimited' if max_pages is None else max_pages}",
        title=f"[bold {header_style}]CRAWLING {section_title.upper()}[/bold {header_style}]",
        border_style=header_style
    ))
    
    # Initialize current start parameter
    current_start = 0
    empty_page_count = 0  # Counter for consecutive empty pages
    max_empty_pages = 2   # Maximum number of consecutive empty pages before stopping
    
    # Check if we should resume from a previous state
    if section_type == 'pre-packaged' and crawl_state.get('pre_packaged_start'):
        current_start = crawl_state.get('pre_packaged_start')
        console.print(f"[bold yellow]Resuming from previous state with start={current_start}[/bold yellow]")
    elif section_type == 'individual' and crawl_state.get('individual_start'):
        current_start = crawl_state.get('individual_start')
        console.print(f"[bold yellow]Resuming from previous state with start={current_start}[/bold yellow]")
    
    page_assessments_count = []  # Track number of assessments per page
    page_num = 1
    
    # First, crawl the home page (start=0) if this is just starting
    if current_start == 0:
        # Construct URL for the main page
        # The main catalog page with type parameter
        if '?' in start_url:
            current_url = start_url
        else:
            current_url = f"{start_url}?type={solution_type}"
            
        console.rule(f"[bold {header_style}]HOME PAGE: {section_type.upper()}[/bold {header_style}]")
        console.print(f"[cyan]URL:[/cyan] {current_url}")
        
        # Save state
        if section_type == 'pre-packaged':
            crawl_state['pre_packaged_start'] = current_start
        else:
            crawl_state['individual_start'] = current_start
        save_crawl_state()
        
        # Skip if already processed
        if current_url in processed_pages:
            console.print("[bold green]✓ Skipping already processed home page[/bold green]")
        else:
            # Process the home page
            soup = get_page_content(current_url)
            if soup:
                with console.status("[bold green]Extracting assessments from home page...[/bold green]"):
                    page_assessments, all_found_urls = extract_assessment_links(soup, section_type)
                
                # Mark page as processed
                processed_pages.add(current_url)
                
                console.print(f"[bold green]✓ Found {len(page_assessments)} {section_type} solutions on home page[/bold green]")
                page_assessments_count.append(len(page_assessments))
                
                # Process assessments from this page
                if page_assessments:
                    process_page_assessments(page_assessments, section_assessments)
        
        # Move to first paginated page (start=12)
        current_start = 12
    
    # Now crawl all pages with the start parameter
    while (max_pages is None or page_num <= max_pages) and empty_page_count < max_empty_pages:
        # Construct URL with current start parameter
        parsed_url = urlparse(start_url)
        query_params = parse_qs(parsed_url.query) if parsed_url.query else {}
        query_params['type'] = [solution_type]
        query_params['start'] = [str(current_start)]
        
        query_string = urlencode(query_params, doseq=True)
        parts = list(parsed_url)
        parts[4] = query_string
        current_url = urlunparse(parts)
        
        console.rule(f"[bold {header_style}]PAGE {page_num}: {section_type.upper()} (start={current_start})[/bold {header_style}]")
        console.print(f"[cyan]URL:[/cyan] {current_url}")
        
        # Save state
        if section_type == 'pre-packaged':
            crawl_state['pre_packaged_start'] = current_start
        else:
            crawl_state['individual_start'] = current_start
        save_crawl_state()
        
        # Skip if already processed
        if current_url in processed_pages:
            console.print(f"[bold green]✓ Skipping already processed page (start={current_start})[/bold green]")
            # Continue to next page
            current_start += 12
            page_num += 1
            continue
        
        # Add delay to avoid rate limiting
        delay = random.uniform(0.2, 0.8)
        with console.status(f"[bold cyan]Waiting {delay:.2f}s before fetching...[/bold cyan]"):
            time.sleep(delay)
        
        # Fetch and process page
        soup = get_page_content(current_url)
        
        if not soup:
            console.print(f"[bold red]✗ Failed to fetch content for {current_url}[/bold red]")
            empty_page_count += 1
            if empty_page_count >= max_empty_pages:
                console.print(f"[bold red]Too many empty pages ({empty_page_count}). Ending pagination.[/bold red]")
                break
            # Try next page anyway
            current_start += 12
            page_num += 1
            continue
        
        # Extract assessments from this page
        with console.status("[bold green]Extracting assessments from page...[/bold green]"):
            page_assessments, all_found_urls = extract_assessment_links(soup, section_type)
        
        # Mark this page as processed
        processed_pages.add(current_url)
        
        console.print(f"[bold green]✓ Found {len(page_assessments)} {section_type} solutions (start={current_start})[/bold green]")
        page_assessments_count.append(len(page_assessments))
        
        # Check if we should stop (no more assessments found)
        if len(all_found_urls) == 0:
            console.print("[bold yellow]No assessment links found on page. Checking next page...[/bold yellow]")
            empty_page_count += 1
            if empty_page_count >= max_empty_pages:
                console.print(f"[bold yellow]Reached {empty_page_count} consecutive empty pages. Assuming end of section.[/bold yellow]")
                break
        else:
            # Reset empty page counter if we found links
            empty_page_count = 0
            
            # Process assessments from this page
            if page_assessments:
                process_page_assessments(page_assessments, section_assessments)
            elif len(all_found_urls) > 0:
                console.print("[bold green]All assessments on this page were already processed.[/bold green]")
        
        # Move to next page
        current_start += 12
        page_num += 1
        
        # Save partial results after each page
        save_partial_results()
    
    # Display summary table for this section
    section_summary = Table(title=f"{section_title} Crawl Summary", show_header=True, header_style="bold")
    section_summary.add_column("Metric", style="cyan")
    section_summary.add_column("Value", style="green")
    
    section_summary.add_row("Pages Crawled", str(page_num - 1))
    section_summary.add_row("Total Assessments", str(len(section_assessments)))
    section_summary.add_row("Assessments Per Page", ", ".join([str(count) for count in page_assessments_count]))
    
    console.print(section_summary)
    
    # Mark section as completed
    if section_type == 'pre-packaged':
        console.print(f"[bold green]✓ Marking pre-packaged section as complete after finding {len(section_assessments)} assessments.[/bold green]")
        crawl_state['pre_packaged_start'] = None
    else:
        console.print(f"[bold green]✓ Marking individual section as complete after finding {len(section_assessments)} assessments.[/bold green]")
        crawl_state['individual_start'] = None
    save_crawl_state()
    
    return section_assessments

def process_page_assessments(page_assessments, section_assessments):
    """Process assessments found on a page."""
    global all_assessments
    
    console.print("[bold green]Processing assessments details:[/bold green]")
    
    # Create progress bar for assessment processing
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn()
    ) as progress:
        task = progress.add_task(f"Processing {len(page_assessments)} assessments", total=len(page_assessments))
        
        for i, assessment in enumerate(page_assessments):
            progress.update(task, description=f"Processing: {assessment['name'][:30]}...")
            updated_assessment = extract_assessment_details(assessment)
            section_assessments.append(updated_assessment)
            all_assessments.append(updated_assessment)
            progress.update(task, advance=1)
            
            # Save partial results every 12 assessments
            if (len(all_assessments) % 12) == 0:
                save_partial_results()
    
    # Display the assessments found on this page
    display_assessments_table(
        page_assessments, 
        f"Assessments Found on Page ({len(page_assessments)} items)"
    )

def crawl_shl_assessments(max_pages=None):
    """
    Main function to crawl SHL assessments and save data to JSON.
    Sequential approach: first all pre-packaged solutions, then all individual solutions.
    
    Args:
        max_pages (int, optional): Maximum number of pages to crawl per section. If None, crawl all pages.
    
    Returns:
        list: List of assessment dictionaries with all details
    """
    global all_assessments, processed_urls, crawl_state, processed_pages
    
    # Display welcome banner
    console.print(Panel.fit(
        "[bold]This script crawls SHL's product catalog to extract assessment information[/bold]\n\n"
        "• Assessment name and URL\n"
        "• Remote Testing Support (Yes/No)\n"
        "• Adaptive/IRT Support (Yes/No)\n"
        "• Duration\n"
        "• Test types (Ability, Behavioral, etc.)\n"
        "• Description\n\n"
        "[dim]Press Ctrl+C at any time to save progress and exit[/dim]",
        title="[bold]SHL Assessment Data Crawler[/bold]",
        border_style="green",
        padding=(1, 2)
    ))
    
    start_time = datetime.now()
    
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
        console.rule("[bold green]STARTING SEQUENTIAL CRAWL: Pre-packaged first, then Individual[/bold green]")
        
        # Always reset the completion status at the start
        crawl_state['completed'] = False
        
        # First, scrape the main catalog page to seed some initial data
        # This step is now integrated into crawl_section with start=0
        
        # =======================================================
        # STEP 1: CRAWL ALL PRE-PACKAGED JOB SOLUTIONS FIRST
        # =======================================================
        console.rule("[bold green]STARTING/RESUMING PRE-PACKAGED JOB SOLUTIONS[/bold green]")
        console.print("[dim](This must complete fully before moving to Individual Solutions)[/dim]")
        
        # Call crawl_section for Pre-packaged Job Solutions
        console.print("[bold green]Starting Pre-packaged section crawl...[/bold green]")
        pre_packaged_url = CATALOG_URL
        pre_packaged_results = crawl_section(pre_packaged_url, 'pre-packaged', PRE_PACKAGED_TYPE, max_pages)
        
        console.print(Panel.fit(
            f"[bold]Total assessments found:[/bold] {len(pre_packaged_results)}",
            title="[bold green]COMPLETED PRE-PACKAGED JOB SOLUTIONS[/bold green]",
            border_style="green"
        ))
        
        # Save intermediate results after pre-packaged section
        save_partial_results()
        
        # =======================================================
        # STEP 2: CRAWL ALL INDIVIDUAL TEST SOLUTIONS NEXT
        # =======================================================
        console.rule("[bold blue]STARTING/RESUMING INDIVIDUAL TEST SOLUTIONS[/bold blue]")
        
        # Call crawl_section for Individual Test Solutions
        console.print("[bold blue]Starting Individual section crawl...[/bold blue]")
        individual_url = CATALOG_URL
        individual_results = crawl_section(individual_url, 'individual', INDIVIDUAL_TYPE, max_pages)
        
        console.print(Panel.fit(
            f"[bold]Total assessments found:[/bold] {len(individual_results)}",
            title="[bold blue]COMPLETED INDIVIDUAL TEST SOLUTIONS[/bold blue]",
            border_style="blue"
        ))
        
        # ===================================================
        # SAVE FINAL RESULTS
        # ===================================================
        
        # Now mark crawl as completed since we've done both sections sequentially
        crawl_state['completed'] = True
        save_crawl_state()
        
        # Save the final data to the main output file
        with console.status(f"[bold green]Saving final results ({len(all_assessments)} assessments)...[/bold green]"):
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_assessments, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✓ Final data saved to {OUTPUT_FILE}[/green]")
        
        # Create final summary table
        end_time = datetime.now()
        duration = end_time - start_time
        
        summary = Table(title="Crawl Summary", show_header=True, header_style="bold magenta")
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="green")
        
        summary.add_row("Start Time", start_time.strftime("%Y-%m-%d %H:%M:%S"))
        summary.add_row("End Time", end_time.strftime("%Y-%m-%d %H:%M:%S"))
        summary.add_row("Duration", str(duration))
        summary.add_row("Pre-packaged Assessments", str(len(pre_packaged_results)))
        summary.add_row("Individual Assessments", str(len(individual_results)))
        summary.add_row("Total Assessments", str(len(all_assessments)))
        summary.add_row("Output File", OUTPUT_FILE)
        
        console.print(Panel.fit(
            summary,
            title="[bold green]CRAWLING COMPLETE[/bold green]",
            border_style="green",
            padding=(1, 2)
        ))
        
        return all_assessments
    
    except Exception as e:
        console.print(f"[bold red]Error during crawling: {e}[/bold red]")
        console.print_exception()
        save_partial_results()
        return all_assessments

if __name__ == "__main__":
    # Set max_pages to None to crawl all pages, or a number to limit pages per section
    crawl_shl_assessments(max_pages=None)
