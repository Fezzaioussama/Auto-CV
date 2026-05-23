/**
 * Auto-CV Frontend JavaScript
 * Handles all client-side functionality
 */

// DOM Elements
const jobDescriptionInput = document.getElementById('jobDescription');
const jobAnalysisSection = document.getElementById('jobAnalysis');
const cvSection = document.getElementById('cvSection');
const resultsSection = document.getElementById('resultsSection');
const actionButtons = document.getElementById('actionButtons');
const loadingIndicator = document.getElementById('loadingIndicator');
const cvLatexInput = document.getElementById('cvLatex');
const latexPreview = document.getElementById('latexPreview');
const optimizedLatexEditor = document.getElementById('optimizedLatexEditor');
const pdfPreviewFrame = document.getElementById('pdfPreviewFrame');
const pdfPreviewStatus = document.getElementById('pdfPreviewStatus');
let currentPdfUrl = null;

// Drop zones
const jobDropZone = document.getElementById('jobDropZone');
const cvDropZone = document.getElementById('cvDropZone');

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    setupDropZones();
    console.log('Auto-CV initialized');
});

function setupDropZones() {
    // Job description drop zone
    jobDropZone.addEventListener('click', () => jobDescriptionInput.focus());
    
    jobDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        jobDropZone.classList.add('dragover');
    });

    jobDropZone.addEventListener('dragleave', () => {
        jobDropZone.classList.remove('dragover');
    });

    jobDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        jobDropZone.classList.remove('dragover');

        const file = e.dataTransfer.files[0];
        if (file && file.type.includes('text')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                jobDescriptionInput.value = e.target.result;
                parseJobDescription();
            };
            reader.readAsText(file);
        }
    });
    
    // CV drop zone
    cvDropZone.addEventListener('click', () => cvLatexInput.focus());
    
    cvDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        cvDropZone.classList.add('dragover');
    });

    cvDropZone.addEventListener('dragleave', () => {
        cvDropZone.classList.remove('dragover');
    });

    cvDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        cvDropZone.classList.remove('dragover');

        const file = e.dataTransfer.files[0];
        if (file && (file.type.includes('text') || file.name.endsWith('.tex'))) {
            const reader = new FileReader();
            reader.onload = (e) => {
                cvLatexInput.value = e.target.result;
            };
            reader.readAsText(file);
        }
    });
}

async function parseJobDescription() {
    const text = jobDescriptionInput.value.trim();
    
    if (!text) {
        alert('Please enter a job description');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/parse-job', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            window.currentJobAnalysis = data;

            // Carry the offer over to the Interview Prep page.
            try { sessionStorage.setItem('autocv_job_text', text); } catch (e) {}

            // Display job analysis results
            document.getElementById('jobSkillsCount').textContent = data.skills.length;
            document.getElementById('jobRequirementsCount').textContent = data.requirements.length;
            document.getElementById('jobQualificationsCount').textContent = data.qualifications.length || 0;
            
            // Display skills
            const skillsContainer = document.getElementById('jobSkillsContainer');
            skillsContainer.innerHTML = '';
            data.skills.forEach(skill => {
                const badge = document.createElement('span');
                badge.className = 'skills-badge';
                badge.textContent = skill;
                skillsContainer.appendChild(badge);
            });
            
            // Display requirements
            const requirementsList = document.getElementById('jobRequirementsList');
            requirementsList.innerHTML = '';
            data.requirements.forEach(req => {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                li.textContent = req;
                requirementsList.appendChild(li);
            });
            
            // Show job analysis section
            jobAnalysisSection.classList.remove('hidden');
            
            // Show CV upload section
            cvSection.classList.remove('hidden');
            
        } else {
            alert(`Error: ${data.error || 'Failed to parse job description'}`);
        }
    } catch (error) {
        console.error('Error parsing job description:', error);
        alert('An error occurred while parsing the job description. Please try again.');
    } finally {
        showLoading(false);
    }
}

async function uploadCV() {
    const cvLatex = cvLatexInput.value.trim();
    
    if (!cvLatex) {
        alert('Please enter or upload your LaTeX CV');
        return;
    }
    
    // Validate LaTeX structure
    if (!cvLatex.includes('\\begin{document}') || !cvLatex.includes('\\end{document}')) {
        alert('This doesn\'t appear to be a valid LaTeX document. Make sure it includes \\begin{document} and \\end{document}');
        return;
    }
    
    // Check if job description was parsed
    if (jobAnalysisSection.classList.contains('hidden')) {
        alert('Please parse a job description first');
        return;
    }
    
    // Carry the CV over to the Interview Prep page.
    try { sessionStorage.setItem('autocv_cv_latex', cvLatex); } catch (e) {}

    actionButtons.classList.remove('hidden');
    alert('CV uploaded successfully! Now click "Optimize CV" to analyze and improve it for this job.');
}

