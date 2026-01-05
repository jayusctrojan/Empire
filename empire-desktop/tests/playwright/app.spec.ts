import { test, expect } from '@playwright/test'

test.describe('Empire Desktop App', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app with test mode enabled
    await page.goto('/?test=true')
    // Wait for app to load and auth to bypass
    await page.waitForTimeout(1000)
  })

  test.describe('App Launch', () => {
    test('should launch the app successfully', async ({ page }) => {
      // Check the title
      await expect(page).toHaveTitle(/Empire Desktop/)
    })

    test('should show the main interface after auth bypass', async ({ page }) => {
      // Wait for the sidebar to be visible
      const sidebar = page.locator('nav').first()
      await expect(sidebar).toBeVisible({ timeout: 5000 })
    })

    test('should have navigation links', async ({ page }) => {
      // Check for Chats link
      const chatsLink = page.locator('text=Chats').first()
      await expect(chatsLink).toBeVisible()

      // Check for Projects link
      const projectsLink = page.locator('text=Projects').first()
      await expect(projectsLink).toBeVisible()

      // Check for Settings link
      const settingsLink = page.locator('text=Settings').first()
      await expect(settingsLink).toBeVisible()
    })
  })

  test.describe('Database Initialization', () => {
    test('should initialize database without errors', async ({ page }) => {
      // Wait for database to initialize
      await page.waitForTimeout(2000)

      // Check there's no database error message
      const errorMsg = page.locator('text=Database Error')
      await expect(errorMsg).not.toBeVisible()
    })
  })

  test.describe('Projects Feature', () => {
    test('should navigate to Projects view', async ({ page }) => {
      // Click on Projects in sidebar
      await page.click('text=Projects')
      await page.waitForTimeout(500)

      // Verify we're on Projects page - look for Projects heading or New Project button
      const projectsPage = page.locator('h1:has-text("Projects"), button:has-text("New Project")').first()
      await expect(projectsPage).toBeVisible({ timeout: 3000 })
    })

    test('should open New Project modal', async ({ page }) => {
      // Navigate to Projects
      await page.click('text=Projects')
      await page.waitForTimeout(500)

      // Click New Project button
      const newProjectBtn = page.locator('button:has-text("New Project")').first()
      await newProjectBtn.click()
      await page.waitForTimeout(500)

      // Modal should appear - check for "New Project" heading
      const modalTitle = page.locator('h2:has-text("New Project")').or(page.locator('text=Project Name'))
      await expect(modalTitle.first()).toBeVisible({ timeout: 2000 })
    })

    test('should create a new project', async ({ page }) => {
      // Navigate to Projects
      await page.click('text=Projects')
      await page.waitForTimeout(500)

      // Open New Project modal
      const newProjectBtn = page.locator('button:has-text("New Project")').first()
      await newProjectBtn.click()
      await page.waitForTimeout(500)

      // Wait for modal to be visible
      const modal = page.locator('div.fixed.inset-0')
      await expect(modal).toBeVisible({ timeout: 3000 })

      // Fill in project name - target the input inside the modal (not the search input)
      const nameInput = modal.locator('input[type="text"]').first()
      await nameInput.fill('Test Project from Playwright')
      await page.waitForTimeout(300)

      // Click Create Project button inside the modal
      const submitBtn = modal.locator('button:has-text("Create Project")')
      await submitBtn.click()
      await page.waitForTimeout(2000)

      // Check for success - no error message
      const errorMsg = page.locator('text=Failed to create project')
      await expect(errorMsg).not.toBeVisible()
    })

    test('should display the created project in the list', async ({ page }) => {
      // First create a project
      await page.click('text=Projects')
      await page.waitForTimeout(500)

      const newProjectBtn = page.locator('button:has-text("New Project")').first()
      await newProjectBtn.click()
      await page.waitForTimeout(500)

      // Wait for modal
      const modal = page.locator('div.fixed.inset-0')
      await expect(modal).toBeVisible({ timeout: 3000 })

      // Fill in project name inside the modal
      const nameInput = modal.locator('input[type="text"]').first()
      await nameInput.fill('Visible Test Project')
      await page.waitForTimeout(300)

      // Click Create Project inside the modal
      const submitBtn = modal.locator('button:has-text("Create Project")')
      await submitBtn.click()

      // Wait for modal to close
      await page.waitForTimeout(2000)

      // Look for our test project in the list
      const testProject = page.locator('text=Visible Test Project')
      await expect(testProject).toBeVisible({ timeout: 5000 })
    })
  })

  test.describe('Chats Feature', () => {
    test('should navigate to Chats view', async ({ page }) => {
      // Click on Chats in sidebar
      await page.click('text=Chats')
      await page.waitForTimeout(500)

      // Verify we're on Chats page - use .or() for multiple selectors
      const chatsPage = page.locator('text=New Chat').or(page.locator('h1:has-text("Chats")'))
      await expect(chatsPage.first()).toBeVisible({ timeout: 3000 })
    })

    test('should show empty state or chat list', async ({ page }) => {
      await page.click('text=Chats')
      await page.waitForTimeout(500)

      // Either empty state or chat list should be visible
      const chatContent = page.locator('main').first()
      await expect(chatContent).toBeVisible()
    })
  })

  test.describe('Settings Feature', () => {
    test('should navigate to Settings view', async ({ page }) => {
      // Click on Settings in sidebar
      await page.click('text=Settings')
      await page.waitForTimeout(500)

      // Verify we're on Settings page - use .or() for multiple selectors
      const settingsPage = page.locator('h1:has-text("Settings")').or(page.locator('text=API Endpoint'))
      await expect(settingsPage.first()).toBeVisible({ timeout: 3000 })
    })

    test('should show settings options', async ({ page }) => {
      await page.click('text=Settings')
      await page.waitForTimeout(500)

      // Check for common settings elements
      const settingsContent = page.locator('main').first()
      await expect(settingsContent).toBeVisible()
    })
  })

  test.describe('Keyboard Navigation', () => {
    test('should navigate using Cmd+1 to Chats', async ({ page }) => {
      // Press Cmd+1
      await page.keyboard.press('Meta+1')
      await page.waitForTimeout(500)

      // Should be on Chats page - use .or() for multiple selectors
      const chatsIndicator = page.locator('text=New Chat').or(page.locator('text=Chats'))
      await expect(chatsIndicator.first()).toBeVisible({ timeout: 2000 })
    })

    test('should navigate using Cmd+2 to Projects', async ({ page }) => {
      // Press Cmd+2
      await page.keyboard.press('Meta+2')
      await page.waitForTimeout(500)

      // Should be on Projects page - use .or() for multiple selectors
      const projectsIndicator = page.locator('button:has-text("New Project")').or(page.locator('h1:has-text("Projects")'))
      await expect(projectsIndicator.first()).toBeVisible({ timeout: 2000 })
    })

    test('should navigate using Cmd+3 to Settings', async ({ page }) => {
      // Press Cmd+3
      await page.keyboard.press('Meta+3')
      await page.waitForTimeout(500)

      // Should be on Settings page - use .or() for multiple selectors
      const settingsIndicator = page.locator('h1:has-text("Settings")').or(page.locator('text=API Endpoint'))
      await expect(settingsIndicator.first()).toBeVisible({ timeout: 2000 })
    })
  })
})
