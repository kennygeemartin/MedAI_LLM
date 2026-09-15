import asyncio
import httpx
import pytest
from backend.ai import answer


@pytest.mark.parametrize('status,content,finish,expected', [
    (200, 'Hello! What would you like to learn about your health?', 'stop', 'general_ai'),
    (429, 'Rate limited', 'stop', 'ai_unavailable'),
    (200, 'You definitely have malaria. Take 500 mg.', 'stop', 'ai_unavailable'),
    (200, 'Incomplete answer', 'length', 'ai_unavailable'),
    (200, 'See https://invented.example', 'stop', 'ai_unavailable'),
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
            assert kwargs['json']['model'] == 'openai/gpt-oss-20b'
            assert kwargs['json']['include_reasoning'] is False
            assert 'reasoning_format' not in kwargs['json']
            assert kwargs['json']['reasoning_effort'] == 'low'
            assert kwargs['json']['max_completion_tokens'] == 1000
            return httpx.Response(status, json={'choices': [{'finish_reason': finish, 'message': {'content': content}}]}, request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx, 'AsyncClient', FakeClient)
    result = asyncio.run(answer('Hello', [], []))
    assert result['mode'] == expected
    assert result['sources'] == []
    if expected == 'general_ai':
        assert 'not reviewed by a clinician' in result['content']
    if status == 429:
        assert 'usage limit' in result['content']
        assert 'reviewed information' not in result['content']


@pytest.mark.parametrize('question,mode', [('I have severe chest pain', 'emergency'), ('What dose should I take?', 'referral')])
def test_safeguards_bypass_hosted_api(monkeypatch, question, mode):
    monkeypatch.setenv('GROQ_API_KEY', 'test-key')
    def unexpected_call(*args, **kwargs):
        raise AssertionError('Safeguard must run before API call')
    monkeypatch.setattr(httpx, 'AsyncClient', unexpected_call)
    assert asyncio.run(answer(question, [], []))['mode'] == mode
