const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch({ headless: true });
  
  const videoDir = path.join(__dirname, 'videos');
  if (!fs.existsSync(videoDir)) {
    fs.mkdirSync(videoDir, { recursive: true });
  }

  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: {
      dir: videoDir,
      size: { width: 1280, height: 800 }
    }
  });

  const page = await context.newPage();
  const targetUrl = 'http://localhost:8080';
  console.log(`Navigating to ${targetUrl}...`);
  await page.goto(targetUrl);

  // 1. Initial pause to show welcome message
  await page.waitForTimeout(3000);

  // 2. Prompt 1: Find apartments nearby to hospital along with pictures
  const prompt1 = "Find apartments within 1km of a hospital and show their pictures";
  console.log(`Typing Prompt 1: "${prompt1}"`);
  await page.type('#input', prompt1, { delay: 60 });
  await page.waitForTimeout(500);
  await page.click('button');

  // Wait for the agent response with cards and pictures to render
  console.log('Waiting for response to Prompt 1...');
  await page.waitForTimeout(14000);

  // 3. Prompt 2: Rich query showing off tool call / database lookup / affordability check
  const prompt2 = "Calculate affordability for $3000 budget and list nearby amenities for apt-101";
  console.log(`Typing Prompt 2: "${prompt2}"`);
  await page.type('#input', prompt2, { delay: 60 });
  await page.waitForTimeout(500);
  await page.click('button');

  // Wait for the agent response with tool calculations and data
  console.log('Waiting for response to Prompt 2...');
  await page.waitForTimeout(14000);

  // Final hold to let the user admire the rich UI
  await page.waitForTimeout(4000);

  console.log('Closing context and saving video...');
  await context.close();
  await browser.close();

  // Find saved video file and copy/rename to demo_video.webm in videoDir
  const videoFiles = fs.readdirSync(videoDir).filter(f => f.endsWith('.webm'));
  if (videoFiles.length > 0) {
    const rawVideo = path.join(videoDir, videoFiles[0]);
    const finalVideo = path.join(videoDir, 'demo_video.webm');
    fs.copyFileSync(rawVideo, finalVideo);
    console.log(`Demo video successfully saved to: ${finalVideo}`);
  }
})();
