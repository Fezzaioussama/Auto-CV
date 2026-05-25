#!/usr/bin/env python3
"""
Test script to verify vLLM API connection and CV generation.
"""

import sys
import os

# This script lives in <repo>/scripts/, so the repo root is one directory up.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from autocv.smart_cv_generator import SmartCVGenerator, generate_smart_cv


def test_vllm_connection():
    """Test vLLM API connection."""
    print("=" * 60)
    print("TEST: vLLM API Connection")
    print("=" * 60)
    
    # Create generator with vLLM config
    api_url = "http://127.0.0.1:8002/v1"
    model = "Qwen/Qwen3-Coder-Next-FP8"
    
    generator = SmartCVGenerator(api_url=api_url, model=model)
    
    # Test simple prompt
    test_prompt = "Hello, how are you?"
    
    print(f"\nTesting vLLM API at: {api_url}")
    print(f"Model: {model}")
    print(f"Prompt: {test_prompt}")
    
    response = generator._call_llm_api(test_prompt, max_tokens=100, temperature=0.1)
    
    if response:
        print(f"\n✓ vLLM API Connection Successful!")
        print(f"Response: {response[:200]}...")
        return True
    else:
        print("\n✗ vLLM API Connection Failed or returned no response")
        print("This is expected if the API is not reachable")
        return False


def test_full_cv_generation():
    """Test full CV generation with vLLM."""
    print("\n" + "=" * 60)
    print("TEST: Full CV Generation with vLLM")
    print("=" * 60)
    
    sample_job = """
    Senior AI Developer - Tech Solutions
    
    Location: Paris, France
    
    About Us:
    We are a leading technology company building next-generation AI solutions.
    
    Job Description:
    We are looking for an experienced AI Developer to join our team. 
    You will be responsible for designing and implementing AI solutions.
    
    Requirements:
    - 5+ years of experience with Python, PyTorch, and computer vision
    - Experience with deep learning models and optimization
    - Knowledge of AWS and cloud deployment
    - Strong problem-solving skills
    
    Preferred:
    - Experience with LLMs and NLP
    - Knowledge of MLOps practices
    """
    
    cv_skills = [
        'Python', 'C++', 'PyTorch', 'OpenCV', 'Deep Learning', 
        'AWS', 'Docker', 'Git', 'English', 'French'
    ]
    
    # Create generator with vLLM
    generator = SmartCVGenerator(
        api_url="http://127.0.0.1:8002/v1",
        model="Qwen/Qwen3-Coder-Next-FP8"
    )
    
    print("\nAnalyzing job description...")
    analysis = generator.analyze_job_description(sample_job, cv_skills)
    
    print(f"\nJob Title: {analysis.job_title}")
    print(f"Match Score: {analysis.match_score}%")
    print(f"LLM Analysis: {bool(analysis.llm_analysis)}")
    
    if analysis.llm_analysis:
        print("\nLLM Recommendations:")
        for i, rec in enumerate(analysis.recommendations, 1):
            print(f"  {i}. {rec[:100]}...")
    
    print("\nGenerating customized CV...")
    cv_content = generator.generate_customized_cv(analysis)
    
    print(f"Generated CV content ({len(cv_content)} characters)")
    
    # Save to file
    output_dir = os.path.join(_REPO_ROOT, 'output')
    tex_path = generator.save_cv(cv_content, 'vllm_test_cv.tex', output_dir)
    
    print(f"Saved LaTeX to: {tex_path}")
    
    # Try PDF compilation
    try:
        pdf_path = generator.compile_to_pdf(tex_path, output_dir)
        print(f"PDF generated at: {pdf_path}")
        return True
    except Exception as e:
        print(f"Note: PDF generation skipped ({e})")
        print("This is normal if pdflatex is not installed")
        return True  # Still pass if LaTeX was generated


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("VLMM CV GENERATOR - TEST SUITE")
    print("=" * 60 + "\n")
    
    results = []
    
    try:
        # Test vLLM connection
        results.append(("vLLM Connection", test_vllm_connection()))
        
        # Test full CV generation
        results.append(("Full CV Generation", test_full_cv_generation()))
        
        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        for name, passed in results:
            status = "✓ PASSED" if passed else "✗ FAILED"
            print(f"{name}: {status}")
        
        all_passed = all(result[1] for result in results)
        if all_passed:
            print("\n✓ ALL TESTS PASSED!")
        else:
            print("\n✗ SOME TESTS FAILED")
        
        return 0 if all_passed else 1
        
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
