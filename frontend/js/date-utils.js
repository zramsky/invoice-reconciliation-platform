/**
 * Centralized Date Formatting Utilities
 * This file contains all date formatting functions used across the platform.
 * To change the date format platform-wide, modify the DATE_FORMAT constant.
 */

// ============================================================================
// CONFIGURATION - Change this to update date format platform-wide
// ============================================================================
const DATE_FORMAT = 'MM/DD/YYYY'; // Options: 'MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD', 'Month DD, YYYY'

// ============================================================================
// Core Date Formatting Functions
// ============================================================================

/**
 * Format a date string or Date object to the platform's standard format
 * @param {string|Date} dateInput - Date to format (YYYY-MM-DD string, Date object, or various formats)
 * @returns {string} Formatted date string (e.g., "12/31/2024")
 */
function formatDate(dateInput) {
    if (!dateInput || dateInput === 'null' || dateInput === 'undefined') {
        return '';
    }
    
    let date;
    
    // Handle different input types
    if (dateInput instanceof Date) {
        date = dateInput;
    } else if (typeof dateInput === 'string') {
        // Handle YYYY-MM-DD format (from database/API)
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateInput)) {
            // Add time to avoid timezone issues
            date = new Date(dateInput + 'T00:00:00');
        } else {
            date = new Date(dateInput);
        }
    } else {
        return '';
    }
    
    // Check for invalid date
    if (isNaN(date.getTime())) {
        return dateInput.toString(); // Return original if can't parse
    }
    
    // Format based on DATE_FORMAT setting
    switch (DATE_FORMAT) {
        case 'MM/DD/YYYY':
            return formatMMDDYYYY(date);
        case 'DD/MM/YYYY':
            return formatDDMMYYYY(date);
        case 'YYYY-MM-DD':
            return formatYYYYMMDD(date);
        case 'Month DD, YYYY':
            return formatMonthDDYYYY(date);
        default:
            return formatMMDDYYYY(date); // Default to MM/DD/YYYY
    }
}

/**
 * Format date for display in UI (uses platform standard)
 * @param {string|Date} dateInput - Date to format
 * @returns {string} Formatted date for display
 */
function formatDateForDisplay(dateInput) {
    return formatDate(dateInput);
}

/**
 * Format date for form inputs (always YYYY-MM-DD for HTML date inputs)
 * @param {string|Date} dateInput - Date to format
 * @returns {string} Date in YYYY-MM-DD format for HTML inputs
 */
function formatDateForInput(dateInput) {
    if (!dateInput || dateInput === 'null' || dateInput === 'undefined') {
        return '';
    }
    
    let date;
    
    if (dateInput instanceof Date) {
        date = dateInput;
    } else if (typeof dateInput === 'string') {
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateInput)) {
            return dateInput; // Already in correct format
        }
        date = parseDate(dateInput);
    } else {
        return '';
    }
    
    if (!date || isNaN(date.getTime())) {
        return '';
    }
    
    return formatYYYYMMDD(date);
}

/**
 * Parse a date string in various formats to a Date object
 * @param {string} dateStr - Date string to parse
 * @returns {Date|null} Parsed Date object or null if invalid
 */
function parseDate(dateStr) {
    if (!dateStr || dateStr === 'null' || dateStr === 'undefined') {
        return null;
    }
    
    let date;
    
    // Try YYYY-MM-DD format
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        date = new Date(dateStr + 'T00:00:00');
    }
    // Try MM/DD/YYYY or MM-DD-YYYY
    else if (/^\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}$/.test(dateStr)) {
        const parts = dateStr.split(/[\/\-]/);
        date = new Date(parts[2], parts[0] - 1, parts[1]);
    }
    // Try DD/MM/YYYY or DD-MM-YYYY (if day > 12, assume European format)
    else if (/^\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}$/.test(dateStr)) {
        const parts = dateStr.split(/[\/\-]/);
        if (parseInt(parts[0]) > 12) {
            date = new Date(parts[2], parts[1] - 1, parts[0]);
        } else {
            date = new Date(parts[2], parts[0] - 1, parts[1]);
        }
    }
    // Try text format like "January 1, 2024"
    else {
        date = new Date(dateStr);
    }
    
    return (date && !isNaN(date.getTime())) ? date : null;
}

