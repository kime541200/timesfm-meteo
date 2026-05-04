const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1600 } });

  const requests = [];
  page.on('request', (request) => {
    const url = request.url();
    if (url.includes('/api/forecast') || url.includes('/api/forecasts') || url.includes('/api/temperatures') || url.includes('/api/evaluate')) {
      requests.push({ method: request.method(), url, postData: request.postData() });
    }
  });

  await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle' });
  await page.locator('button:has-text("Apply filters")').click();
  await page.waitForTimeout(1000);

  const beforeText = await page.locator('main').textContent();
  const dateCountBefore = await page.locator('text=/\\d+ dates/').textContent().catch(() => null);

  await page.locator('button:has-text("Run Forecast")').click();
  await page.waitForTimeout(4000);

  const forecastStatusText = await page.locator('text=/Forecast start/').textContent().catch(() => null);
  const mainTextAfter = await page.locator('main').textContent();
  const dateCountAfter = await page.locator('text=/\\d+ dates/').textContent().catch(() => null);

  const result = {
    requests,
    beforeHasChartEmptyState: beforeText?.includes('No data for the selected range') ?? false,
    beforeDateCount: dateCountBefore,
    afterDateCount: dateCountAfter,
    forecastStatusText,
    afterContainsForecastStart: mainTextAfter?.includes('Forecast start') ?? false,
    afterContainsHorizon: mainTextAfter?.includes('horizon') ?? false,
    pageTextSnippet: mainTextAfter?.slice(0, 1000) ?? '',
  };

  console.log(JSON.stringify(result, null, 2));
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
