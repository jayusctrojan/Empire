const path = require('path');

// Path to the built Tauri app
const appPath = path.join(
  __dirname,
  'src-tauri/target/release/bundle/macos/Empire Desktop.app/Contents/MacOS/empire-desktop'
);

exports.config = {
  specs: ['./tests/e2e/**/*.spec.js'],
  exclude: [],
  maxInstances: 1,
  capabilities: [
    {
      'tauri:options': {
        application: appPath,
      },
    },
  ],
  logLevel: 'info',
  bail: 0,
  baseUrl: '',
  waitforTimeout: 10000,
  connectionRetryTimeout: 120000,
  connectionRetryCount: 3,
  framework: 'mocha',
  reporters: ['spec'],
  mochaOpts: {
    ui: 'bdd',
    timeout: 60000,
  },

  // Hooks
  onPrepare: async function () {
    const { spawn } = require('child_process');

    // Start tauri-driver
    const tauriDriver = spawn('tauri-driver', [], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    tauriDriver.stdout.on('data', (data) => {
      console.log(`tauri-driver: ${data}`);
    });

    tauriDriver.stderr.on('data', (data) => {
      console.error(`tauri-driver error: ${data}`);
    });

    // Give tauri-driver time to start
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Store reference for cleanup
    global.tauriDriver = tauriDriver;
  },

  onComplete: async function () {
    // Kill tauri-driver
    if (global.tauriDriver) {
      global.tauriDriver.kill();
    }
  },
};
