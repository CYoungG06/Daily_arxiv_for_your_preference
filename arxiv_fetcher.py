import re
import json
import arxiv
import logging
import yaml
import datetime
from typing import List, Optional, Dict, Any
from datetime import date, timedelta

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%m/%d/%Y %H:%M:%S',
)

arxiv_url = "http://arxiv.org/"

def parse_single_filter(filter_str: str) -> str:
    """Parse a single filter string."""
    if not filter_str:
        return ""
    
    ESCAPE = '"'
    if len(filter_str.split()) > 1:
        return f"{ESCAPE}{filter_str}{ESCAPE}"
    return filter_str

def parse_filter_list(filters: list) -> str:
    """Parse a list of filters."""
    OR = " OR "
    return OR.join([parse_single_filter(f) for f in filters])

def process_keywords(keywords_dict: dict) -> dict:
    """Process keywords dictionary."""
    keywords = {}
    for k, v in keywords_dict.items():
        keywords[k] = parse_filter_list(v)
    return keywords

def load_config(config_file: str = None, config_dict: dict = None) -> dict:
    """Load configuration from a YAML file or dictionary."""
    try:
        if config_file:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        elif config_dict:
            config = config_dict
        else:
            raise ValueError("Either config_file or config_dict must be provided.")
        
        if not config:
            raise ValueError("Empty configuration.")
        
        return config
    
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        return {}

class ArxivPaperFetcher:
    def __init__(self, arxiv_url: str = arxiv_url):
        self.arxiv_url = arxiv_url

    @staticmethod
    def get_authors(authors, first_author=False):
        """Get authors from the author list as strings."""
        if first_author and authors:
            return str(authors[0])
        return ", ".join(str(author) for author in authors)
    
    def get_paper_key(self, paper_id: str) -> str:
        """Remove the version number from the paper ID."""
        return paper_id.split("v")[0]
    
    def format_paper_info(self, paper_key: str, update_time: date, paper_title: str, 
                          paper_first_author: str, paper_authors: str, paper_url: str, 
                          comments: Optional[str], category: str,
                          paper_summary: str) -> Dict[str, Any]:
        """Format the paper information into a structured dictionary."""
        paper_info = {
            "id": paper_key,
            "title": paper_title,
            "url": paper_url,
            "update_date": str(update_time),
            "first_author": paper_first_author,
            "authors": paper_authors,
            "category": category,
            "abstract": paper_summary,
            "comments": comments if comments else ""
        }
        
        return paper_info
    
    def get_papers(self, topic: str, query: str, max_results: int = 50, 
                  date_from: Optional[date] = None, date_to: Optional[date] = None,
                  categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get papers from arXiv that match the criteria."""
        papers = []
        search_engine = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        for result in search_engine.results():
            update_time = result.updated.date()
            
            # Apply date filter if specified
            if date_from and update_time < date_from:
                continue
            if date_to and update_time > date_to:
                continue
                
            # Apply category filter if specified
            primary_category = result.primary_category
            if categories and primary_category not in categories:
                continue
                
            paper_id = result.get_short_id()
            paper_title = result.title
            paper_summary = result.summary.replace("\n", " ")
            
            # Convert author objects to strings
            paper_first_author = self.get_authors(result.authors, first_author=True)
            paper_authors = self.get_authors(result.authors)
            
            comments = result.comment
            
            logging.info(f"Found paper: {update_time} - {paper_title} - {paper_first_author} - {primary_category}")

            paper_key = self.get_paper_key(paper_id)
            paper_url = f"{self.arxiv_url}abs/{paper_key}"

            try:
                paper_info = self.format_paper_info(
                    paper_key, update_time, paper_title, paper_first_author, 
                    paper_authors, paper_url, comments, primary_category, paper_summary
                )
                
                papers.append(paper_info)
                
            except Exception as e:
                logging.error(f"Error processing paper {paper_key}: {e}")
        
        return papers
    
    def batch_papers(self, papers: List[Dict[str, Any]], batch_size: int = 5) -> List[List[Dict[str, Any]]]:
        """Split papers into batches."""
        return [papers[i:i + batch_size] for i in range(0, len(papers), batch_size)]

def fetch_papers(keywords_dict: Dict[str, List[str]], max_results: int = 50, 
                date_from: Optional[str] = None, date_to: Optional[str] = None,
                categories: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch papers based on keywords dictionary.
    
    Args:
        keywords_dict: Dictionary mapping topics to lists of filter terms.
        max_results: Maximum number of results per topic.
        date_from: Start date in 'YYYY-MM-DD' format.
        date_to: End date in 'YYYY-MM-DD' format.
        categories: List of arXiv categories to filter by.
        
    Returns:
        A dictionary mapping topics to lists of paper dictionaries.
    """
    # Process keywords
    processed_keywords = process_keywords(keywords_dict)
    
    # Parse date strings to date objects if provided
    from_date = None
    to_date = None
    if date_from:
        from_date = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
    if date_to:
        to_date = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Initialize paper fetcher
    fetcher = ArxivPaperFetcher()
    
    # Fetch papers for each topic
    result = {}
    for topic, query in processed_keywords.items():
        logging.info(f"Fetching papers for topic: {topic} with query: {query}")
        papers = fetcher.get_papers(
            topic=topic,
            query=query,
            max_results=max_results,
            date_from=from_date,
            date_to=to_date,
            categories=categories
        )
        
        if papers:
            # Sort papers by date (most recent first)
            papers.sort(key=lambda x: x["update_date"], reverse=True)
            result[topic] = papers
            
            logging.info(f"Found {len(papers)} papers for topic '{topic}'")
        else:
            logging.info(f"No papers found for topic '{topic}'")
    
    return result