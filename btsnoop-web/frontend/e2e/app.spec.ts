import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SAMPLE_FILE = path.resolve(
  __dirname,
  '../../backend/tests/sample.btsnoop'
);

test.describe('btsnoop-web E2E', () => {
  test('1. Page Load - shows upload zone', async ({ page }) => {
    await page.goto('/');
    // The upload zone text should be visible
    await expect(
      page.getByText('Drop a btsnoop file here', { exact: false })
    ).toBeVisible({ timeout: 10000 });
  });

  test('2. File Upload - displays packet list', async ({ page }) => {
    await page.goto('/');
    // Wait for initial render
    await expect(
      page.getByText('Drop a btsnoop file here', { exact: false })
    ).toBeVisible({ timeout: 10000 });

    // Use the hidden file input in the upload zone to upload
    const fileInput = page.locator('.upload-zone input[type="file"]');
    await fileInput.setInputFiles(SAMPLE_FILE);

    // Wait for upload zone to disappear - packet list should show
    await expect(
      page.getByText('Drop a btsnoop file here', { exact: false })
    ).not.toBeVisible({ timeout: 10000 });

    // Verify packet list header appears with packet count
    await expect(
      page.getByText('Packet List', { exact: false })
    ).toBeVisible({ timeout: 10000 });

    // Verify at least 1 packet row is visible (rows have class packet-row)
    const packetRows = page.locator('.packet-row');
    await expect(packetRows.first()).toBeVisible({ timeout: 10000 });

    // Verify protocol column has values - check that at least one row contains HCI
    const protocols = page.locator('.packet-row span.font-semibold');
    await expect(protocols.first()).toBeVisible({ timeout: 10000 });
    const firstProtocol = await protocols.first().textContent();
    expect(firstProtocol).toBeTruthy();
    expect(firstProtocol!.trim().length).toBeGreaterThan(0);
  });

  test('3. Filter Buttons - HCI filter works', async ({ page }) => {
    await page.goto('/');
    await expect(
      page.getByText('Drop a btsnoop file here', { exact: false })
    ).toBeVisible({ timeout: 10000 });

    // Upload file
    const fileInput = page.locator('.upload-zone input[type="file"]');
    await fileInput.setInputFiles(SAMPLE_FILE);

    // Wait for packets to load
    const packetRows = page.locator('.packet-row');
    await expect(packetRows.first()).toBeVisible({ timeout: 10000 });

    // Count total packets before filtering
    // Wait a moment for all packets to arrive via websocket
    await page.waitForTimeout(1000);
    const totalBefore = await packetRows.count();

    // Click "HCI" button in the protocol filter bar
    await page.getByRole('button', { name: 'HCI', exact: true }).click();

    // Wait for filter to apply (packets reload via websocket)
    await page.waitForTimeout(1500);

    // All visible packets should contain "HCI" in protocol column
    const filteredRows = page.locator('.packet-row');
    const filteredCount = await filteredRows.count();
    if (filteredCount > 0) {
      // Check each visible row's protocol
      for (let i = 0; i < Math.min(filteredCount, 10); i++) {
        const protocolText = await filteredRows
          .nth(i)
          .locator('span.font-semibold')
          .textContent();
        expect(protocolText?.toUpperCase()).toContain('HCI');
      }
    }

    // Click "全部" to reset
    await page.getByRole('button', { name: '全部' }).click();
    await page.waitForTimeout(1500);

    // Verify more packets visible than with filter
    const totalAfterReset = await packetRows.count();
    expect(totalAfterReset).toBeGreaterThanOrEqual(filteredCount);
  });

  test('4. Packet Selection - shows decode and hex panels', async ({
    page,
  }) => {
    await page.goto('/');
    await expect(
      page.getByText('Drop a btsnoop file here', { exact: false })
    ).toBeVisible({ timeout: 10000 });

    // Upload file
    const fileInput = page.locator('.upload-zone input[type="file"]');
    await fileInput.setInputFiles(SAMPLE_FILE);

    // Wait for packets
    const packetRows = page.locator('.packet-row');
    await expect(packetRows.first()).toBeVisible({ timeout: 10000 });

    // Click the first packet row
    await packetRows.first().click();

    // Verify "Protocol Decode" panel shows decoded info
    await expect(
      page.getByText('Protocol Decode', { exact: false })
    ).toBeVisible({ timeout: 10000 });

    // After selection, protocol tree should show actual decode content (not "Select a packet" placeholder)
    await expect(
      page.getByText('Select a packet to view protocol details')
    ).not.toBeVisible({ timeout: 10000 });

    // Verify "Hex Dump" panel shows hex data
    await expect(
      page.getByText('Hex Dump', { exact: false })
    ).toBeVisible({ timeout: 10000 });

    // The hex view should show byte content (not "Select a packet" placeholder)
    await expect(
      page.getByText('Select a packet to view hex data')
    ).not.toBeVisible({ timeout: 10000 });

    // Verify hex offset is visible (format: 00000000)
    await expect(
      page.getByText('00000000')
    ).toBeVisible({ timeout: 10000 });
  });

  test('5. Demo Mode - starts and shows packets', async ({ page }) => {
    await page.goto('/');
    await expect(
      page.getByText('Drop a btsnoop file here', { exact: false })
    ).toBeVisible({ timeout: 10000 });

    // Set up dialog handler for the confirm prompt
    page.on('dialog', async (dialog) => {
      // Accept the demo mode dialog
      await dialog.accept();
    });

    // Click Start button
    await page.getByRole('button', { name: 'Start' }).click();

    // Verify demo banner appears
    await expect(
      page.getByText('Demo', { exact: false })
    ).toBeVisible({ timeout: 10000 });

    // Verify packets start appearing - wait for at least 10 packets
    const packetRows = page.locator('.packet-row');
    await expect(async () => {
      const count = await packetRows.count();
      expect(count).toBeGreaterThanOrEqual(10);
    }).toPass({ timeout: 30000, intervals: [500] });
  });

  test('6. Export - opens export dialog', async ({ page }) => {
    await page.goto('/');
    await expect(
      page.getByText('Drop a btsnoop file here', { exact: false })
    ).toBeVisible({ timeout: 10000 });

    // Upload file first
    const fileInput = page.locator('.upload-zone input[type="file"]');
    await fileInput.setInputFiles(SAMPLE_FILE);

    // Wait for packets to load
    const packetRows = page.locator('.packet-row');
    await expect(packetRows.first()).toBeVisible({ timeout: 10000 });

    // Set up dialog handler for the export prompt
    let promptMessage = '';
    page.on('dialog', async (dialog) => {
      promptMessage = dialog.message();
      await dialog.accept('1'); // Select pcapng format
    });

    // Click Export button
    await page.getByRole('button', { name: 'Export' }).click();

    // Verify the prompt appeared with format options
    await page.waitForTimeout(500);
    expect(promptMessage).toContain('pcapng');
  });
});
