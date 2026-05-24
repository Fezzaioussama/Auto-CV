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
const loadingTitle = document.getElementById('loadingTitle');
const loadingMessage = document.getElementById('loadingMessage');
const toastRegion = document.getElementById('toastRegion');
let currentPdfUrl = null;

// Drop zones
const jobDropZone = document.getElementById('jobDropZone');
const cvDropZone = document.getElementById('cvDropZone');
const jobFileInput = document.getElementById('jobFileInput');
const cvFileInput = document.getElementById('cvFileInput');

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    setupDropZones();
    console.log('Auto-CV initialized');
});

function setupDropZones() {
    setupTextFileZone({
        zone: jobDropZone,
        input: jobFileInput,
        allowedExtensions: ['txt', 'md', 'tex'],
        invalidMessage: 'Upload a plain text, Markdown, or TeX file for the job description.',
        onText: (text, file) => {
            jobDescriptionInput.value = text;
            notify('success', 'Job file loaded', file.name);
            parseJobDescription();
        }
    });

    setupCvUploadZone();
}

// The CV zone accepts LaTeX/text (read locally) *and* PDF/DOCX (sent to the
// server for text extraction + conversion to a compilable LaTeX document).
function setupCvUploadZone() {
    const zone = cvDropZone;
    const input = cvFileInput;
    if (!zone || !input) {
        return;
    }

    const handle = (file) => {
        if (!file) {
            return;
        }
        const ext = (file.name.split('.').pop() || '').toLowerCase();
        const SERVER_EXT = ['pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp', 'gif'];
        if (ext === 'tex' || ext === 'txt' || (file.type.includes('text') && !file.type.startsWith('image/'))) {
            const reader = new FileReader();
            reader.onload = (event) => {
                cvLatexInput.value = event.target.result || '';
                notify('success', 'CV file loaded', file.name);
            };
            reader.onerror = () => notify('danger', 'Could not read file', 'Try pasting the LaTeX directly.');
            reader.readAsText(file);
        } else if (SERVER_EXT.includes(ext) || file.type.startsWith('image/')) {
            extractCvFile(file);
        } else {
            notify('warning', 'Unsupported file', 'Upload a .tex, .pdf, .docx, or an image (PNG/JPG) CV.');
        }
        input.value = '';
    };

    zone.addEventListener('click', () => input.click());
    zone.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            input.click();
        }
    });
    zone.addEventListener('dragover', (event) => {
        event.preventDefault();
        zone.classList.add('dragover');
    });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', (event) => {
        event.preventDefault();
        zone.classList.remove('dragover');
        handle(event.dataTransfer.files[0]);
    });
    input.addEventListener('change', () => handle(input.files[0]));
}

// Upload a PDF/DOCX/image CV; the server extracts text (OCR for images and
// scanned PDFs) and returns a LaTeX document.
async function extractCvFile(file) {
    const statusEl = document.getElementById('cvExtractStatus');
    const templateEl = document.getElementById('cvTemplate');
    const languageEl = document.getElementById('cvLanguage');

    const form = new FormData();
    form.append('file', file);
    if (templateEl && templateEl.value) form.append('template', templateEl.value);
    if (languageEl && languageEl.value) form.append('language', languageEl.value);

    showLoading(true, 'Reading your CV', 'Extracting text (OCR for images/scans) and building LaTeX');
    if (statusEl) statusEl.innerHTML = '';
    try {
        // Note: no Content-Type header — the browser sets the multipart boundary.
        const response = await fetch('/api/extract-cv', { method: 'POST', body: form });
        const data = await response.json();
        if (response.ok) {
            cvLatexInput.value = data.latex || '';
            if (statusEl) {
                statusEl.innerHTML =
                    `<div class="recommendation"><i class="bi bi-check2-circle"></i> ` +
                    `Imported <strong>${escapeHtml(file.name)}</strong> as LaTeX. ` +
                    `Review it below — then upload it for this offer.</div>`;
            }
            notify('success', 'CV imported', 'Your file was converted to LaTeX.');
        } else {
            notify('danger', 'Import failed', data.error || 'Could not read that file.');
        }
    } catch (error) {
        console.error('Error extracting CV file:', error);
        notify('danger', 'Import failed', 'An error occurred while reading the file.');
    } finally {
        showLoading(false);
    }
}

function setupTextFileZone({ zone, input, allowedExtensions, invalidMessage, onText }) {
    if (!zone || !input) {
        return;
    }

    const openPicker = () => input.click();
    const canRead = (file) => {
        if (!file) {
            return false;
        }
        const ext = (file.name.split('.').pop() || '').toLowerCase();
        return file.type.includes('text') || allowedExtensions.includes(ext);
    };

    const readFile = (file) => {
        if (!canRead(file)) {
            notify('warning', 'Unsupported file', invalidMessage);
            input.value = '';
            return;
        }

        const reader = new FileReader();
        reader.onload = (event) => onText(event.target.result || '', file);
        reader.onerror = () => notify('danger', 'Could not read file', 'Try pasting the content directly into the text area.');
        reader.readAsText(file);
    };

    zone.addEventListener('click', openPicker);
    zone.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openPicker();
        }
    });

    zone.addEventListener('dragover', (event) => {
        event.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));

    zone.addEventListener('drop', (event) => {
        event.preventDefault();
        zone.classList.remove('dragover');
        readFile(event.dataTransfer.files[0]);
    });

    input.addEventListener('change', () => readFile(input.files[0]));
}

