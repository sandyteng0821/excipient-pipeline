import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

raw_dir = Path('data/raw')
files = sorted(raw_dir.glob('*.json'))

excipients = []
matrix = []

for f in files:
    data = json.loads(f.read_text())
    name = data.get('name', f.stem)
    sections = data.get('sections', {})
    section_nums = {k.split('_')[0] for k in sections.keys()}
    excipients.append(name)
    row = [1 if str(i) in section_nums else 0 for i in range(1, 23)]
    matrix.append(row)

matrix = np.array(matrix)

fig, ax = plt.subplots(figsize=(14, 60))
ax.imshow(matrix, aspect='auto', cmap='RdYlGn', vmin=0, vmax=1)
ax.set_xticks(range(22))
ax.set_xticklabels([str(i) for i in range(1, 23)])
ax.set_yticks(range(len(excipients)))
ax.set_yticklabels(excipients, fontsize=6)
ax.set_xlabel('Section')
ax.set_title('Raw Section Coverage (301 Excipients)')
plt.tight_layout()
plt.savefig('section_coverage.png', dpi=150, bbox_inches='tight')
print('saved to section_coverage.png')