import asyncio
import httpx
import pytest
from backend.ai import answer


@pytest.mark.parametrize('status,content,finish,expected', [
    (200, 'Hello! What would you like to learn about your health?', 'stop', 'general_ai'),
    (429, 'Rate limited', 'stop', 'no_evidence'),
    (200, 'You definitely have malaria. Take 500 mg.', 'stop', 'no_evidence'),
    (200, 'Incomplete answer', 'length', 'no_evidence'),
    (200, 'See https://invented.example', 'stop', 'no_evidence'),
])
def test_hosted_answers_and_failures(monkeypatch, status, content, finish, expected):
    monkeypatch.setenv('GROQ_API_KEY', 'test-key')
    monkeypatch.delenv('INFERENCE_URL', raising=False)
    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            assert url == 'https://api.groq.com/openai/v1/chat/completions'
            assert kwargs['json']['model'] == 'qwen/qwen3.6-27b'
            assert kwargs['json']['reasoning_format'] == 'hidden'
            return httpx.Response(status, json={'choices': [{'finish_reason': finish, 'message': {'content': content}}]}, request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx, 'AsyncClient', FakeClient)
    result = asyncio.run(answer('Hello', [], []))
    assert result['mode'] == expected
    assert result['sources'] == []
    if expected == 'general_ai':
        assert 'not reviewed by a clinician' in result['content']


@pytest.mark.parametrize('question,mode', [('I have severe chest pain', 'emergency'), ('What dose should I take?', 'referral')])
def test_safeguards_bypass_hosted_api(monkeypatch, question, mode):
    monkeypatch.setenv('GROQ_API_KEY', 'test-key')
    def unexpected_call(*args, **kwargs):
        raise AssertionError('Safeguard must run before API call')
    monkeypatch.setattr(httpx, 'AsyncClient', unexpected_call)
    assert asyncio.run(answer(question, [], []))['mode'] == mode
