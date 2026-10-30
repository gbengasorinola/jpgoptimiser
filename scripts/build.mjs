import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

function run(command, args) {
  const result = spawnSync(command, args, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

// Keep build dependencies isolated from system Python and the media backend.
const python = join('.build-venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(python)) run(process.env.PYTHON ?? 'python3', ['-m', 'venv', '.build-venv']);
run(python, ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements-build.txt']);
run(python, ['scripts/build_dist.py']);
