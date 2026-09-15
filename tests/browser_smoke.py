"""Optional browser integration check: pip install playwright; python tests/browser_smoke.py."""
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)

def main():
    with tempfile.TemporaryDirectory(prefix='medai-browser-') as directory:
        env = os.environ | {'DATABASE_URL':'sqlite:///' + str(Path(directory) / 'browser.db'), 'JWT_SECRET':secrets.token_urlsafe(48), 'APP_ENV':'development', 'INFERENCE_URL':'', 'INFERENCE_API_KEY':'', 'VERCEL':''}
        process = subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8765'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            for _ in range(80):
                try:
                    if httpx.get('http://127.0.0.1:8765/api/health').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.25)
            else:raise RuntimeError('Browser test server did not start.')
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='msedge' if os.name=='nt' else 'chromium',headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:8765')
                expect(page.locator('h1').first).to_contain_text('Your health,')
                page.screenshot(path=str(ARTIFACTS/'desktop.png'),full_page=True)
                page.locator('#account').click()
                page.locator('#auth-switch').click()
                page.locator('#full-name').fill('Browser Test')
                page.locator('#email').fill('browser@example.com')
                page.locator('#password').fill('browser-test-password')
                page.locator('#consent').check()
                page.locator('#auth-submit').click()
                expect(page.locator('#auth-dialog')).not_to_be_visible()
                page.locator('#question').fill('Tell me about malaria')
                sent_at=time.monotonic()
                page.locator('#send').click()
                expect(page.locator('.thinking-status')).to_contain_text('Thinking')
                expect(page.locator('.message.user')).to_contain_text('Tell me about malaria')
                expect(page.locator('.message.assistant')).to_contain_text('reviewed information',timeout=10000)
                assert time.monotonic()-sent_at >= 4.9, 'Normal reply appeared before the five-second pause'
                expect(page.locator('.thinking-status')).to_have_count(0)
                page.locator('#question').fill('I have severe chest pain')
                page.locator('#send').click()
                expect(page.locator('.message.emergency')).to_contain_text('immediate help')
                page.locator('.feedback').last.get_by_role('button',name='Yes',exact=True).click()
                expect(page.locator('.feedback').last).to_contain_text('Thank you')
                page.reload()
                page.locator('[data-conversation]').first.click()
                expect(page.locator('.message')).to_have_count(4)
                # Elevate only the isolated test database account to exercise administrator UI.
                subprocess.run([sys.executable,'-c',"from backend.database import Session,User; from sqlalchemy import select; db=Session(); u=db.scalar(select(User).where(User.email=='browser@example.com')); u.role='admin'; db.commit(); db.close()"],cwd=ROOT,env=env,check=True)
                page.reload()
                page.locator('#admin-nav').click()
                expect(page.locator('.stat')).to_have_count(4)
                page.locator('[data-admin="documents"]').click()
                page.locator('#add-document').click()
                page.locator('#doc-title').fill('Malaria education')
                page.locator('#doc-category').fill('Malaria')
                page.locator('#doc-source').fill('https://www.who.int/news-room/fact-sheets/detail/malaria')
                page.locator('#doc-content').fill('Malaria may involve fever and headache. Consult a qualified healthcare professional about testing.')
                page.locator('#doc-approved').check()
                page.locator('#document-form button[type="submit"]').click()
                expect(page.locator('#document-dialog')).not_to_be_visible()
                expect(page.locator('#admin-content')).to_contain_text('Published')
                page.locator('[data-view="library"]').click()
                page.locator('[data-article]').click()
                expect(page.locator('#article-content')).to_contain_text('Malaria education')
                page.locator('[data-close="article-dialog"]').click()
                page.locator('#new-chat').click()
                page.locator('#question').fill('malaria symptoms')
                page.locator('#send').click()
                expect(page.locator('.message.assistant')).to_contain_text('Library excerpts',timeout=10000)
                expect(page.locator('.source-links a')).to_have_count(1)
                page.screenshot(path=str(ARTIFACTS/'conversation.png'),full_page=True)
                page.on('dialog',lambda dialog:dialog.accept())
                page.locator('#delete-chat').click()
                expect(page.locator('#welcome')).to_be_visible()
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(ARTIFACTS/'mobile.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile layout overflows'
                assert not errors, errors
                browser.close()
            print('Browser smoke passed: registration, chat, emergency, feedback, persistence, admin publication, library, sources, deletion, mobile layout.')
        finally:
            process.terminate()
            process.wait(timeout=15)

if __name__=='__main__':
    main()
