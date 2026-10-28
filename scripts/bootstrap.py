"""Create a repository-local environment without changing user configuration."""
from pathlib import Path
import subprocess
import sys
import venv

def main():
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10+ required')
    root = Path(__file__).resolve().parents[1]
    env = root / '.venv'
    python = env / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(env)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')], check=True)
    print(f'Ready: {python}\nNext: read SKILL.md and supply your CV to the AI assistant.')

if __name__ == '__main__':
    main()