// Pull a job posting's text from a URL (server fetches it, SSRF-protected),
// drop it into the textarea, then parse it like any pasted offer.
async function fetchJobFromUrl() {
    const urlInput = document.getElementById('jobUrl');
    const url = (urlInput && urlInput.value || '').trim();
    if (!url) {
        notify('warning', 'No URL', 'Paste a job posting URL first.');
        return;
    }

    showLoading(true, 'Fetching the offer', 'Reading the job posting from the URL');
    try {
        const response = await fetch('/api/fetch-job-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await response.json();
        if (!response.ok) {
            notify('danger', 'Could not fetch', data.error || 'The page could not be read.');
            return;
        }
        jobDescriptionInput.value = data.text || '';
        notify('success', 'Offer fetched', 'Review the text below, then parse it.');
    } catch (e) {
        notify('danger', 'Could not fetch', 'A network error occurred. Paste the text instead.');
    } finally {
        showLoading(false);
    }
}

async function parseJobDescription() {
    const text = jobDescriptionInput.value.trim();

    if (!text) {
        notify('warning', 'Job description missing', 'Paste an offer or upload a text file first.');
        return;
    }
    
    showLoading(true, 'Reading the offer', 'Extracting skills, requirements, and qualifications');
    
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
            notify('success', 'Job analyzed', `${data.skills.length} skills and ${data.requirements.length} requirements found.`);
            signalWorkflowChange();
            
        } else {
            notify('danger', 'Job analysis failed', data.error || 'Failed to parse job description.');
        }
    } catch (error) {
        console.error('Error parsing job description:', error);
        notify('danger', 'Job analysis failed', 'An error occurred while parsing the job description. Please try again.');
    } finally {
        showLoading(false);
    }
}

async function uploadCV() {
    const cvLatex = cvLatexInput.value.trim();
    
    if (!cvLatex) {
        notify('warning', 'CV missing', 'Paste your LaTeX CV or upload a .tex file first.');
        return;
    }
    
    // Validate LaTeX structure
    if (!cvLatex.includes('\\begin{document}') || !cvLatex.includes('\\end{document}')) {
        notify('warning', 'Invalid LaTeX document', 'Make sure the CV includes \\begin{document} and \\end{document}.');
        return;
    }
    
    // Check if job description was parsed
    if (jobAnalysisSection.classList.contains('hidden')) {
        notify('warning', 'Analyze the offer first', 'Parse the job description before uploading the CV.');
        return;
    }
    
    // Carry the CV over to the Interview Prep page.
    try { sessionStorage.setItem('autocv_cv_latex', cvLatex); } catch (e) {}

    actionButtons.classList.remove('hidden');
    notify('success', 'CV ready', 'You can optimize it for this offer now.');
    signalWorkflowChange();
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
        notify('danger', 'Sample job unavailable', 'Failed to load the sample job. Please try again.');
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
        notify('danger', 'Sample CV unavailable', 'Failed to load the sample CV. Please try again.');
    }
}

async function optimizeCV() {
    const cvLatex = cvLatexInput.value.trim();
    const jobText = jobDescriptionInput.value.trim();
    
    if (!cvLatex || !jobText) {
        notify('warning', 'Context missing', 'Provide both a CV and a job description before optimizing.');
        return;
    }

    // Carry context over to the Interview Prep page.
    try {
        sessionStorage.setItem('autocv_cv_latex', cvLatex);
        sessionStorage.setItem('autocv_job_text', jobText);
    } catch (e) {}

    // First, parse job description if not already done
    if (jobAnalysisSection.classList.contains('hidden')) {
        showLoading(true, 'Reading the offer', 'Preparing the job context before optimization');
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
            notify('danger', 'Job analysis failed', error.message || 'Could not parse the job description.');
            showLoading(false);
            return;
        } finally {
            showLoading(false);
        }
    }
    
    // Analyze and optimize CV
    showLoading(true, 'Optimizing your CV', 'Matching skills, rewriting sections, and preparing the PDF');

    const languageEl = document.getElementById('cvLanguage');
    const language = (languageEl && languageEl.value) || 'en';

    try {
        const response = await fetch('/api/optimize-cv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cv_latex: cvLatex,
                job_description: window.currentJobAnalysis || { skills: [], requirements: [] },
                language: language
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

            // Keep the full optimization + context around for the ATS panel,
            // before/after review, cover letter, and "save to workspace".
            window.currentOptimization = data;
            window.currentCvLatex = cvLatex;
            window.currentLanguage = language;

            // Let the feature modules (ATS / review / cover letter) render.
            if (window.AutoCVFeatures && typeof window.AutoCVFeatures.onOptimized === 'function') {
                window.AutoCVFeatures.onOptimized(data);
            }
            if (window.AutoCVReview && typeof window.AutoCVReview.render === 'function') {
                window.AutoCVReview.render(data.section_diffs, data.optimized_latex);
            }

            // Show results
            resultsSection.classList.remove('hidden');
            signalWorkflowChange();
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

            // Build the visual PDF preview from the optimized LaTeX.
            await renderPDFPreview();
            
        } else {
            notify('danger', 'Optimization failed', data.error || 'Failed to optimize CV.');
        }
    } catch (error) {
        console.error('Error optimizing CV:', error);
        notify('danger', 'Optimization failed', 'An error occurred while optimizing your CV. Please try again.');
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
    notify('success', 'Section inserted', 'Render the PDF again to preview the updated CV.');
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
        recEl.innerHTML = `<i class="bi bi-lightbulb"></i> ${escapeHtml(rec)}`;
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
    notify('success', 'PDF downloaded', 'Your optimized CV PDF was generated.');
}

