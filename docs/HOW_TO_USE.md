# How to Use Your Invoice Reconciliation Platform

## 🎉 Your App is Now Live!

**Your website:** https://zramsky.github.io/invoice-reconciliation-platform/

## What This Does (In Simple Terms)

This app helps you compare contracts and invoices to find mistakes or differences. Think of it like having an AI assistant that reads both documents and tells you if the invoice matches what was agreed in the contract.

For example:
- ✅ "The vendor name matches"
- ❌ "The invoice amount is $1,500 but the contract says $1,200"
- ⚠️ "The invoice references a different contract number"

## How to Use It (Step by Step)

### Step 1: Get an OpenAI API Key (One-Time Setup)

**What is this?** Think of it like a key that lets the app talk to ChatGPT to understand your documents.

**How to get it:**
1. Go to https://platform.openai.com/api-keys
2. Create an account or sign in
3. Click "Create new secret key"
4. Copy the key (starts with "sk-")
5. **Important:** Add $5-10 in credits to your OpenAI account (this is what pays for the AI to read your documents)

**Cost:** Usually costs about $0.01-0.05 per document comparison (very cheap!)

### Step 2: Use the App

1. **Open your app:** https://zramsky.github.io/invoice-reconciliation-platform/

2. **Enter your API key:**
   - Paste your OpenAI key in the first box
   - Click "Save & Test Key"
   - You should see "✅ API key verified and ready!"

3. **Upload your documents:**
   - Click the contract box and select your contract PDF
   - Click the invoice box and select your invoice PDF
   - Both files should show green checkmarks

4. **Start the comparison:**
   - Click "Start Reconciliation"
   - Wait while the app reads both documents (takes 1-2 minutes)

5. **Review the results:**
   - See if documents PASSED or FAILED reconciliation
   - Check any discrepancies found
   - Review warnings and matches

## What Files Work?

- ✅ PDF documents (best)
- ✅ Image files (PNG, JPG, JPEG)
- ✅ Scanned documents (the app can read text from images)
- ❌ Maximum file size: 10MB each

## Privacy & Security

- 🔒 **Your documents never leave your computer** - everything happens in your browser
- 🔒 **Your API key is stored only in your browser** - not on any server
- 🔒 **Only the text extracted from documents is sent to OpenAI** - not the actual files
- 🔒 **No data is stored anywhere** - everything is deleted when you close the browser

## Example Results You Might See

**✅ When Everything Matches:**
- Status: PASSED
- Vendor Name: ✓ Match
- Total Amount: ✓ Match
- Contract Reference: ✓ Match

**❌ When There Are Problems:**
- Status: FAILED
- Discrepancies Found:
  - Vendor Name: Contract says "ABC Corp" but Invoice says "ABC Company"
  - Total Amount: Contract $1,200 but Invoice $1,500 (Difference: $300)

## Troubleshooting

**"API key not working":**
- Make sure you copied the whole key (starts with "sk-")
- Check that you have credits in your OpenAI account
- Try creating a new API key

**"Can't read my document":**
- Make sure the PDF has readable text (not just an image)
- For scanned documents, ensure the text is clear and not blurry
- Large files might take longer to process

**"Processing taking too long":**
- PDFs with many pages take longer
- Large image files take longer
- Try with a simpler document first

**"Getting strange results":**
- The AI works best with clearly formatted business documents
- Handwritten text might not work well
- Try with a standard invoice or contract format

## Tips for Best Results

1. **Use clear, standard business documents**
2. **Make sure contract and invoice are from the same vendor**
3. **PDFs with selectable text work better than scanned images**
4. **Check that your documents have clear vendor names and amounts**

## Need Help?

- Check the troubleshooting section above
- Make sure you have internet connection
- Try refreshing the page and starting over
- The app works best in Chrome, Firefox, or Safari

## Cost Breakdown

- **Website hosting:** FREE (GitHub Pages)
- **Using the app:** Only pay for OpenAI usage
- **Typical cost per comparison:** $0.01-0.05
- **Monthly cost for 100 comparisons:** ~$2-5

---

## For Future Updates

Your app automatically updates! Since it's hosted on GitHub Pages, any improvements I make will automatically appear at your website URL.

**Your live app:** https://zramsky.github.io/invoice-reconciliation-platform/

Bookmark this link and use it whenever you need to reconcile invoices with contracts!