const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const PORT = 4173;
const DIST_DIR = path.resolve(__dirname, '../dist');
const SCREENSHOT_DIR = path.resolve(__dirname, '../../docs/screenshots');

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

// Simple static file + mock API server
function startServer() {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const parsedUrl = new URL(req.url, `http://localhost:${PORT}`);
      const pathname = parsedUrl.pathname;

      // Mock API responses
      if (pathname === '/api/v1/auth/me') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ success: true, user: { username: 'DrSatyam', role: 'clinician' } }));
      }
      if (pathname === '/api/v1/sessions') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({
          success: true,
          sessions: [
            { session_id: 's-101', preview: 'Pediatric fever triage', last_active: new Date().toISOString() },
            { session_id: 's-102', preview: 'Hypertension management plan', last_active: new Date(Date.now() - 3600000).toISOString() },
            { session_id: 's-103', preview: 'Dermatology lesion review', last_active: new Date(Date.now() - 86400000).toISOString() }
          ]
        }));
      }
      if (pathname === '/api/v1/history') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({
          success: true,
          messages: [
            { role: 'user', content: 'Patient presents with mild fever and persistent dry cough for 3 days.', timestamp: '10:00' },
            {
              role: 'assistant',
              content: '### Clinical Assessment Summary\n\nBased on your description, the symptoms suggest an acute upper respiratory process. Please consider:\n\n1. **Hydration & Rest**: Ensure adequate fluid intake.\n2. **Monitoring**: Track temperature twice daily.\n3. **Red Flags**: Seek urgent care if dyspnea, chest pain, or high fever persists beyond 72 hours.\n\n*Note: This assessment is informational and does not replace in-person physician evaluation.*',
              source: 'clinical-triage',
              timestamp: '10:01'
            }
          ]
        }));
      }
      if (pathname.startsWith('/api/v1/sessions/') && pathname.endsWith('/history')) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({
          success: true,
          messages: [
            { role: 'user', content: 'Patient presents with mild fever and persistent dry cough for 3 days.', timestamp: '10:00' },
            {
              role: 'assistant',
              content: '### Clinical Assessment Summary\n\nBased on your description, the symptoms suggest an acute upper respiratory process. Please consider:\n\n1. **Hydration & Rest**: Ensure adequate fluid intake.\n2. **Monitoring**: Track temperature twice daily.\n3. **Red Flags**: Seek urgent care if dyspnea, chest pain, or high fever persists beyond 72 hours.\n\n*Note: This assessment is informational and does not replace in-person physician evaluation.*',
              source: 'clinical-triage',
              timestamp: '10:01'
            }
          ]
        }));
      }
      if (pathname === '/api/v1/chat') {
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', () => {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            success: true,
            response: 'Thank you for providing the additional clinical history. I have logged these symptoms.',
            source: 'clinical-triage',
            timestamp: new Date().toLocaleTimeString()
          }));
        });
        return;
      }
      if (pathname === '/api/v1/new-chat') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ success: true, session_id: 's-' + Date.now() }));
      }
      if (pathname === '/api/v1/clear') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ success: true, message: 'Cleared' }));
      }

      // Serve static files from frontend/dist
      let filePath = path.join(DIST_DIR, pathname === '/' ? 'index.html' : pathname);
      if (!fs.existsSync(filePath)) {
        filePath = path.join(DIST_DIR, 'index.html');
      }

      const ext = path.extname(filePath);
      const mimeTypes = {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.svg': 'image/svg+xml'
      };
      const contentType = mimeTypes[ext] || 'application/octet-stream';

      fs.readFile(filePath, (err, content) => {
        if (err) {
          res.writeHead(500);
          res.end(`Server Error: ${err.code}`);
        } else {
          res.writeHead(200, { 'Content-Type': contentType });
          res.end(content, 'utf-8');
        }
      });
    });

    server.listen(PORT, (err) => {
      if (err) reject(err);
      else resolve(server);
    });
  });
}

