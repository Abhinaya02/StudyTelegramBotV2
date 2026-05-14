const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const htmlFilePath = process.argv[2];
    const outputFilePath = process.argv[3];

    if (!htmlFilePath || !outputFilePath) {
        console.error('Usage: node generate_pdf.js <input.html> <output.pdf>');
        process.exit(1);
    }

    let browser;
    try {
        const html = fs.readFileSync(htmlFilePath, 'utf8');

        // Launch headless browser
        browser = await chromium.launch({
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        });
        
        const page = await browser.newPage();
        
        // Wait for network to be idle so images/fonts load if there are any
        await page.setContent(html, { waitUntil: 'load' });
        
        // Emulate print media for better PDF output
        await page.emulateMedia({ media: 'print' });

        await page.pdf({
            path: outputFilePath,
            format: 'A4',
            printBackground: true,
            margin: { top: '20mm', right: '15mm', bottom: '20mm', left: '15mm' }
        });

    } catch (err) {
        console.error('Error generating PDF:', err);
        process.exit(1);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
})();