async function loadSampleJob() {
    try {
        const response = await fetch('/api/sample-job');
        const data = await response.json();
        
        if (response.ok) {
            jobDescriptionInput.value = data.job.text;
            parseJobDescription();
        }
    } catch (error) {
        console.error('Error loading sample job:', error);
        alert('Failed to load sample job. Please try again.');
    }
}

async function loadSampleCV() {
    try {
        const response = await fetch('/api/sample-cv');
        const data = await response.json();
        
        if (response.ok) {
            const cvData = data.cv;
            let latex = '\\documentclass[10pt,a4paper]{article}\n';
            latex += '\\usepackage[utf8]{inputenc}\n';
            latex += '\\usepackage[margin=1in]{geometry}\n\n';
            
            latex += '\\begin{document}\n\n';
            latex += `\\title{${cvData.metadata.author}}\n`;
            latex += `\\author{${cvData.metadata.email} | ${cvData.metadata.phone} | ${cvData.metadata.location}}\n`;
            latex += '\\maketitle\n\n';
            
            for (const [sectionName, content] of Object.entries(cvData.sections)) {
                latex += `\\section{${sectionName.toUpperCase()}}\n${content}\n\n`;
            }
            
            latex += '\\end{document}\n';
            
            cvLatexInput.value = latex;
            uploadCV();
        }
    } catch (error) {
        console.error('Error loading sample CV:', error);
        alert('Failed to load sample CV. Please try again.');
    }
}

async function optimizeCV() {
    const cvLatex = cvLatexInput.value.trim();
    const jobText = jobDescriptionInput.value.trim();
    
    if (!cvLatex || !jobText) {
        alert('Please provide both CV and job description');
        return;
    }

    // Carry context over to the Interview Prep page.
    try {
        sessionStorage.setItem('autocv_cv_latex', cvLatex);
        sessionStorage.setItem('autocv_job_text', jobText);
    } catch (e) {}

    // First, parse job description if not already done
    if (jobAnalysisSection.classList.contains('hidden')) {
        showLoading(true);
        try {
            const response = await fetch('/api/parse-job', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: jobText })
            });
            const jobData = await response.json();
            
            if (!response.ok) {
                throw new Error(jobData.error || 'Failed to parse job description');
            }
            
            // Store job analysis for later use
            window.currentJobAnalysis = jobData;
            
        } catch (error) {
            console.error('Error parsing job:', error);
            showLoading(false);
            return;
        } finally {
            showLoading(false);
        }
    }
    
    // Analyze and optimize CV
    showLoading(true);
    
    try {
        const response = await fetch('/api/optimize-cv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cv_latex: cvLatex,
                job_description: window.currentJobAnalysis || { skills: [], requirements: [] }
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Update statistics
            updateStatistics(data.analysis);

            // Show which offer skills are matched vs. missing
            updateSkillsCoverage(data.analysis);

            // Update recommendations
            updateRecommendations(data.analysis.recommendations);

            // Show which CV sections were rephrased for the offer
            updateAdaptedSections(data.rewritten_sections);

            // Update editable LaTeX and preview
            setOptimizedLatex(data.optimized_latex);

            // LLM-proposed new sections the candidate can insert
            updateProposedAdditions(data.proposed_additions);
            
            // Show results
            resultsSection.classList.remove('hidden');
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

            // Build the visual PDF preview from the optimized LaTeX.
            await renderPDFPreview();
            
        } else {
            alert(`Error: ${data.error || 'Failed to optimize CV'}`);
        }
    } catch (error) {
        console.error('Error optimizing CV:', error);
        alert('An error occurred while optimizing your CV. Please try again.');
    } finally {
        showLoading(false);
    }
}

function updateStatistics(analysis) {
    const skillsMatch = analysis.skills_match || {};
    const matchedCount = skillsMatch.matched ? skillsMatch.matched.length : 0;
    const missingCount = skillsMatch.missing ? skillsMatch.missing.length : 0;
    const totalJobSkills = skillsMatch.total_job_skills || 0;
    
    // Update match score
    const score = analysis.overall_score || 0;
    document.getElementById('matchScore').textContent = Math.round(score) + '%';
    document.getElementById('matchProgressBar').style.width = Math.round(score) + '%';
    
    // Update skills stats
    document.getElementById('skillsMatched').textContent = `${matchedCount}/${totalJobSkills}`;
    document.getElementById('missingSkills').textContent = missingCount;
    
    // Color code the score
    const matchScoreEl = document.getElementById('matchScore');
    if (score >= 80) {
        matchScoreEl.style.color = '#10b981';
    } else if (score >= 60) {
        matchScoreEl.style.color = '#f59e0b';
    } else {
        matchScoreEl.style.color = '#ef4444';
    }
}

