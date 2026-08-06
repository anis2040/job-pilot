import { spawn, spawnSync } from 'node:child_process'
import { accessSync, constants } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const frontendDir = path.join(root, 'frontend')
const isWindows = process.platform === 'win32'
let npmCmd = isWindows ? 'npm.cmd' : 'npm'
let npmPrefixArgs = []
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
    shell: usesShell(command),
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
  const result = spawnSync(command, args, { stdio: 'ignore', shell: usesShell(command) })
  return !result.error && result.status === 0
}

function usesShell(command) {
  return isWindows && /\.(cmd|bat)$/i.test(command)
}

function findNpmCommand() {
  if (!isWindows) {
    return canRun('npm') ? { command: 'npm', prefixArgs: [] } : null
  }

  const nodeDirs = [
    path.dirname(process.execPath),
    path.join(process.env.ProgramFiles || '', 'nodejs', 'npm.cmd'),
    path.join(process.env['ProgramFiles(x86)'] || '', 'nodejs', 'npm.cmd'),
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'nodejs', 'npm.cmd'),
    path.join(process.env.APPDATA || '', 'nvm', 'current', 'npm.cmd'),
  ]
    .filter(Boolean)
    .map((candidate) => candidate.replace(/[\\/]npm\.cmd$/i, ''))

  for (const dir of nodeDirs) {
    const npmCli = path.join(dir, 'node_modules', 'npm', 'bin', 'npm-cli.js')
    if (exists(npmCli) && canRun(process.execPath, [npmCli, '--version'])) {
      return { command: process.execPath, prefixArgs: [npmCli] }
    }
  }

  const candidates = [
    'npm.cmd',
    ...nodeDirs.map((dir) => path.join(dir, 'npm.cmd')),
  ]

  for (const candidate of candidates) {
    if (canRun(candidate)) {
      return { command: candidate, prefixArgs: [] }
    }
  }

  return null
}

function installNodeWithWinget() {
  if (!isWindows || !canRun('winget', ['--version'])) {
    return false
  }

  console.log('\nnpm was not found, but Node.js is running. Installing or repairing Node.js LTS with winget...')
  const result = spawnSync(
    'winget',
    [
      'install',
      '--id',
      'OpenJS.NodeJS.LTS',
      '--exact',
      '--silent',
      '--accept-package-agreements',
      '--accept-source-agreements',
    ],
    { cwd: root, stdio: 'inherit', shell: false },
  )

  return !result.error && result.status === 0
}

function npmArgs(args) {
  return [...npmPrefixArgs, ...args]
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
  let resolvedNpm = findNpmCommand()
  if (!resolvedNpm) {
    installNodeWithWinget()
    resolvedNpm = findNpmCommand()
  }

  if (!resolvedNpm) {
    const setupScript = isWindows ? 'setup-react.bat' : './setup-react.sh'
    throw new Error(
      `npm was not found. Install Node.js LTS from https://nodejs.org/, then open a new terminal and run ${setupScript} again.`,
    )
  }
  npmCmd = resolvedNpm.command
  npmPrefixArgs = resolvedNpm.prefixArgs

  console.log('\nInstalling frontend dependencies...')
  // --force ensures npm installs rolldown native bindings even when the local
  // Node version is slightly below the package engine range (npm otherwise
  // skips optional dependencies — see https://github.com/npm/cli/issues/4828).
  runChecked(npmCmd, ['install', '--prefix', 'frontend', '--include=optional', '--force'])

  if (frontendToolWorks()) {
    return
  }

  console.log('\nFrontend native dependencies are incomplete. Reinstalling cleanly...')
  runChecked(npmCmd, ['ci', '--prefix', 'frontend', '--include=optional', '--force'])

  if (!frontendToolWorks(true)) {
    throw new Error(
      'Frontend dependencies installed, but Vite still cannot load its native binding. ' +
        'Delete frontend/node_modules and run npm install --prefix frontend --include=optional.',
    )
  }
}

function frontendToolWorks(verbose = false) {
  const result = spawnSync(npmCmd, npmArgs(['--prefix', 'frontend', 'exec', '--', 'vite', '--version']), {
    cwd: root,
    stdio: verbose ? 'inherit' : 'ignore',
    shell: usesShell(npmCmd),
  })

  return !result.error && result.status === 0
}

function ensureFrontendBuild() {
  // The Flask backend serves the built SPA from frontend/dist/ at /app. Vite's
  // dev server (port 5173) doesn't need it, but a fresh clone has no dist/, so
  // /app shows "React app not built". Build once if it's missing; skip if present.
  if (exists(path.join(frontendDir, 'dist', 'index.html'))) {
    return
  }
  console.log('\nBuilding frontend (frontend/dist/ for the backend-served /app route)...')
  runChecked(npmCmd, npmArgs(['run', 'build', '--prefix', 'frontend']))
}

function startProcess(command, args, name) {
  const child = spawn(command, args, {
    cwd: root,
    stdio: 'inherit',
    shell: usesShell(command),
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
  // The backend serves the built SPA at /app, so it needs frontend/dist/.
  // In backend-only mode, ensure frontend deps exist before building.
  if (mode === 'backend') {
    ensureFrontendDeps()
    ensureFrontendBuild()
  } else if (mode === 'full') {
    ensureFrontendBuild()
  }

  if (mode === 'backend') {
    console.log('\nStarting backend on http://localhost:5050')
    backend = startProcess(venvPython, ['web.py'], 'Backend')
  } else if (mode === 'frontend') {
    console.log('\nStarting frontend on http://localhost:5173')
    frontend = startProcess(npmCmd, npmArgs(['--prefix', 'frontend', 'run', 'dev']), 'Frontend')
  } else {
    console.log('\nStarting backend on http://localhost:5050')
    backend = startProcess(venvPython, ['web.py'], 'Backend')

    console.log('Starting frontend on http://localhost:5173')
    frontend = startProcess(npmCmd, npmArgs(['--prefix', 'frontend', 'run', 'dev']), 'Frontend')
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
