# Smart CV Template System

The Smart CV Template System is an AI-powered CV customization tool that adapts your CV based on specific job requirements.

## Overview

This system consists of two main components:

1. **Smart LaTeX Template** (`templates/template_smart.tex`)
   - Modular structure with placeholders for dynamic content
   - Job-specific variables that can be customized
   - Section markers for targeted modifications

2. **Smart CV Generator** (`src/autocv/smart_cv_generator.py`)
   - Analyzes job descriptions and extracts key requirements
   - Generates optimized CV sections based on job analysis
   - Creates a tailored CV highlighting relevant skills and experiences

## Features

- **Job Analysis**: Automatically extracts job title, company, location, required skills, and keywords from job descriptions
- **Skill Matching**: Compares CV skills with job requirements and identifies gaps
- **Content Optimization**: Generates tailored content emphasizing relevant experience
- **Keyword Integration**: Incorporates job-specific keywords throughout the CV
- **Match Scoring**: Calculates how well your CV matches the job requirements

## Usage

### Basic Usage

```python
from src.smart_cv_generator import generate_smart_cv, SmartCVGenerator

# Option 1: Use the convenience function
pdf_path = generate_smart_cv(
    job_description="""
    Senior AI Developer - Tech Company
    
    Requirements:
    - Python, PyTorch, computer vision
    - Experience with deep learning
    - AWS and cloud deployment
    """,
    cv_skills=['Python', 'PyTorch', 'OpenCV', 'AWS', 'Docker'],
    output_dir='./output'
)

# Option 2: Use the SmartCVGenerator class
generator = SmartCVGenerator()

# Analyze job description
job_analysis = generator.analyze_job_description(job_text, cv_skills)

# Generate customized CV
cv_content = generator.generate_customized_cv(job_analysis)

# Save to file
generator.save_cv(cv_content, 'customized_cv.tex')
```

### Advanced Usage

```python
from src.smart_cv_generator import SmartCVGenerator, JobAnalysis

generator = SmartCVGenerator()

# Analyze job
job_analysis = generator.analyze_job_description(job_text, cv_skills)

# Access analysis results
print(f"Job Title: {job_analysis.job_title}")
print(f"Required Skills: {job_analysis.required_skills}")
print(f"Match Score: {job_analysis.match_score}%")
print(f"Missing Skills: {job_analysis.missing_skills}")

# Generate specific sections
summary = generator.generate_cv_section('summary', job_analysis)
skills = generator.generate_cv_section('skills', job_analysis)
experience = generator.generate_cv_section('experience', job_analysis)

# Generate complete customized CV
cv_content = generator.generate_customized_cv(job_analysis)

# Compile to PDF
tex_path = generator.save_cv(cv_content, 'my_cv.tex')
pdf_path = generator.compile_to_pdf(tex_path)
```

## Template Structure

The smart template uses the following customizable elements:

### Job Variables
```latex
\jobTitle{Position Title}
\jobCompany{Company Name}
\jobLocation{Location}
\targetSkill1{First key skill}
\targetSkill2{Second key skill}
\targetSkill3{Third key skill}
\targetKeyword1{First keyword}
\targetKeyword2{Second keyword}
\jobObjective{Custom objective}
```

### Section Placeholders
```latex
% PROFESSIONAL SUMMARY PLACEHOLDER
% KEY SKILLS PLACEHOLDER
% PROFESSIONAL EXPERIENCE PLACEHOLDER
% PROJECTS PLACEHOLDER
```

## File Structure

```
auto-cv-app/
├── templates/
│   ├── template_main.tex          # Original template
│   └── template_smart.tex         # Smart template (NEW)
├── src/
│   └── autocv/
│       ├── smart_cv_generator.py  # Smart CV generator
│       ├── matcher.py             # CV matcher
│       ├── latex_gen.py           # LaTeX generator
│       └── parser.py              # Job description parser
├── requirements.txt               # Python dependencies
└── docs/SMART_CV_README.md        # This file
```

## Dependencies

The smart CV generator requires the following dependencies (added to requirements.txt):

- pandas (for data processing)
- pillow (for image processing)

Optional for LLM integration:
- ollama
- openai

## Customization

### Modifying the Template

1. Edit `templates/template_smart.tex`
2. Update the section placeholders to match your content
3. Add your own LaTeX commands and formatting

### Customizing the Generator

1. Modify `src/autocv/smart_cv_generator.py`
2. Adjust the section generation logic
3. Add new section types as needed
4. Update the job analysis patterns

## Example Workflow

1. **Extract job requirements**:
   ```python
   analysis = generator.analyze_job_description(job_text, cv_skills)
   ```

2. **Review analysis results**:
   - Check required skills
   - Review match score
   - Identify missing skills

3. **Generate customized CV**:
   ```python
   cv_content = generator.generate_customized_cv(analysis)
   ```

4. **Compile to PDF**:
   ```python
   pdf_path = generator.compile_to_pdf(
       generator.save_cv(cv_content, 'cv.tex')
   )
   ```

## Best Practices

1. **Customize the summary**: Always tailor the professional summary to match the job
2. **Highlight relevant experience**: Emphasize experiences that align with job requirements
3. **Use keywords**: Incorporate keywords from the job description naturally
4. **Focus on achievements**: Use quantifiable achievements where possible
5. **Proofread**: Always review the generated CV before submitting

## Troubleshooting

### Template Compilation Issues

- Ensure you have a LaTeX distribution installed (TeX Live, MiKTeX, etc.)
- Check that all required packages are installed
- Verify that the template path is correct

### Analysis Issues

- Ensure the job description is complete and well-formatted
- Check that CV skills are properly formatted
- Review the extracted keywords and requirements

## Contributing

To extend the smart CV system:

1. Add new section types to `SmartCVGenerator.generate_cv_section()`
2. Update the template with new placeholders
3. Add job analysis patterns to `JobDescriptionParser`
4. Test with various job descriptions and CVs

## License

This module is part of the Auto-CV project and follows the same license.