/**
 * Get today's date in the platform's standard format
 * @returns {string} Today's date formatted
 */
function getTodayFormatted() {
    return formatDate(new Date());
}

/**
 * Get today's date in YYYY-MM-DD format for form inputs
 * @returns {string} Today's date in YYYY-MM-DD format
 */
function getTodayForInput() {
    return formatDateForInput(new Date());
}

/**
 * Calculate end date by adding years to start date
 * @param {string|Date} startDate - Start date
 * @param {number} years - Number of years to add
 * @returns {string} End date in platform format
 */
function calculateEndDate(startDate, years) {
    const date = parseDate(startDate);
    if (!date) return '';
    
    const endDate = new Date(date);
    endDate.setFullYear(endDate.getFullYear() + years);
    
    return formatDate(endDate);
}

/**
 * Calculate end date by adding months to start date
 * @param {string|Date} startDate - Start date
 * @param {number} months - Number of months to add
 * @returns {string} End date in platform format
 */
function calculateEndDateMonths(startDate, months) {
    const date = parseDate(startDate);
    if (!date) return '';
    
    const endDate = new Date(date);
    endDate.setMonth(endDate.getMonth() + months);
    
    return formatDate(endDate);
}

/**
 * Format date relative to today (e.g., "Today", "Yesterday", "3 days ago")
 * @param {string|Date} dateInput - Date to format
 * @returns {string} Relative date string
 */
function formatDateRelative(dateInput) {
    const date = parseDate(dateInput);
    if (!date) return formatDate(dateInput);
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    date.setHours(0, 0, 0, 0);
    
    const diffTime = today - date;
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays === -1) return 'Tomorrow';
    if (diffDays > 0 && diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 0 && diffDays > -7) return `In ${Math.abs(diffDays)} days`;
    
    return formatDate(date);
}

// ============================================================================
// Internal Formatting Functions
// ============================================================================

function formatMMDDYYYY(date) {
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const year = date.getFullYear();
    return `${month}/${day}/${year}`;
}

function formatDDMMYYYY(date) {
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
}

function formatYYYYMMDD(date) {
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const year = date.getFullYear();
    return `${year}-${month}-${day}`;
}

function formatMonthDDYYYY(date) {
    const months = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December'];
    return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

// ============================================================================
// Validation Functions
// ============================================================================

/**
 * Check if a date string is valid
 * @param {string} dateStr - Date string to validate
 * @returns {boolean} True if valid date
 */
function isValidDate(dateStr) {
    const date = parseDate(dateStr);
    return date !== null && !isNaN(date.getTime());
}

/**
 * Check if a date is in the future
 * @param {string|Date} dateInput - Date to check
 * @returns {boolean} True if date is in the future
 */
function isFutureDate(dateInput) {
    const date = parseDate(dateInput);
    if (!date) return false;
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    date.setHours(0, 0, 0, 0);
    
    return date > today;
}

/**
 * Check if a date is in the past
 * @param {string|Date} dateInput - Date to check
 * @returns {boolean} True if date is in the past
 */
function isPastDate(dateInput) {
    const date = parseDate(dateInput);
    if (!date) return false;
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    date.setHours(0, 0, 0, 0);
    
    return date < today;
}

// ============================================================================
// Export for use in other files (if using modules)
// ============================================================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatDate,
        formatDateForDisplay,
        formatDateForInput,
        parseDate,
        getTodayFormatted,
        getTodayForInput,
        calculateEndDate,
        calculateEndDateMonths,
        formatDateRelative,
        isValidDate,
        isFutureDate,
        isPastDate,
        DATE_FORMAT
    };
}