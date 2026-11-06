import { chromium } from '/Users/satyamgupta/Documents/NewGenHealthAI/frontend/node_modules/playwright/index.mjs';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'https://sg721642-newgenhealthai.hf.space';
const SCREENSHOT_DIR = '/Users/satyamgupta/.gemini/antigravity/brain/f68a3956-5251-4366-a127-2eb082ec2b4f/screenshots_rc6';
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const TEST_USER = `verify_rc6_${Date.now()}`;
const TEST_PASS = 'P@ssw0rd123!';
const TEST_USER_2 = `verify_rc6_user2_${Date.now()}`;

const results = {
  journeys: {},
  passed: 0,
  failed: 0,
  screenshots: [],
};

function recordStep(journey, name, passed, details = {}) {
  if (!results.journeys[journey]) results.journeys[journey] = [];
  results.journeys[journey].push({ name, passed, details, timestamp: new Date().toISOString() });
  if (passed) results.passed++;
  else results.failed++;
  console.log(`[${passed ? 'PASS' : 'FAIL'}] ${journey} :: ${name}`);
}

async function takeScreenshot(page, filename, description) {
  const filepath = path.join(SCREENSHOT_DIR, filename);
  await page.screenshot({ path: filepath, fullPage: false });
  results.screenshots.push({ filename, path: filepath, description });
  console.log(`📸 Saved screenshot: ${filename} (${description})`);
}

async function waitForResponse(page, timeout = 45000) {
  await page.waitForSelector('.typing-active', { state: 'attached', timeout: 5000 }).catch(() => {});
  await page.waitForSelector('.typing-active', { state: 'detached', timeout });
  await page.waitForTimeout(1000);
}