async function runBrowserQA() {
  console.log('--- Starting Browser QA with Playwright Chromium ---');
  const server = await startServer();
  console.log(`Test server running at http://localhost:${PORT}`);

  const browser = await chromium.launch({ headless: true });
  const qaResults = {
    viewportsTested: [],
    overflowDetected: false,
    consoleErrors: [],
    screenshotsCaptured: []
  };

  try {
    const viewports = [
      { name: 'desktop_1440x900', width: 1440, height: 900, isMobile: false },
      { name: 'laptop_1280x800', width: 1280, height: 800, isMobile: false },
      { name: 'tablet_768x1024', width: 768, height: 1024, isMobile: false },
      { name: 'mobile_390x844', width: 390, height: 844, isMobile: true },
      { name: 'mobile_320x700', width: 320, height: 700, isMobile: true }
    ];

    for (const vp of viewports) {
      console.log(`\nTesting viewport: ${vp.name} (${vp.width}x${vp.height})...`);
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        isMobile: vp.isMobile,
        hasTouch: vp.isMobile
      });

      const page = await context.newPage();

      // Track console errors
      page.on('console', msg => {
        if (msg.type() === 'error') {
          console.warn(`[Browser Console Error] ${msg.text()}`);
          qaResults.consoleErrors.push({ viewport: vp.name, error: msg.text() });
        }
      });
      page.on('pageerror', err => {
        console.error(`[Browser Unhandled Exception] ${err.message}`);
        qaResults.consoleErrors.push({ viewport: vp.name, error: err.message });
      });

      // 1. Test unauthenticated Auth Page first (clear storage)
      await page.goto(`http://localhost:${PORT}`);
      await page.evaluate(() => localStorage.clear());
      await page.reload();
      await page.waitForSelector('.auth-surface', { timeout: 5000 });

      if (vp.name === 'desktop_1440x900') {
        const authPath = path.join(SCREENSHOT_DIR, 'auth_login_view.png');
        await page.screenshot({ path: authPath, fullPage: false });
        qaResults.screenshotsCaptured.push('auth_login_view.png');
        console.log(`  Saved screenshot: auth_login_view.png`);
      }

      // 2. Set authenticated state and reload
      await page.evaluate(() => {
        localStorage.setItem('auth_user', JSON.stringify({ username: 'DrSatyam', user_id: 'usr-1', role: 'clinician' }));
        localStorage.setItem('auth_token', 'mock-qa-token');
        localStorage.setItem('theme', 'light');
        localStorage.setItem('sidebarOpen', 'true');
      });
      await page.reload();
      await page.waitForSelector('.app-header', { timeout: 5000 });
      // Give initial load animations/messages a moment
      await page.waitForTimeout(600);

      // Check horizontal overflow
      const overflow = await page.evaluate(() => {
        const docWidth = document.documentElement.scrollWidth;
        const winWidth = window.innerWidth;
        const bodyWidth = document.body.scrollWidth;
        return {
          docWidth,
          winWidth,
          bodyWidth,
          hasOverflow: docWidth > winWidth + 1 || bodyWidth > winWidth + 1
        };
      });

      if (overflow.hasOverflow) {
        console.error(`  FAIL: Horizontal overflow detected in ${vp.name}! docWidth=${overflow.docWidth}, winWidth=${overflow.winWidth}`);
        qaResults.overflowDetected = true;
      } else {
        console.log(`  PASS: Zero horizontal overflow (docWidth=${overflow.docWidth}, winWidth=${overflow.winWidth})`);
      }

      // Capture main screenshot
      const mainShotPath = path.join(SCREENSHOT_DIR, `${vp.name}_light.png`);
      await page.screenshot({ path: mainShotPath, fullPage: false });
      qaResults.screenshotsCaptured.push(`${vp.name}_light.png`);
      console.log(`  Saved screenshot: ${vp.name}_light.png`);

      // Test dark theme on desktop
      if (vp.name === 'desktop_1440x900') {
        const themeBtn = await page.waitForSelector('.theme-toggle-btn');
        await themeBtn.click();
        await page.waitForTimeout(300);
        const darkShotPath = path.join(SCREENSHOT_DIR, 'desktop_1440x900_dark.png');
        await page.screenshot({ path: darkShotPath, fullPage: false });
        qaResults.screenshotsCaptured.push('desktop_1440x900_dark.png');
        console.log(`  Saved screenshot: desktop_1440x900_dark.png`);
        // Switch back to light
        await themeBtn.click();
        await page.waitForTimeout(200);
      }

      // Test mobile drawer toggle on mobile
      if (vp.name === 'mobile_390x844') {
        const navToggle = await page.waitForSelector('.header-nav-toggle');
        await navToggle.click();
        await page.waitForTimeout(400);
        const drawerShotPath = path.join(SCREENSHOT_DIR, 'mobile_390x844_sidebar.png');
        await page.screenshot({ path: drawerShotPath, fullPage: false });
        qaResults.screenshotsCaptured.push('mobile_390x844_sidebar.png');
        console.log(`  Saved screenshot: mobile_390x844_sidebar.png`);

        // Close sidebar drawer
        const backdrop = await page.$('.sidebar-backdrop');
        if (backdrop) {
          await backdrop.click();
          await page.waitForTimeout(300);
        }
      }

      // Test ConfirmationModal rendering on desktop
      if (vp.name === 'desktop_1440x900') {
        const clearBtn = await page.waitForSelector('button[title="Clear current conversation"]', { timeout: 3000 });
        if (clearBtn) {
          await clearBtn.click();
          await page.waitForSelector('.modal-card', { timeout: 3000 });
          const modalShotPath = path.join(SCREENSHOT_DIR, 'modal_confirmation.png');
          await page.screenshot({ path: modalShotPath, fullPage: false });
          qaResults.screenshotsCaptured.push('modal_confirmation.png');
          console.log(`  Saved screenshot: modal_confirmation.png`);
          // Cancel modal
          const cancelBtn = await page.$('.modal-actions .btn-secondary');
          if (cancelBtn) await cancelBtn.click();
          await page.waitForTimeout(200);
        }
      }

      qaResults.viewportsTested.push({
        name: vp.name,
        width: vp.width,
        height: vp.height,
        status: overflow.hasOverflow ? 'FAIL_OVERFLOW' : 'PASS'
      });

      await context.close();
    }

    console.log('\n--- Browser QA Summary ---');
    console.log(`Total viewports tested: ${qaResults.viewportsTested.length}`);
    console.log(`Total screenshots captured: ${qaResults.screenshotsCaptured.length}`);
    console.log(`Console errors: ${qaResults.consoleErrors.length}`);
    console.log(`Horizontal overflow detected: ${qaResults.overflowDetected ? 'YES (FAIL)' : 'NO (PASS)'}`);

    if (qaResults.overflowDetected || qaResults.consoleErrors.length > 0) {
      console.error('QA FAILED due to errors or overflow.');
      process.exitCode = 1;
    } else {
      console.log('ALL BROWSER QA CHECKS PASSED CLEANLY!');
    }
  } catch (err) {
    console.error('Browser QA execution failed:', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
    server.close();
  }
}

runBrowserQA();
