"""
Job Description Parser Module
Extracts skills, qualifications, and requirements from job descriptions.
"""

import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.probability import FreqDist
import string

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt_tab')
except (LookupError, OSError):
    try:
        nltk.download('punkt_tab', quiet=True)
    except:
        pass  # Silent fail for sandbox environments

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


class JobDescriptionParser:
    """Parser for extracting information from job descriptions."""
    
    def __init__(self):
        self.stop_words = set(stopwords.words('english'))
        self.common_skills = self._load_common_skills()
    
    def _load_common_skills(self):
        """Load a list of common technical and professional skills."""
        return {
            # Programming languages
            'python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'php', 'swift', 
            'kotlin', 'rust', 'go', 'typescript', 'scala', 'perl', 'r', 'matlab',
            # Frameworks and libraries
            'django', 'flask', 'react', 'angular', 'vue.js', 'node.js', 'express',
            'spring', 'hibernate', 'tensorflow', 'pytorch', 'pandas', 'numpy',
            'scikit-learn', 'matplotlib', 'seaborn', 'git', 'docker', 'kubernetes',
            # Databases
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'oracle', 'sqlite',
            'cassandra', 'elastic search', 'mariadb',
            # Cloud and DevOps
            'aws', 'azure', 'google cloud', 'terraform', 'ansible', 'jenkins',
            'ci/cd', 'github actions', 'gitlab ci', 'kafka', 'rabbitmq',
            # Methodologies and other
            'agile', 'scrum', 'devops', 'tdd', 'bdd', 'microservices',
            'rest', 'graphql', 'oauth', 'jwt', 'linux', 'shell scripting',
            'data analysis', 'machine learning', 'deep learning', 'ai',
            'blockchain', 'cybersecurity', 'networking', 'serverless',
            'frontend', 'backend', 'full-stack', 'ui/ux', 'mobile development',
            'testing', 'qa', 'debugging', 'optimization', 'scalability'
        }
    
    def parse(self, text):
        """
        Parse a job description and extract key information.
        
        Args:
            text: The job description text
            
        Returns:
            dict: Extracted information including skills, requirements, etc.
        """
        if not text:
            return {}
        
        # Clean the text
        text = self._clean_text(text)
        
        # Extract sections
        sections = self._extract_sections(text)
        
        # Extract skills
        skills = self._extract_skills(text)
        
        # Extract requirements
        requirements = self._extract_requirements(text)
        
        # Extract qualifications
        qualifications = self._extract_qualifications(text)
        
        # Extract company info if present
        company_info = self._extract_company_info(text)
        
        return {
            'text': text,
            'sections': sections,
            'skills': skills,
            'requirements': requirements,
            'qualifications': qualifications,
            'company_info': company_info,
            'raw_text': text
        }
    
    def _clean_text(self, text):
        """Clean and normalize text."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,;:!?-]', ' ', text)
        return text.strip()
    
    def _extract_sections(self, text):
        """Extract section headers from job description."""
        sections = {}
        
        # Common section patterns
        section_patterns = {
            'about': r'(about\s+the\s+company|about\s+us|company\s+profile|overview)',
            'responsibilities': r'(job\s+responsibilities|your\s+responsibilities|what\s+you\'?ll\s+do|key\s+responsibilities)',
            'requirements': r'(requirements|qualifications|what\s+we\'?re\s+looking\s+for|we\s+require)',
            'skills': r'(skills\s+required|required\s+skills|must\s+have\s+skills)',
            'benefits': r'(benefits|what\s+we\s+offer|perks)',
            'education': r'(education|qualifications|degrees|academic)',
        }
        
        for section_name, pattern in section_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                sections[section_name] = True
        
        return sections
    
    def _extract_skills(self, text):
        """Extract skills from a job description.

        Matching uses alphanumeric/symbol boundaries instead of a plain
        substring test, so short skills like ``r``, ``go`` and ``ai`` are only
        picked up as standalone words — not inside ``are``, ``category`` or
        ``available`` — while symbol-bearing tokens (``c++``, ``c#``,
        ``node.js``) still match cleanly.
        """
        skills_found = set()
        text_lower = text.lower()

        for skill in self.common_skills:
            pattern = r'(?<![a-z0-9+#.])' + re.escape(skill) + r'(?![a-z0-9+#])'
            if re.search(pattern, text_lower):
                skills_found.add(skill)

        return list(skills_found)
    
    def _extract_requirements(self, text):
        """Extract job requirements."""
        requirements = []
        
        # Split into sentences
        sentences = re.split(r'[.!?]', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            # Look for requirement patterns
            if any(word in sentence.lower() for word in ['required', 'must', 'need', 'experience', 'years', 'proficient', 'knowledge']):
                if len(sentence) > 10 and len(sentence) < 200:
                    requirements.append(sentence.strip())
        
        return requirements[:10]  # Return top 10 requirements
    
    def _extract_qualifications(self, text):
        """Extract qualifications and education requirements."""
        qualifications = []
        
        # Look for degree patterns
        degree_pattern = r'(b\.?s\.?|b\.?a\.?|m\.?s\.?|m\.?a\.?|ph\.?d\.?|bacherlor|master|doctorate)\s+(in\s+[A-Za-z]+)?'
        degrees = re.findall(degree_pattern, text, re.IGNORECASE)
        
        for degree in degrees:
            qual = ' '.join(degree).strip()
            if len(qual) > 5:
                qualifications.append(qual)
        
        # Look for certification patterns
        cert_pattern = r'(certified|certification|certificate)\s+(in\s+[A-Za-z]+)+'
        certs = re.findall(cert_pattern, text, re.IGNORECASE)
        qualifications.extend([cert[0] for cert in certs])
        
        return qualifications
    
    def _extract_company_info(self, text):
        """Extract company information if present."""
        info = {}
        
        # Try to find company name (look for "at [Company]" or "[Company] is")
        company_patterns = [
            r'(?:at|for)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+is\s+a',
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, text)
            if match:
                info['company_name'] = match.group(1)
                break
        
        # Extract location
        location_pattern = r'(location|headquarters|office)?\s*[:\-]?\s*([A-Z][a-zA-Z\s,]+?(?:USA|US|UK|Europe|Asia|Africa|Australia|Canada))?'
        match = re.search(location_pattern, text, re.IGNORECASE)
        if match:
            info['location'] = match.group(2) if match.group(2) else match.group(1)
        
        return info
    
    def get_top_skills(self, text, n=10):
        """Get the top N most frequent skills from text."""
        words = word_tokenize(text.lower())
        words = [w for w in words if w not in self.stop_words and w.isalpha()]
        freq_dist = FreqDist(words)
        
        # Filter for skills
        skills = [word for word, count in freq_dist.most_common(n) 
                  if word in self.common_skills or count >= 2]
        
        return skills[:n]


def parse_job_description(text):
    """
    Convenience function to parse a job description.
    
    Args:
        text: Job description text
        
    Returns:
        dict: Parsed job description
    """
    parser = JobDescriptionParser()
    return parser.parse(text)
