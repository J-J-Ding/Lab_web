"""Regenerate vendored notices from the exact installed lockfile dependency tree."""
import json
from pathlib import Path

root=Path(__file__).resolve().parent
parts=[]
for manifest in sorted((root/'node_modules').rglob('package.json')):
    if '/esbuild' in str(manifest):continue
    try:meta=json.loads(manifest.read_text())
    except ValueError:continue
    licenses=[p for p in manifest.parent.iterdir() if p.is_file() and p.name.lower() in ('license','license.md','license.txt','copying')]
    if licenses:
        parts.append(f"{meta.get('name')} {meta.get('version')} ({meta.get('license','see license')})\n"+'\n'.join(p.read_text(errors='replace') for p in licenses))
(root.parent/'vendor/lab-editor.LICENSE.txt').write_text('\n\n'.join(parts).rstrip()+'\n')