function renderSkillBadges(container, skills, cssClass) {
    if (!container) {
        return;
    }
    container.innerHTML = '';
    if (!skills || skills.length === 0) {
        container.innerHTML = '<span class="text-muted">None.</span>';
        return;
    }
    skills.forEach(skill => {
        const badge = document.createElement('span');
        badge.className = 'skills-badge ' + cssClass;
        badge.textContent = skill;
        container.appendChild(badge);
    });
}

function updateSkillsCoverage(analysis) {
    const skillsMatch = (analysis && analysis.skills_match) || {};
    const matched = skillsMatch.matched || [];
    const missing = skillsMatch.missing || [];

    document.getElementById('matchedSkillsCount').textContent = matched.length;
    document.getElementById('missingSkillsCount').textContent = missing.length;

    renderSkillBadges(document.getElementById('matchedSkillsContainer'), matched, 'matched');
    renderSkillBadges(document.getElementById('missingSkillsContainer'), missing, 'missing');
}

function updateAdaptedSections(sections) {
    const el = document.getElementById('adaptedSectionsInfo');
    if (!el) {
        return;
    }

    if (sections && sections.length > 0) {
        const pills = sections
            .map(s => `<span class="adapted-pill"><i class="bi bi-pencil-square"></i> ${escapeHtml(s)}</span>`)
            .join('');
        el.innerHTML = `
            <div class="recommendation">
                <strong><i class="bi bi-magic"></i> Rephrased ${sections.length} section(s) to match the offer's wording (your facts were kept):</strong>
                <div class="mt-2">${pills}</div>
            </div>`;
    } else {
        el.innerHTML = `
            <div class="recommendation warning">
                <i class="bi bi-info-circle"></i> The live model rewrite was unavailable, so the CV was adapted with rule-based rephrasing. Review the LaTeX below before downloading.
            </div>`;
    }
}

