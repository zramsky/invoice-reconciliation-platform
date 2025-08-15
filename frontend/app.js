// For local development use: 'http://localhost:5000/api'
// For Firebase deployment use: '/api'
const API_BASE = window.location.hostname === 'localhost' 
    ? 'http://localhost:5000/api' 
    : '/api';

let currentSessionId = null;

document.getElementById('contractFile').addEventListener('change', handleFileSelect);
document.getElementById('invoiceFile').addEventListener('change', handleFileSelect);
document.getElementById('processBtn').addEventListener('click', startReconciliation);
document.getElementById('newReconciliationBtn').addEventListener('click', resetForm);

function handleFileSelect(event) {
    const fileInput = event.target;
    const fileName = fileInput.files[0]?.name || '';
    const fileNameSpan = fileInput.id === 'contractFile' 
        ? document.getElementById('contractFileName')
        : document.getElementById('invoiceFileName');
    
    fileNameSpan.textContent = fileName;
    
    if (fileName) {
        fileInput.closest('.upload-box').classList.add('has-file');
    } else {
        fileInput.closest('.upload-box').classList.remove('has-file');
    }
    
    checkFilesReady();
}

function checkFilesReady() {
    const contractFile = document.getElementById('contractFile').files[0];
    const invoiceFile = document.getElementById('invoiceFile').files[0];
    const processBtn = document.getElementById('processBtn');
    
    processBtn.disabled = !(contractFile && invoiceFile);
}

async function startReconciliation() {
    const contractFile = document.getElementById('contractFile').files[0];
    const invoiceFile = document.getElementById('invoiceFile').files[0];
    
    if (!contractFile || !invoiceFile) {
        alert('Please select both contract and invoice files');
        return;
    }
    
    showProcessingSection();
    
    try {
        updateProcessingStatus('Uploading files...');
        const sessionId = await uploadFiles(contractFile, invoiceFile);
        currentSessionId = sessionId;
        
        updateProcessingStatus('Extracting text using OCR...');
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        updateProcessingStatus('Analyzing documents with AI...');
        const results = await processDocuments(sessionId);
        
        updateProcessingStatus('Generating reconciliation report...');
        await new Promise(resolve => setTimeout(resolve, 500));
        
        displayResults(results);
    } catch (error) {
        alert('Error processing documents: ' + error.message);
        resetForm();
    }
}

async function uploadFiles(contractFile, invoiceFile) {
    const formData = new FormData();
    formData.append('contract', contractFile);
    formData.append('invoice', invoiceFile);
    
    const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Upload failed');
    }
    
    const data = await response.json();
    return data.session_id;
}

async function processDocuments(sessionId) {
    const response = await fetch(`${API_BASE}/process/${sessionId}`, {
        method: 'POST'
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Processing failed');
    }
    
    const data = await response.json();
    return data.results;
}

function showProcessingSection() {
    document.getElementById('uploadSection').classList.add('hidden');
    document.getElementById('processingSection').classList.remove('hidden');
    document.getElementById('resultsSection').classList.add('hidden');
}

function updateProcessingStatus(status) {
    document.getElementById('processingStatus').textContent = status;
}

function displayResults(results) {
    document.getElementById('processingSection').classList.add('hidden');
    document.getElementById('resultsSection').classList.remove('hidden');
    
    displaySummary(results.comparison.summary);
    displayDiscrepancies(results.comparison.discrepancies);
    displayWarnings(results.comparison.warnings);
    displayMatches(results.comparison.matches);
    displayDocumentDetails(results.contract_details, 'contractDetails');
    displayDocumentDetails(results.invoice_details, 'invoiceDetails');
}

function displaySummary(summary) {
    const statusBadge = document.getElementById('statusBadge');
    statusBadge.textContent = summary.reconciliation_status;
    statusBadge.className = 'status-badge ' + summary.reconciliation_status.toLowerCase();
    
    const summaryStats = document.getElementById('summaryStats');
    summaryStats.innerHTML = `
        <div class="stat-item">
            <div class="stat-value">${summary.total_discrepancies}</div>
            <div class="stat-label">Discrepancies</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${summary.total_warnings}</div>
            <div class="stat-label">Warnings</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${summary.total_matches}</div>
            <div class="stat-label">Matches</div>
        </div>
    `;
}

function displayDiscrepancies(discrepancies) {
    const discrepanciesList = document.getElementById('discrepanciesList');
    
    if (discrepancies.length === 0) {
        discrepanciesList.innerHTML = '<p style="color: #4CAF50;">No discrepancies found!</p>';
        return;
    }
    
    discrepanciesList.innerHTML = discrepancies.map(disc => `
        <div class="discrepancy-item">
            <h4>${disc.field}</h4>
            <div class="discrepancy-values">
                <div class="value-box">
                    <div class="value-label">Contract Value</div>
                    <div class="value-content">${disc.contract_value || 'N/A'}</div>
                </div>
                <div class="value-box">
                    <div class="value-label">Invoice Value</div>
                    <div class="value-content">${disc.invoice_value || 'N/A'}</div>
                </div>
            </div>
            ${disc.difference ? `<p style="margin-top: 10px; color: #f44336;">Difference: ${disc.difference}</p>` : ''}
        </div>
    `).join('');
}

function displayWarnings(warnings) {
    const warningsList = document.getElementById('warningsList');
    
    if (warnings.length === 0) {
        warningsList.innerHTML = '<p style="color: #666;">No warnings</p>';
        return;
    }
    
    warningsList.innerHTML = warnings.map(warning => `
        <div class="warning-item">
            <h4>${warning.field}</h4>
            <p>${warning.message}</p>
        </div>
    `).join('');
}

function displayMatches(matches) {
    const matchesList = document.getElementById('matchesList');
    
    if (matches.length === 0) {
        matchesList.innerHTML = '<p style="color: #666;">No matching fields found</p>';
        return;
    }
    
    matchesList.innerHTML = matches.map(match => 
        `<span class="match-badge">${match}</span>`
    ).join('');
}

function displayDocumentDetails(details, elementId) {
    const detailsElement = document.getElementById(elementId);
    
    const formatValue = (value) => {
        if (value === null || value === undefined) return 'N/A';
        if (typeof value === 'object') return JSON.stringify(value, null, 2);
        return value;
    };
    
    const detailsHtml = Object.entries(details || {})
        .filter(([key]) => key !== 'items')
        .map(([key, value]) => `
            <div class="detail-item">
                <div class="detail-label">${key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</div>
                <div class="detail-value">${formatValue(value)}</div>
            </div>
        `).join('');
    
    detailsElement.innerHTML = detailsHtml || '<p>No details available</p>';
}

function resetForm() {
    document.getElementById('uploadSection').classList.remove('hidden');
    document.getElementById('processingSection').classList.add('hidden');
    document.getElementById('resultsSection').classList.add('hidden');
    
    document.getElementById('contractFile').value = '';
    document.getElementById('invoiceFile').value = '';
    document.getElementById('contractFileName').textContent = '';
    document.getElementById('invoiceFileName').textContent = '';
    
    document.querySelectorAll('.upload-box').forEach(box => {
        box.classList.remove('has-file');
    });
    
    document.getElementById('processBtn').disabled = true;
    currentSessionId = null;
}