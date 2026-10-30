import { expect, test } from '@playwright/test';

test('saved data, navigation, downloads and responsive layout', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Simulador de lanzamientos.' })).toBeVisible();
  await expect(page.frameLocator('iframe').locator('#play')).toBeVisible();
  await page.getByRole('navigation').getByRole('link', { name: 'Lanzadores', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Conoce al lanzador.' })).toBeVisible();
  await expect(page.locator('.pitcher-card')).toBeVisible();
  await page.getByLabel('Buscar lanzador').fill('no-existe');
  await expect(page.getByText('No hay resultados disponibles para esta selección.')).toBeVisible();
  await page.getByLabel('Buscar lanzador').fill('');
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Descargar tabla completa' }).click();
  expect((await download).suggestedFilename()).toMatch(/pitchers.*\.csv$/);
  await page.getByRole('navigation').getByRole('link', { name: 'Confianza', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Errores y calibración' })).toBeVisible();
  await page.getByLabel('Prueba evaluada').selectOption('park');
  await expect(page.locator('tbody tr').first()).toBeVisible();
  await page.getByRole('navigation').getByRole('link', { name: 'Ayuda', exact: true }).click();
  await expect(page.locator('.markdown')).toBeVisible();
  await expect(page.getByRole('navigation').getByRole('link', { name: 'Histórico v8' })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('simulation submits edited measurements and marks old results stale', async ({ page }) => {
  const profile = { type: 'Four-Seam', hand: 'Right', n: 400, median: { RelSpeed: 90, HorzBreak: 8, InducedVertBreak: 15, SpinRate: 2200 }, p01: {}, p99: {} };
  await page.route('**/api/bootstrap', route => route.fulfill({ json: { runs: [{ id: 'stuff_plus_output_v9', profiles: [profile], stadiums: [], stadium_context: false, pitchers: [] }], documents: [] } }));
  let payload: Record<string, unknown> = {};
  await page.route('**/api/simulate', async route => {
    payload = route.request().postDataJSON();
    await route.fulfill({ json: { results: [{ stadium: 'Altitud baja', pitching_plus: 104, stuff_plus: 102, location_plus: 101 }, { stadium: 'Altitud media', pitching_plus: 104, stuff_plus: 102, location_plus: 101 }], outside: [], reference: {} } });
  });
  await page.goto('/#simulador');
  await page.getByLabel('Velocidad (mph)', { exact: true }).fill('94');
  await page.getByRole('button', { name: 'Estimar Stuff+' }).click();
  await expect(page.locator('.results .score-card')).toHaveCount(2);
  expect((payload.measurements as Record<string, number>).RelSpeed).toBe(94);
  expect(payload.stadiums).toEqual(['Extreme Altitude', 'No Altitude']);
  await page.getByLabel('Velocidad (mph)', { exact: true }).fill('95');
  await expect(page.getByText('Los datos cambiaron.')).toBeVisible();
  await page.route('**/api/simulate', route => route.fulfill({ status: 503, json: { error: 'Modelo no disponible para esta prueba.' } }));
  await page.getByRole('button', { name: 'Estimar Stuff+' }).click();
  await expect(page.locator('form').getByRole('alert')).toHaveText('Modelo no disponible para esta prueba.');
});

test('API connection failure can be retried', async ({ page }) => {
  await page.route('**/api/bootstrap', route => route.fulfill({ status: 503, json: { error: 'Offline' } }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('No se pudo conectar con la API');
  await page.unroute('**/api/bootstrap');
  await page.getByRole('button', { name: 'Reintentar' }).click();
  await expect(page.getByRole('heading', { name: 'Simulador de lanzamientos.' })).toBeVisible();
});

test('two selected stadiums show real model probability differences', async ({ page, request }) => {
  const bootstrap = await (await request.get('/api/bootstrap')).json();
  test.skip(!bootstrap.runs.some((r: { id: string }) => r.id === 'stuff_plus_output_v9_estadios'), 'Requires the real stadium model');
  await page.goto('/#simulador');
  await page.getByRole('combobox', { name: 'Tipo de lanzamiento', exact: true }).selectOption('Four-Seam');
  await page.getByRole('combobox', { name: 'Mano del lanzador', exact: true }).selectOption({ label: 'Derecho' });
  await page.getByRole('combobox', { name: 'Escenario 1', exact: true }).selectOption('mexico_ahh');
  await page.getByRole('combobox', { name: 'Escenario 2', exact: true }).selectOption('monterrey_beisbol');
  const response = page.waitForResponse(r => r.url().endsWith('/api/simulate') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Estimar Stuff+' }).click();
  const result = await (await response).json();
  expect(result.results.map((r: { stadium_id: string }) => r.stadium_id)).toEqual(['mexico_ahh', 'monterrey_beisbol']);
  expect(result.results[0].stuff_plus).toBe(result.results[1].stuff_plus);
  expect(result.results[0].p_whiff).not.toBe(result.results[1].p_whiff);
  await expect(page.locator('.results .score-card').first()).toContainText('Estadio Alfredo Harp Helu');
  await expect(page.locator('.results .score-card').nth(1)).toContainText('Estadio Mobil Super');
  const row = page.locator('.results tbody tr').filter({ hasText: 'Swing fallido por lanzamiento' });
  await expect(row).toBeVisible();
  const cells = await row.locator('td').allTextContents();
  expect(cells[1]).not.toBe(cells[2]);
  expect(Number(cells[3])).not.toBe(0);
  await page.getByRole('combobox', { name: 'Escenario 2', exact: true }).selectOption('veracruz_avila');
  await expect(page.getByText('Los datos cambiaron.')).toBeVisible();
  const updated = page.waitForResponse(r => r.url().endsWith('/api/simulate') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Estimar Stuff+' }).click();
  expect((await (await updated).json()).results[1].stadium_id).toBe('veracruz_avila');
  await expect(page.locator('.results .score-card').nth(1)).not.toContainText('Estadio Mobil Super');
  await expect(page.getByText('Los datos cambiaron.')).toHaveCount(0);
});