async function run() {
  console.log('=== STARTING LIVE RC6 BROWSER ACCEPTANCE SUITE ===');
  console.log('Target Live Space URL:', BASE_URL);

  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    timezoneId: 'Asia/Kolkata', // Real IST user environment
  });

  const page = await context.newPage();

  try {
    // ── JOURNEY 0: Initial Load & Registration ──
    console.log('\n--- Journey 0: Initial App Load & Registration ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 60000 });
    await takeScreenshot(page, '01_landing_auth.png', 'Landing and authentication screen');

    // Switch to Register tab
    const registerTab = page.locator('#tab-register, button:has-text("Register")');
    if (await registerTab.isVisible()) {
      await registerTab.click();
      await page.waitForTimeout(500);
    }

    // Fill registration form
    await page.fill('#auth-username', TEST_USER);
    await page.fill('#auth-password', TEST_PASS);
    await takeScreenshot(page, '02_registration_filled.png', 'Registration form filled');

    // Submit registration
    const submitBtn = page.locator('#auth-submit, button[type="submit"]');
    await submitBtn.click();

    // Wait for chat interface
    await page.waitForSelector('.app-layout, .app-sidebar', { timeout: 15000 });
    recordStep('Journey 0', 'User Registration and Shell Load', true, { username: TEST_USER });
    await takeScreenshot(page, '03_chat_interface_loaded.png', 'Authenticated chat interface loaded');

    // ── JOURNEY 1: Multi-turn Fever Intake & Structured Response ──
    console.log('\n--- Journey 1: Multi-Turn Fever Consultation ---');
    const textarea = page.locator('.composer-textarea, textarea');
    const sendBtn = page.locator('.composer-send-btn, button[title="Send message"]');

    // Send Round 1: Initial symptom presentation
    await textarea.fill('I have had a high fever for three days');
    await sendBtn.click();

    // Wait for typing indicator to detach (LLM response arrived)
    await waitForResponse(page);
    await takeScreenshot(page, '04_fever_round1_response.png', 'Fever Round 1 response with choice chips');

    const assistantMessages = page.locator('.message-wrapper.message-assistant:not(.typing-active)');
    const r1Text = await assistantMessages.first().innerText();
    const chips = page.locator('.followup-choice-chip');
    const chipCount = await chips.count();

    const r1HasChoiceChips = chipCount > 0;
    recordStep('Journey 1', 'Fever Round 1 asks focused follow-up and renders choice chips', r1HasChoiceChips, {
      chipCount,
      preview: r1Text.slice(0, 150),
    });

    // Check sidebar title
    const sessionTitles = page.locator('.session-title');
    await page.waitForSelector('.session-title', { timeout: 10000 });
    const firstTitle = await sessionTitles.first().innerText();
    const titleIsClean = firstTitle.includes('Fever') || firstTitle.includes('Consultation');
    recordStep('Journey 1', 'Stable Title Generation (Fever Consultation)', titleIsClean, {
      sidebarTitle: firstTitle.trim(),
    });

    // Send Round 2: Click a choice chip (e.g. first chip or "3-5 days" or "102 F")
    if (chipCount > 0) {
      await chips.first().click();
    } else {
      await textarea.fill('Temperature is 102 F');
      await sendBtn.click();
    }

    // Wait for round 2 response
    await waitForResponse(page);
    await takeScreenshot(page, '05_fever_round2_response.png', 'Fever Round 2 response');
    const msgCountAfterR2 = await assistantMessages.count();
    recordStep('Journey 1', 'Choice chip click advances consultation smoothly', msgCountAfterR2 >= 2);

    // ── JOURNEY 2: Gibberish Rejection in Triage ──
    console.log('\n--- Journey 2: Gibberish Rejection During Triage ---');
    await textarea.fill('shsauidfewjew');
    await sendBtn.click();

    await waitForResponse(page);
    await takeScreenshot(page, '06_gibberish_rejection.png', 'Gibberish input politely reprompts');

    const lastMsgText = await assistantMessages.last().innerText();
    const isReprompt = lastMsgText.toLowerCase().includes('understand') ||
                        lastMsgText.toLowerCase().includes('clarify') ||
                        lastMsgText.toLowerCase().includes('valid') ||
                        lastMsgText.toLowerCase().includes('re-select');
    recordStep('Journey 2', 'Gibberish rejected without advancing intake', isReprompt, {
      responsePreview: lastMsgText.slice(0, 150),
    });

    // ── JOURNEY 3: Hinglish Third-Person Cardiac Emergency ──
    console.log('\n--- Journey 3: Hinglish Third-Person Cardiac Emergency ---');
    // Start New Conversation
    const newChatBtn = page.locator('.new-chat-btn');
    await newChatBtn.click();
    await page.waitForTimeout(1000);

    // Send Hinglish emergency query
    await textarea.fill('mera dost ko heart attack aaya hai');
    await sendBtn.click();

    // Wait for emergency alert
    await waitForResponse(page);
    await takeScreenshot(page, '07_hinglish_cardiac_emergency.png', 'Immediate 112/108 cardiac emergency alert');

    const emergencyText = await assistantMessages.last().innerText();
    const has112 = emergencyText.includes('112');
    const has108 = emergencyText.includes('108');
    const hasEmergencyTitle = emergencyText.toLowerCase().includes('emergency') || emergencyText.includes('🚨');
    recordStep('Journey 3', 'Hinglish third-person cardiac triggers immediate 112/108 alert', has112 && has108 && hasEmergencyTitle, {
      has112,
      has108,
      hasEmergencyTitle,
    });

    // ── JOURNEY 4: Emergency Follow-up Location Preservation ──
    console.log('\n--- Journey 4: Emergency Follow-up Location Context (Delhi) ---');
    await textarea.fill('Delhi me');
    await sendBtn.click();

    await waitForResponse(page);
    await takeScreenshot(page, '08_delhi_emergency_dispatch.png', 'Delhi localized dispatch guidance');

    const delhiResponseText = await assistantMessages.last().innerText();
    const hasDelhiHospitals = delhiResponseText.includes('AIIMS') || delhiResponseText.includes('Safdarjung') || delhiResponseText.includes('CATS');
    const preservesEmergency = delhiResponseText.includes('112') || delhiResponseText.includes('108');
    recordStep('Journey 4', 'Location follow-up ("Delhi me") returns localized Delhi hospital dispatch', hasDelhiHospitals && preservesEmergency, {
      hasDelhiHospitals,
      preservesEmergency,
      preview: delhiResponseText.slice(0, 150),
    });

    // ── JOURNEY 5: Medical Image Analysis & Fallback Modality ──
    console.log('\n--- Journey 5: Medical Image Analysis & Modality Locking ---');
    await newChatBtn.click();
    await page.waitForTimeout(1000);

    // 5A: Non-medical image rejection
    const fileInput = page.locator('input[type="file"]');
    const natureImgPath = '/Users/satyamgupta/.gemini/antigravity/brain/f68a3956-5251-4366-a127-2eb082ec2b4f/scratch/test_nature_non_medical.png';
    await fileInput.setInputFiles(natureImgPath);

    await waitForResponse(page);
    await takeScreenshot(page, '09_non_medical_image_response.png', 'Non-medical image rejected');
    const imgResponseText1 = await assistantMessages.last().innerText();
    const isUnsupported = imgResponseText1.toLowerCase().includes('unsupported') ||
                          imgResponseText1.toLowerCase().includes('non-medical') ||
                          imgResponseText1.toLowerCase().includes('does not appear');
    recordStep('Journey 5A', 'Non-medical image returns unsupported_image explanation', isUnsupported, {
      preview: imgResponseText1.slice(0, 150),
    });

    // 5B: Skin lesion image with modality dropdown
    const modalitySelect = page.locator('.modality-select');
    if (await modalitySelect.isVisible()) {
      await modalitySelect.selectOption('skin');
      await page.waitForTimeout(500);
    }
    const skinImgPath = '/Users/satyamgupta/.gemini/antigravity/brain/f68a3956-5251-4366-a127-2eb082ec2b4f/scratch/test_skin_lesion.png';
    await fileInput.setInputFiles(skinImgPath);

    await waitForResponse(page);
    await takeScreenshot(page, '10_skin_modality_unavailable.png', 'Skin lesion model unavailable truthful explanation');
    const imgResponseText2 = await assistantMessages.last().innerText();
    const isUnavailable = imgResponseText2.toLowerCase().includes('unavailable') ||
                          imgResponseText2.toLowerCase().includes('not loaded') ||
                          imgResponseText2.toLowerCase().includes('specialist');
    recordStep('Journey 5B', 'Skin lesion returns truthful model_unavailable notice', isUnavailable, {
      preview: imgResponseText2.slice(0, 150),
    });

    // ── JOURNEY 6: Consultation Management & Clear All ──
    console.log('\n--- Journey 6: Consultation Management & Clear All ---');
    // Verify relative timestamp format ("Just now", "seconds ago")
    const timestamps = page.locator('.message-timestamp, .session-time');
    let hasRecentTimestamp = false;
    if (await timestamps.count() > 0) {
      const tsText = await timestamps.first().innerText();
      hasRecentTimestamp = tsText.toLowerCase().includes('just now') ||
                            tsText.toLowerCase().includes('m ago') ||
                            tsText.toLowerCase().includes('s ago') ||
                            !tsText.includes('5h ago');
    }
    recordStep('Journey 6', 'Timestamp formatting does not suffer IST negative skew', hasRecentTimestamp);

    // Test "Clear All" button in sidebar
    const clearAllBtn = page.locator('.btn-clear-all-sessions, button:has-text("Clear All")');
    const clearAllVisible = await clearAllBtn.isVisible();
    if (clearAllVisible) {
      await clearAllBtn.click();
      await page.waitForTimeout(500);
      await takeScreenshot(page, '11_clear_all_confirm_modal.png', 'Clear all consultations confirm modal');

      // Click Confirm Delete in modal
      const confirmDeleteBtn = page.locator('.modal-actions .btn-danger, button:has-text("Delete All")');
      await confirmDeleteBtn.click();
      await page.waitForTimeout(2000);
      await takeScreenshot(page, '12_all_consultations_cleared.png', 'Consultations cleared cleanly');

      const remainingSessions = await page.locator('.history-session-item').count();
      recordStep('Journey 6', 'Clear All Consultations wipes user history and resets shell', remainingSessions === 0, {
        remainingSessions,
      });
    } else {
      recordStep('Journey 6', 'Clear All button visible in sidebar', false);
    }

    // ── JOURNEY 7: Multi-User Isolation & Safe Logout ──
    console.log('\n--- Journey 7: Multi-User Isolation & Safe Logout ---');
    // Click Sign Out
    const logoutBtn = page.locator('.sidebar-logout-btn');
    await logoutBtn.click();
    await page.waitForTimeout(1000);
    await takeScreenshot(page, '13_signed_out_auth_page.png', 'Signed out to AuthPage');

    const authPageVisible = await page.locator('.auth-container').first().isVisible();
    recordStep('Journey 7', 'Logout immediately clears client state and returns to AuthPage', authPageVisible);

    // Register User 2
    const registerTab2 = page.locator('#tab-register, button:has-text("Register")');
    if (await registerTab2.isVisible()) {
      await registerTab2.click();
      await page.waitForTimeout(500);
    }
    await page.fill('#auth-username', TEST_USER_2);
    await page.fill('#auth-password', TEST_PASS);
    await page.locator('#auth-submit, button[type="submit"]').click();

    await page.waitForSelector('.app-layout, .app-sidebar', { timeout: 15000 });
    await page.waitForTimeout(1000);
    await takeScreenshot(page, '14_user2_empty_state.png', 'User 2 isolated empty state');

    const user2Sessions = await page.locator('.history-session-item').count();
    recordStep('Journey 7', 'User 2 has zero access to User 1 consultations (Strict Isolation)', user2Sessions === 0, {
      user2Sessions,
    });

  } catch (err) {
    console.error('Test execution error:', err);
    await takeScreenshot(page, '99_error_state.png', `Error: ${err.message}`);
    recordStep('Suite', 'Global Suite Execution', false, { error: err.message });
  } finally {
    await browser.close();
    fs.writeFileSync(
      path.join(SCREENSHOT_DIR, 'rc6_results.json'),
      JSON.stringify(results, null, 2)
    );
    console.log('\n=== SUITE COMPLETE ===');
    console.log(`Passed: ${results.passed} / ${results.passed + results.failed}`);
  }
}

run();
