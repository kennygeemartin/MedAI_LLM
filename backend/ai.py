"""Conservative evidence excerpts, with an optional private MedGemma RAG service."""
import os
import re
import httpx

EMERGENCY = re.compile(r"(?:cannot|can't|cant|unable to|struggling to) breathe|(?:severe|difficulty|trouble) breathing|breathing (?:difficulty|problems)|shortness of breath|chest pain|unconscious|unresponsive|severe bleeding|bleeding (?:heavily|won't stop)|suicid|kill myself|overdose|seizure|face droop|slurred speech", re.I)
UNSAFE = re.compile(r'\b(?:you (?:definitely )?have|you are diagnosed|your diagnosis is|I diagnose|take \d|\d+\s*(?:mg|mcg|tablets?|capsules?)|I prescribe)\b', re.I)
STOP = set('a an the i me my it is are was were what which how can could should do does have has this that to of in for with and or please tell about yesterday today started'.split())
PRESCRIBING = re.compile(r'\b(?:prescribe|dosage|dose|how much (?:medicine|medication)|which (?:drug|medicine|antibiotic)|what (?:drug|medicine|antibiotic))\b', re.I)

def tokens(text):
    return set(re.findall(r'[a-z]{3,}', text.lower())) - STOP

def retrieve(question, history, documents):
    context = question + ' ' + ' '.join(m.content for m in history[-4:] if m.sender == 'user')
    query = tokens(context)
    matches = []
    for doc in documents:
        words = doc.content.split()
        for start in range(0, len(words), 150):
            chunk = ' '.join(words[start:start + 200])
            overlap = query & tokens(doc.title + ' ' + doc.category + ' ' + chunk)
            if overlap:
                matches.append((len(overlap), {'id': doc.id, 'title': doc.title, 'url': doc.source, 'text': chunk}))
    matches.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in matches[:3]]

async def answer(question, history, documents):
    if EMERGENCY.search(question):
        return {'content': 'Your message mentions a possible emergency. Please seek immediate help from local emergency services or the nearest emergency department. If possible, ask someone nearby to stay with you. Do not wait for this chat to assess your condition.', 'mode': 'emergency', 'sources': []}
    if PRESCRIBING.search(question):
        return {'content': 'I cannot select medicines or recommend a dose for you. Please ask a qualified healthcare professional or pharmacist about medication and your individual needs. I can help you explore general information about a health topic.', 'mode': 'referral', 'sources': []}
    sources = retrieve(question, history, documents)
    endpoint = os.getenv('INFERENCE_URL', '').rstrip('/')
    api_key = os.getenv('INFERENCE_API_KEY', '')
    if endpoint and api_key and documents:
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(endpoint + '/generate', headers={'Authorization': 'Bearer ' + api_key}, json={'question': question, 'history': [{'role': m.sender, 'content': m.content} for m in history[-8:]], 'documents': [{'id': d.id, 'title': d.title, 'url': d.source, 'content': d.content} for d in documents]})
                response.raise_for_status()
                result = response.json()
            content = result.get('content', '')
            valid = {d.id: d for d in documents}
            cited = result.get('sources', [])
            if isinstance(content, str) and 0 < len(content) <= 8000 and not UNSAFE.search(content) and cited and all(isinstance(s, dict) and s.get('id') in valid for s in cited):
                sources = [{'id': s['id'], 'title': valid[s['id']].title, 'url': valid[s['id']].source} for s in cited]
                return {'content': content + '\n\nThis is general health information. A qualified clinician should assess symptoms and treatment needs.', 'mode': 'medgemma', 'sources': sources}
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            pass
    if not sources:
        return {'content': 'I do not have reviewed information that answers this question yet. Please speak with a qualified healthcare professional about symptoms or treatment. You can try asking about another topic in the health library.', 'mode': 'no_evidence', 'sources': []}
    excerpts = '\n\n'.join(f'[{i + 1}] {s["title"]}\n{s["text"]}' for i, s in enumerate(sources))
    return {'content': 'Here are relevant excerpts from the reviewed health library:\n\n' + excerpts + '\n\nThese excerpts are general information and cannot determine a diagnosis or treatment for you. Please discuss symptoms with a qualified healthcare professional.', 'mode': 'evidence', 'sources': [{k: v for k, v in s.items() if k != 'text'} for s in sources]}
