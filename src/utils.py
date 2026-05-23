"""
Utility functions for Auto-CV application.
"""

import os
import re
import uuid
from datetime import datetime


def generate_cv_filename(job_title=None, company_name=None):
    """Generate a filename for the generated CV."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cv_id = str(uuid.uuid4())[:8]
    
    if job_title:
        # Clean job title for filename
        clean_title = re.sub(r'[^a-zA-Z0-9]', '_', job_title.lower())[:30]
        return f"CV_{clean_title}_{cv_id}_{timestamp}.pdf"
    elif company_name:
        clean_company = re.sub(r'[^a-zA-Z0-9]', '_', company_name.lower())[:20]
        return f"CV_{clean_company}_{cv_id}_{timestamp}.pdf"
    else:
        return f"CV_{cv_id}_{timestamp}.pdf"


def extract_keywords_from_text(text, n_keywords=15):
    """Extract keywords from text using simple frequency analysis."""
    if not text:
        return []
    
    # Clean text
    text = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
    words = text.split()
    
    # Remove common words
    common_words = {
        'the', 'and', 'for', 'with', 'are', 'has', 'have', 'was', 'were',
        'will', 'can', 'that', 'this', 'from', 'which', 'you', 'your',
        'their', 'its', 'about', 'into', 'than', 'over', 'after', 'under',
        'between', 'more', 'all', 'each', 'them', 'these', 'those'
    }
    words = [w for w in words if w not in common_words and len(w) > 2]
    
    # Get frequency distribution
    freq_dist = {}
    for word in words:
        freq_dist[word] = freq_dist.get(word, 0) + 1
    
    # Sort by frequency and return top keywords
    sorted_words = sorted(freq_dist.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:n_keywords]]


def save_text_to_file(text, directory, filename):
    """Save text content to a file."""
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    return filepath


def format_skills_list(skills):
    """Format a list of skills for display."""
    if not skills:
        return ""
    return ", ".join(sorted(set(skills)))


def match_keywords(cv_skills, job_requirements):
    """Match CV skills with job requirements."""
    if not cv_skills or not job_requirements:
        return [], []
    
    cv_skills_lower = [s.lower() for s in cv_skills]
    matched = []
    missing = []
    
    for req in job_requirements:
        req_lower = req.lower()
        for skill in cv_skills_lower:
            if skill in req_lower or req_lower in skill:
                matched.append(req)
                break
        else:
            if len(req.strip()) > 5:  # Only add if meaningful
                missing.append(req)
    
    return matched, missing


def count_words(text):
    """Count words in text."""
    if not text:
        return 0
    return len(text.split())


def truncate_text(text, max_length=150, add_ellipsis=True):
    """Truncate text to a maximum length."""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    if add_ellipsis:
        return text[:max_length-3] + "..."
    return text[:max_length]
