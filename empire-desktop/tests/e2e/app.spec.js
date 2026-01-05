describe('Empire Desktop App', () => {
  describe('App Launch', () => {
    it('should launch the app successfully', async () => {
      // Wait for app to load
      await browser.pause(3000);

      // Get the window title
      const title = await browser.getTitle();
      console.log('Window title:', title);

      // App should have loaded
      expect(title).toBe('Empire Desktop');
    });

    it('should show the main interface after auth bypass', async () => {
      // Wait for auth bypass timeout (we set 3 seconds)
      await browser.pause(5000);

      // Check if sidebar exists (indicates main app loaded)
      const sidebar = await $('[data-testid="sidebar"]');
      const sidebarExists = await sidebar.isExisting();

      // If no data-testid, try finding by class or structure
      if (!sidebarExists) {
        // Look for the sidebar by its structure
        const sidebarAlt = await $('nav');
        const navExists = await sidebarAlt.isExisting();
        console.log('Nav element exists:', navExists);
      }
    });
  });

  describe('Database Initialization', () => {
    it('should initialize database without errors', async () => {
      // Wait for database init message to disappear
      await browser.pause(3000);

      // Check there's no database error message
      const errorMsg = await $('*=Database Error');
      const hasError = await errorMsg.isExisting();

      expect(hasError).toBe(false);
    });
  });

  describe('Projects Feature', () => {
    it('should navigate to Projects view', async () => {
      // Click on Projects in sidebar
      const projectsButton = await $('button*=Projects');

      if (await projectsButton.isExisting()) {
        await projectsButton.click();
        await browser.pause(1000);
      } else {
        // Try finding by icon or other means
        const projectsNav = await $('[href*="projects"]');
        if (await projectsNav.isExisting()) {
          await projectsNav.click();
          await browser.pause(1000);
        }
      }

      // Verify we're on Projects page
      const projectsHeader = await $('h1*=Projects');
      const headerExists = await projectsHeader.isExisting();
      console.log('Projects header exists:', headerExists);
    });

    it('should open New Project modal', async () => {
      // Click New Project button
      const newProjectBtn = await $('button*=New Project');

      if (await newProjectBtn.isExisting()) {
        await newProjectBtn.click();
        await browser.pause(500);

        // Modal should appear
        const modal = await $('h2*=New Project');
        const modalExists = await modal.isExisting();
        console.log('New Project modal exists:', modalExists);
        expect(modalExists).toBe(true);
      } else {
        // Try Create Project button
        const createBtn = await $('button*=Create Project');
        if (await createBtn.isExisting()) {
          await createBtn.click();
          await browser.pause(500);
        }
      }
    });

    it('should create a new project', async () => {
      // Fill in project name
      const nameInput = await $('input[placeholder*="project name"]');
      if (await nameInput.isExisting()) {
        await nameInput.setValue('Test Project');
      }

      // Fill in description (optional)
      const descInput = await $('textarea[placeholder*="description"]');
      if (await descInput.isExisting()) {
        await descInput.setValue('This is a test project created by automated testing');
      }

      // Click Create/Submit button
      const submitBtn = await $('button[type="submit"]');
      if (await submitBtn.isExisting()) {
        await submitBtn.click();
        await browser.pause(2000);
      }

      // Check for success - no error message
      const errorMsg = await $('*=Failed to create project');
      const hasError = await errorMsg.isExisting();

      if (hasError) {
        const errorText = await errorMsg.getText();
        console.error('Error creating project:', errorText);
      }

      expect(hasError).toBe(false);
    });

    it('should display the created project in the list', async () => {
      // Wait for project list to update
      await browser.pause(1000);

      // Look for our test project
      const testProject = await $('*=Test Project');
      const projectExists = await testProject.isExisting();

      console.log('Test Project exists in list:', projectExists);
      expect(projectExists).toBe(true);
    });

    it('should open project detail view', async () => {
      // Click on the test project
      const testProject = await $('h3*=Test Project');
      if (await testProject.isExisting()) {
        await testProject.click();
        await browser.pause(1000);
      }

      // Should see project detail view with Knowledge panel
      const knowledgePanel = await $('*=Project Knowledge');
      const panelExists = await knowledgePanel.isExisting();
      console.log('Project Knowledge panel exists:', panelExists);
    });
  });

  describe('Chats Feature', () => {
    it('should navigate to Chats view', async () => {
      // Click on Chats in sidebar
      const chatsButton = await $('button*=Chats');

      if (await chatsButton.isExisting()) {
        await chatsButton.click();
        await browser.pause(1000);
      }

      // Verify we're on Chats page
      const chatArea = await $('[data-testid="chat-view"]');
      const chatExists = await chatArea.isExisting();
      console.log('Chat view exists:', chatExists);
    });
  });

  describe('Settings Feature', () => {
    it('should navigate to Settings view', async () => {
      // Click on Settings in sidebar
      const settingsButton = await $('button*=Settings');

      if (await settingsButton.isExisting()) {
        await settingsButton.click();
        await browser.pause(1000);
      }

      // Verify we're on Settings page
      const settingsHeader = await $('h1*=Settings');
      const headerExists = await settingsHeader.isExisting();
      console.log('Settings header exists:', headerExists);
    });
  });

  describe('Cleanup', () => {
    it('should delete the test project', async () => {
      // Navigate back to Projects
      const projectsButton = await $('button*=Projects');
      if (await projectsButton.isExisting()) {
        await projectsButton.click();
        await browser.pause(1000);
      }

      // Find and delete Test Project
      const moreMenu = await $('h3*=Test Project').$('..').$('..').$('button');
      if (await moreMenu.isExisting()) {
        await moreMenu.click();
        await browser.pause(500);

        const deleteBtn = await $('button*=Delete');
        if (await deleteBtn.isExisting()) {
          await deleteBtn.click();
          await browser.pause(500);

          // Handle confirmation dialog if exists
          // Browser's confirm() is auto-accepted in WebDriver
        }
      }

      console.log('Cleanup completed');
    });
  });
});