// Export the optimized CV to a recruiter-friendly Word (.docx) or plain-text
// file via the server-side converter (no LaTeX toolchain needed for these).
async function exportCV(format) {
    const latex = getOptimizedLatex();
    if (!latex) {
        notify('warning', 'Nothing to export', 'Optimize your CV first, then export to Word or text.');
        return;
    }

    const ext = format === 'docx' ? 'docx' : 'txt';
    showLoading(true, 'Exporting', `Preparing your ${ext.toUpperCase()} file`);
    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latex, format })
        });
        if (!response.ok) {
            let msg = 'Export failed.';
            try { const e = await response.json(); msg = e.error || msg; } catch (_) {}
            notify('danger', 'Export failed', msg);
            return;
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cv_optimized_${new Date().toISOString().split('T')[0]}.${ext}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        notify('success', 'Export ready', `Your ${ext.toUpperCase()} file was downloaded.`);
    } catch (e) {
        console.error('Export error:', e);
        notify('danger', 'Export failed', 'An error occurred while exporting. Please try again.');
    } finally {
        showLoading(false);
    }
}

async function renderLatexToPdfBlob() {
    const latex = getOptimizedLatex();
    
    if (!latex) {
        notify('warning', 'Nothing to render', 'Optimize your CV first, then render or download the PDF.');
        return null;
    }
    
    showLoading(true, 'Rendering PDF', 'Compiling LaTeX and repairing small issues if needed');
    
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
            notify('danger', 'PDF render failed', errorData.details || errorData.error || 'Failed to generate PDF.');
            return null;
        }
    } catch (error) {
        console.error('Error downloading PDF:', error);
        notify('danger', 'PDF render failed', 'An error occurred while generating the PDF. Please try again.');
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
        notify('warning', 'Nothing to copy', 'Optimize your CV first, then copy the LaTeX.');
        return;
    }
    
    navigator.clipboard.writeText(latex).then(() => {
        const btn = document.querySelector('button[onclick="copyToClipboard()"]');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check2"></i> Copied!';
        setTimeout(() => {
            btn.innerHTML = originalText;
        }, 2000);
        notify('success', 'Copied', 'Optimized LaTeX copied to the clipboard.');
    }).catch(err => {
        notify('danger', 'Copy failed', 'Your browser blocked clipboard access.');
    });
}

function showLoading(show, title, message) {
    if (show) {
        if (loadingTitle && title) {
            loadingTitle.textContent = title;
        }
        if (loadingMessage && message) {
            loadingMessage.textContent = message;
        }
        loadingIndicator.classList.add('show');
    } else {
        loadingIndicator.classList.remove('show');
    }
}

function signalWorkflowChange() {
    document.dispatchEvent(new CustomEvent('autocv:state-change'));
}

function notify(type, title, message) {
    if (!toastRegion) {
        console[type === 'danger' ? 'error' : 'log'](`${title}: ${message || ''}`);
        return;
    }

    const toast = document.createElement('div');
    const icon = {
        success: 'bi-check2-circle',
        warning: 'bi-exclamation-triangle',
        danger: 'bi-x-circle'
    }[type] || 'bi-info-circle';

    toast.className = `toast-card ${type || 'info'}`;
    toast.innerHTML = `
        <span class="toast-icon"><i class="bi ${icon}"></i></span>
        <span class="toast-copy">
            <strong>${escapeHtml(title || 'Notice')}</strong>
            ${message ? `<span>${escapeHtml(message)}</span>` : ''}
        </span>
        <button type="button" class="toast-close" aria-label="Dismiss notification">
            <i class="bi bi-x-lg"></i>
        </button>`;

    const removeToast = () => {
        toast.classList.add('closing');
        setTimeout(() => toast.remove(), 220);
    };

    toast.querySelector('.toast-close').addEventListener('click', removeToast);
    toastRegion.appendChild(toast);
    setTimeout(removeToast, type === 'danger' ? 7000 : 4200);
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
    return String(value || '')
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
