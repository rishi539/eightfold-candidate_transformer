#!/usr/bin/env python3
"""Show pipeline results summary."""

import json

with open('output/result_with_pdfs.json', encoding='utf-8') as f:
    data = json.load(f)

print(f'\n📊 Pipeline Results Summary')
print(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
print(f'Total candidates: {len(data["candidates"])}\n')

for i, c in enumerate(data['candidates'], 1):
    name = c.get('full_name', 'Unknown')
    conf = c.get('overall_confidence', 0)
    emails = len(c.get('emails', []))
    phones = len(c.get('phones', []))
    skills = len(c.get('skills', []))
    experience = len(c.get('experience', []))
    education = len(c.get('education', []))
    sources = set()
    for prov in c.get('provenance', []):
        sources.add(prov.get('source', ''))
    sources.discard('')
    
    print(f'{i}. {name}')
    print(f'   Confidence: {conf:.2f}')
    print(f'   Emails: {emails} | Phones: {phones}')
    print(f'   Skills: {skills} | Experience: {experience} | Education: {education}')
    print(f'   Sources: {", ".join(sorted(sources))}')
    print()
