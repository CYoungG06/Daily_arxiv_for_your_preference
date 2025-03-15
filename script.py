import os
import re
import json
import arxiv
import logging
import yaml
import argparse
import datetime
import requests
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, timedelta


logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%m/%d/%Y %H:%M:%S',
    )

arxiv_url = "http://arxiv.org/"


def parse_single_filter(filter_str: str) -> str:
    """
    Parse a single filter string.
    """
    if not filter_str:
        return ""
    
    ESCAPE = '"'
    if len(filter_str.split()) > 1:
        return f"{ESCAPE}{filter_str}{ESCAPE}"
    return filter_str


def parse_filter_list(filters: list) -> str:
    """
    Parse a list of filters.
    """
    OR = " OR "
    return OR.join([parse_single_filter(f) for f in filters])


def process_keywords(config: dict) -> dict:
    """
    Process keywords in the configuration.
    """
    keywords = {}
    for k, v in config['keywords'].items():
        keywords[k] = parse_filter_list(v['filters'])
    return keywords


def load_config(config_file: str) -> dict:
    """
    Load configuration from a YAML file.
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not config:
            raise ValueError("Empty configuration file.")
        
        config['kv'] = process_keywords(config)

        logging.info(f"Configuration loaded successfully: {config}")
        return config
    
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        return {}


def sort_papers(papers):
    """
    Sort papers by date in descending order.
    """
    ans = {}
    keys = list(papers.keys())
    keys.sort(reverse=True)
    for k in keys:
        ans[k] = papers[k]
    return ans


class ArxivPaperFetcher:
    def __init__(self, arxiv_url: str = arxiv_url):
        self.arxiv_url = arxiv_url


    @staticmethod
    def get_authors(authors, first_author=False):
        """
        Get authors from the author list as strings.
        """
        if first_author and authors:
            return str(authors[0])
        return ", ".join(str(author) for author in authors)
    

    def get_paper_key(self, paper_id: str) -> str:
        """
        Remove the version number from the paper ID.
        """
        return paper_id.split("v")[0]
    

    def format_paper_info(self, paper_key: str, update_time: date, paper_title: str, 
                          paper_first_author: str, paper_authors: str, paper_url: str, 
                          comments: Optional[str], category: str,
                          paper_summary: str) -> Dict[str, Any]:
        """
        Format the paper information into a structured dictionary.
        
        Args:
            paper_key: The paper key (arXiv ID without version).
            update_time: The update time of the paper.
            paper_title: The title of the paper.
            paper_first_author: The first author of the paper.
            paper_authors: All authors of the paper.
            paper_url: The URL of the paper.
            comments: Additional comments.
            category: The primary category of the paper.
            paper_summary: The abstract of the paper.
            
        Returns:
            A dictionary containing the paper information.
        """
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
        """
        Get papers from arXiv that match the criteria.
        
        Args:
            topic: The topic of the papers.
            query: The query for the papers.
            max_results: The maximum number of results.
            date_from: The start date for filtering papers (inclusive).
            date_to: The end date for filtering papers (inclusive).
            categories: List of arXiv categories to filter by.
            
        Returns:    
            A list of paper information dictionaries.
        """
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
            
            # Convert author objects to strings to ensure JSON serialization works
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
        """
        Split papers into batches for processing by LLM.
        
        Args:
            papers: List of paper information dictionaries.
            batch_size: The size of each batch.
            
        Returns:
            A list of batches, where each batch is a list of paper dictionaries.
        """
        return [papers[i:i + batch_size] for i in range(0, len(papers), batch_size)]


def fetch_papers_by_config(config_file: str, max_results: int = 50, 
                          date_from: Optional[str] = None, date_to: Optional[str] = None,
                          categories: Optional[List[str]] = None, batch_size: int = 5) -> Dict[str, List[List[Dict[str, Any]]]]:
    """
    Fetch papers based on a configuration file.
    
    Args:
        config_file: Path to the configuration file.
        max_results: Maximum number of results per topic.
        date_from: Start date in 'YYYY-MM-DD' format.
        date_to: End date in 'YYYY-MM-DD' format.
        categories: List of arXiv categories to filter by.
        batch_size: Size of each batch for LLM processing.
        
    Returns:
        A dictionary mapping topics to batches of papers.
    """
    # Load configuration
    config = load_config(config_file)
    if not config:
        return {}
    
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
    for topic, query in config['kv'].items():
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
            
            # Split into batches
            batches = fetcher.batch_papers(papers, batch_size)
            result[topic] = batches
            
            logging.info(f"Found {len(papers)} papers for topic '{topic}', split into {len(batches)} batches")
        else:
            logging.info(f"No papers found for topic '{topic}'")
    
    return result



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch arXiv papers based on configuration")
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to configuration file')
    parser.add_argument('--max_results', type=int, default=50, help='Maximum number of results per topic')
    parser.add_argument('--date_from', type=str, help='Start date in YYYY-MM-DD format')
    parser.add_argument('--date_to', type=str, help='End date in YYYY-MM-DD format')
    parser.add_argument('--categories', type=str, nargs='+', help='arXiv categories to filter by')
    parser.add_argument('--batch_size', type=int, default=5, help='Size of each batch for LLM processing')
    parser.add_argument('--output', type=str, help='Output file path for JSON results')
    
    args = parser.parse_args()
    
    # Set default date_to to today if not specified
    if not args.date_to:
        args.date_to = datetime.date.today().strftime('%Y-%m-%d')
    
    # Set default date_from to 7 days ago if not specified
    if not args.date_from:
        from_date = datetime.date.today() - timedelta(days=7)
        args.date_from = from_date.strftime('%Y-%m-%d')
    
    logging.info(f"Fetching papers from {args.date_from} to {args.date_to}")
    
    # Fetch papers
    results = fetch_papers_by_config(
        config_file=args.config,
        max_results=args.max_results,
        date_from=args.date_from,
        date_to=args.date_to,
        categories=args.categories,
        batch_size=args.batch_size
    )
    
    # Save results to file if output path is specified
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logging.info(f"Results saved to {args.output}")
    
    # Print summary
    for topic, batches in results.items():
        total_papers = sum(len(batch) for batch in batches)
        logging.info(f"Topic: {topic} - {total_papers} papers in {len(batches)} batches")