function updateProposedAdditions(proposals) {
    const container = document.getElementById('proposedAdditionsContainer');
    if (!container) {
        return;
    }

    // Keep proposals around so the Insert buttons can reach the LaTeX snippet.
    window.currentProposals = Array.isArray(proposals) ? proposals : [];
    container.innerHTML = '';

    if (window.currentProposals.length === 0) {
        container.innerHTML = '<p class="text-muted">No extra sections suggested — your CV already covers what this offer asks for.</p>';
        return;
    }

    window.currentProposals.forEach((item, index) => {
        const typeLabel = item.type === 'skill_gap' ? 'Skill gap' : 'New section';
        const card = document.createElement('div');
        card.className = 'proposal-card';
        card.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <strong>${escapeHtml(item.title || 'Suggested addition')}</strong>
                    <span class="proposal-type">${escapeHtml(typeLabel)}</span>
                    ${item.reason ? `<div class="text-muted mt-1" style="font-size:0.9rem;">${escapeHtml(item.reason)}</div>` : ''}
                </div>
                <button class="btn btn-outline-primary btn-sm flex-shrink-0" data-proposal="${index}" onclick="insertProposal(${index})">
                    <i class="bi bi-plus-lg"></i> Insert into CV
                </button>
            </div>
            <pre>${escapeHtml(item.latex || '')}</pre>`;
        container.appendChild(card);
    });
}

function insertProposal(index) {
    const proposals = window.currentProposals || [];
    const item = proposals[index];
    if (!item || !optimizedLatexEditor) {
        return;
    }

    const snippet = '\n\n' + String(item.latex).trim() + '\n';
    let latex = optimizedLatexEditor.value;

    if (latex.includes('\\end{document}')) {
        latex = latex.replace('\\end{document}', snippet + '\n\\end{document}');
    } else {
        latex = latex.replace(/\s*$/, '') + snippet;
    }

    optimizedLatexEditor.value = latex;
    updateLatexPreview();
    if (pdfPreviewStatus) {
        pdfPreviewStatus.textContent = 'PDF needs rendering.';
    }

    const btn = document.querySelector(`button[data-proposal="${index}"]`);
    if (btn) {
        btn.disabled = true;
        btn.classList.remove('btn-outline-primary');
        btn.classList.add('btn-success');
        btn.innerHTML = '<i class="bi bi-check2"></i> Inserted';
    }
}

function updateRecommendations(recommendations) {
    const container = document.getElementById('recommendationsContainer');
    container.innerHTML = '';
    
    if (!recommendations || recommendations.length === 0) {
        container.innerHTML = '<p class="text-muted">No specific recommendations at this time.</p>';
        return;
    }
    
    recommendations.forEach((rec, index) => {
        const recEl = document.createElement('div');
        recEl.className = 'recommendation';
        recEl.innerHTML = `<i class="bi bi-lightbulb"></i> ${rec}`;
        container.appendChild(recEl);
    });
}

async function downloadPDF() {
    const pdfBlob = await renderLatexToPdfBlob();
    
    if (!pdfBlob) {
        return;
    }

    const url = URL.createObjectURL(pdfBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cv_optimized_${new Date().toISOString().split('T')[0]}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

async function renderLatexToPdfBlob() {
    const latex = getOptimizedLatex();
    
    if (!latex) {
        alert('No LaTeX content to render. Please optimize your CV first.');
        return null;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/render-latex', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latex })
        });
        
        if (response.ok) {
            // The server may have silently auto-repaired broken LaTeX. If so,
            // update the editor to the version that actually compiles so the
            // user never deals with the error and copies/downloads stay valid.
            if (response.headers.get('X-Latex-Repaired') === 'true') {
                const encoded = response.headers.get('X-Corrected-Latex');
                if (encoded && optimizedLatexEditor) {
                    try {
                        const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
                        const corrected = new TextDecoder('utf-8').decode(bytes);
                        if (corrected) {
                            optimizedLatexEditor.value = corrected;
                            updateLatexPreview();
                        }
                    } catch (e) {
                        console.warn('Could not apply auto-corrected LaTeX:', e);
                    }
                }
            }
            return await response.blob();
        } else {
            const errorData = await response.json();
            alert(`Error: ${errorData.error || 'Failed to generate PDF'}\n\n${errorData.details || ''}`);
            return null;
        }
    } catch (error) {
        console.error('Error downloading PDF:', error);
        alert('An error occurred while generating the PDF. Please try again.');
        return null;
    } finally {
        showLoading(false);
    }
}

async function renderPDFPreview() {
    updateLatexPreview();

    if (!pdfPreviewFrame || !pdfPreviewStatus) {
        return;
    }

    pdfPreviewStatus.textContent = 'Rendering PDF...';
    const pdfBlob = await renderLatexToPdfBlob();

    if (!pdfBlob) {
        pdfPreviewStatus.textContent = 'PDF render failed.';
        return;
    }

    if (currentPdfUrl) {
        URL.revokeObjectURL(currentPdfUrl);
    }

    currentPdfUrl = URL.createObjectURL(pdfBlob);
    pdfPreviewFrame.src = currentPdfUrl;
    pdfPreviewFrame.classList.remove('hidden');
    pdfPreviewStatus.textContent = 'PDF preview rendered.';
}

function copyToClipboard() {
    const latex = getOptimizedLatex();
    
    if (!latex) {
        alert('No LaTeX content to copy. Please optimize your CV first.');
        return;
    }
    
    navigator.clipboard.writeText(latex).then(() => {
        const btn = document.querySelector('button[onclick="copyToClipboard()"]');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check2"></i> Copied!';
        setTimeout(() => {
            btn.innerHTML = originalText;
        }, 2000);
    }).catch(err => {
        alert('Failed to copy LaTeX to clipboard');
    });
}

function showLoading(show) {
    if (show) {
        loadingIndicator.classList.add('show');
    } else {
        loadingIndicator.classList.remove('show');
    }
}

function getOptimizedLatex() {
    return optimizedLatexEditor ? optimizedLatexEditor.value.trim() : '';
}

function setOptimizedLatex(latex) {
    if (optimizedLatexEditor) {
        optimizedLatexEditor.value = latex || '';
    }
    updateLatexPreview();
    if (pdfPreviewFrame) {
        pdfPreviewFrame.classList.add('hidden');
        pdfPreviewFrame.removeAttribute('src');
    }
    if (pdfPreviewStatus) {
        pdfPreviewStatus.textContent = 'PDF needs rendering.';
    }
}

function escapeHtml(value) {
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Add syntax highlighting to LaTeX code preview
function highlightLaTeX() {
    let latex = escapeHtml(getOptimizedLatex());
    
    // Add syntax highlighting classes
    latex = latex
        .replace(/\\[a-zA-Z]+/g, '<span class="command">$&</span>')
        .replace(/%.*$/gm, '<span class="comment">$&</span>')
        .replace(/"([^"]*)"/g, '<span class="string">$&</span>');
    
    latexPreview.innerHTML = latex;
}

function updateLatexPreview() {
    if (!latexPreview) {
        return;
    }
    highlightLaTeX();
}

if (optimizedLatexEditor) {
    optimizedLatexEditor.addEventListener('input', () => {
        updateLatexPreview();
        if (pdfPreviewStatus) {
            pdfPreviewStatus.textContent = 'PDF needs rendering.';
        }
    });
}
