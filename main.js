const {
    app,
    BrowserWindow
} = require('electron')
const path = require('path')
const {
    spawn
} = require('child_process')
const isDev = require('electron-is-dev')
const portfinder = require('portfinder')

let mainWindow
let flaskProcess

async function createWindow() {
    // Find available port
    const port = await portfinder.getPortPromise()

    // Start Flask server
    const flaskPath = isDev ?
        path.join(__dirname, 'venv', 'Scripts', 'python.exe') :
        path.join(process.resourcesPath, 'flask', 'python.exe')

    const appPath = isDev ?
        path.join(__dirname, 'app.py') :
        path.join(process.resourcesPath, 'flask', 'app.py')

    flaskProcess = spawn(flaskPath, [appPath], {
        env: {
            ...process.env,
            PORT: port.toString()
        }
    })

    // Create Electron window
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true
        }
    })

    // Wait for Flask server to start
    setTimeout(() => {
        mainWindow.loadURL(`http://localhost:${port}`)
    }, 2000)

    mainWindow.on('closed', () => {
        mainWindow = null
    })
}

app.on('ready', createWindow)

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit()
    }
    if (flaskProcess) {
        flaskProcess.kill()
    }
})

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow()
    }
})