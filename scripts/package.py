"""Create a source-only MVP archive, excluding databases, credentials and caches."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
files = [root / name for name in ('.gitignore', '.env.example', 'README.md', 'index.html', 'server.py', 'requirements-dev.txt')]
for directory in ('cmo', 'web', 'tests', 'docs', 'scripts', '.github'):
    files.extend(p for p in (root / directory).rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts and p.suffix != '.pyc')
output = root / 'artifacts' / 'CMO_AI_MVP.zip'
output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(files):
        archive.write(file, Path('CMO_AI_MVP') / file.relative_to(root))
print(output)
print(f'{len(files)} source files; no database, .env, credentials, or Git metadata included.')
