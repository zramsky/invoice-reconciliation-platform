
console.log('=== DEBUGGING VENDOR DATA ===');
const vendors = JSON.parse(localStorage.getItem('vendors') || '[]');
const history = JSON.parse(localStorage.getItem('reconciliation_history') || '[]');

console.log('Total vendors in storage:', vendors.length);
console.log('Vendors:', vendors);

console.log('Total history entries:', history.length);
console.log('History:', history);

// Check what makes a vendor "active" for KPI
const activeVendorsForKPI = vendors.filter(vendor => (!vendor.status || vendor.status !== 'disabled') && vendor.contractFile);
console.log('Active vendors (with contractFile):', activeVendorsForKPI.length, activeVendorsForKPI);

// Check what shows in table
const activeVendorsForTable = vendors.filter(vendor => !vendor.status || vendor.status !== 'disabled');
console.log('Active vendors (for table):', activeVendorsForTable.length, activeVendorsForTable);

// Check invoice counts
const vendorInvoiceCounts = {};
history.forEach(entry => {
    const vendorName = entry.results?.contractDetails?.vendor_name;
    if (vendorName) {
        vendorInvoiceCounts[vendorName] = (vendorInvoiceCounts[vendorName] || 0) + 1;
    }
});
console.log('Invoice counts by vendor name:', vendorInvoiceCounts);
