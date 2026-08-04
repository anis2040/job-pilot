import { spawn, spawnSync } from 'node:child_process'
import { accessSync, constants } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const isWindows = process.platform === 'win32'
const npmCmd = isWindows ? 'npm.cmd' : 'npm'
const mode = process.argv.includes('--backend-only')
  ? 'backend'
  : process.argv.includes('--frontend-only')
    ? 'frontend'
    : 'full'

const venvPython = path.join(root, '.venv', isWindows ? 'Scripts/python.exe' : 'bin/python')

function exists(target) {
  try {
    accessSync(target, constants.F_OK)
    return true
  } catch {
    return false
  }
}

function runChecked(command, args, options = {}) {
  const label = [command, ...args].join(' ')
  console.log(`\n> ${label}`)
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: 'inherit',
    shell: false,
    ...options,
  })

  if (result.error) {
    throw result.error
  }
  if (result.status !== 0) {
    throw new Error(`Command failed: ${label}`)
  }
}

function canRun(command, args = ['--version']) {
  const result = spawnSync(command, args, { stdio: 'ignore', shell: false })
  return !result.error && result.status === 0
}

function findPythonLauncher() {
  const candidates = isWindows
    ? [
        ['py', ['-3']],
        ['python', []],
      ]
    : [
        ['python3', []],
        ['python', []],
      ]

  for (const [command, prefixArgs] of candidates) {
    if (canRun(command, [...prefixArgs, '--version'])) {
      return { command, prefixArgs }
    }
  }

  throw new Error('Python 3.9+ was not found. Install Python and try again.')
}

function ensureBackendDeps() {
  if (!exists(venvPython)) {
    const launcher = findPythonLauncher()
    console.log('\nCreating Python virtual environment...')
    runChecked(launcher.command, [...launcher.prefixArgs, '-m', 'venv', '.venv'])
  }

  console.log('\nInstalling backend dependencies...')
  runChecked(venvPython, ['-m', 'pip', 'install', '-r', 'requirements.txt'])
}

function ensureFrontendDeps() {
  if (!canRun(npmCmd)) {
    throw new Error('npm was not found. Install Node.js and try again.')
  }

  console.log('\nInstalling frontend dependencies...')
  runChecked(npmCmd, ['install', '--prefix', 'frontend'])
}

function startProcess(command, args, name) {
  const child = spawn(command, args, {
    cwd: root,
    stdio: 'inherit',
    shell: false,
  })

  child.on('error', (error) => {
    console.error(`\n${name} failed to start: ${error.message}`)
    shutdown(1)
  })

  child.on('exit', (code, signal) => {
    if (shuttingDown) {
      return
    }
    const reason = signal ? `signal ${signal}` : `exit code ${code ?? 0}`
    console.error(`\n${name} stopped unexpectedly (${reason}).`)
    shutdown(code ?? 1)
  })

  return child
}

let shuttingDown = false
let backend
let frontend

function stopChild(child) {
  if (!child || child.killed) {
    return
  }

  if (isWindows) {
    spawnSync('taskkill', ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore' })
    return
  }

  child.kill('SIGTERM')
}

function shutdown(exitCode = 0) {
  if (shuttingDown) {
    return
  }
  shuttingDown = true

  stopChild(frontend)
  stopChild(backend)

  setTimeout(() => process.exit(exitCode), 250)
}

process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))

try {
  console.log('Preparing JobPilot AI dev environment...')

  if (mode === 'backend' || mode === 'full') {
    ensureBackendDeps()
  }
  if (mode === 'frontend' || mode === 'full') {
    ensureFrontendDeps()
  }

  if (mode === 'backend') {
    console.log('\nStarting backend on http://localhost:5050')
    backend = startProcess(venvPython, ['web.py'], 'Backend')
  } else if (mode === 'frontend') {
    console.log('\nStarting frontend on http://localhost:5173')
    frontend = startProcess(npmCmd, ['--prefix', 'frontend', 'run', 'dev'], 'Frontend')
  } else {
    console.log('\nStarting backend on http://localhost:5050')
    backend = startProcess(venvPython, ['web.py'], 'Backend')

    console.log('Starting frontend on http://localhost:5173')
    frontend = startProcess(npmCmd, ['--prefix', 'frontend', 'run', 'dev'], 'Frontend')
  }

  console.log('\nDev mode is running:')
  if (mode === 'backend' || mode === 'full') {
    console.log('  Backend:  http://localhost:5050')
  }
  if (mode === 'frontend' || mode === 'full') {
    console.log('  Frontend: http://localhost:5173')
  }
  console.log('Press Ctrl+C to stop the running process(es).')
} catch (error) {
  console.error(`\n${error.message}`)
  process.exit(1)
}
