"""Real browser workflow check. Requires Python Playwright + Chromium (dev tools only)."""
import csv
import io
import os
import re
import sys
import tempfile
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from server import handler_for
from cmo.store import Store
from cmo.service import Service


def run():
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'DEEPSEEK_API_KEY': '', 'CMO_LLM_API_KEY':'', 'CMO_DAILY_GENERATION_LIMIT':'100'}):
        service=Service(Store(Path(directory)/'test.sqlite3'))
        server=ThreadingHTTPServer(('127.0.0.1',0), handler_for(service))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
                page=browser.new_page(viewport={'width':1440,'height':1050})
                errors=[]
                page.on('pageerror',lambda e: errors.append(str(e)))
                page.on('console',lambda m: errors.append(m.text) if m.type=='error' else None)
                page.goto(base)
                expect(page.get_by_role('heading',name='Your marketing, in good hands.')).to_be_visible()
                expect(page.locator('#mode-pill')).to_have_text('Local mode')
                # Save brand and confirm it survives a page reload.
                page.locator('nav a[data-page="brand"]').click()
                page.locator('#name').fill('Bright & Co')
                page.locator('#product').fill('Affordable marketing tools for small businesses')
                page.get_by_role('button',name='Save Brand Brain').click()
                expect(page.locator('#toast')).to_contain_text('Brand Brain saved')
                page.reload()
                expect(page.locator('#name')).to_have_value('Bright & Co')
                # Generate a plan, then persist an asset from the first plan item.
                page.locator('nav a[data-page="planner"]').click()
                page.locator('#goal').fill('Get 10 qualified leads')
                page.get_by_role('button',name='Generate weekly plan').click()
                expect(page.locator('.day-card')).to_have_count(7)
                page.locator('[data-action="draft-plan"]').first.click()
                expect(page.locator('#editor-body')).to_be_visible()
                assert 'Bright & Co' in page.locator('#editor-body').input_value()
                # Draft edits persist; approval locks to current revision and brand.
                page.locator('#editor-body').fill(page.locator('#editor-body').input_value()+'\nA useful, reviewed message.')
                page.locator('[data-action="save-asset"]').click()
                expect(page.locator('#dirty-label')).to_have_text('All changes saved')
                page.locator('[data-action="approve-asset"]').click()
                expect(page.locator('.asset-option .badge')).to_have_text('Approved')
                with page.expect_download() as downloaded:
                    page.get_by_role('link',name='Export approved CSV').click()
                exported=Path(directory)/'assets.csv'
                downloaded.value.save_as(exported)
                rows=list(csv.DictReader(io.StringIO(exported.read_text())))
                assert len(rows)==1 and 'reviewed message' in rows[0]['body']
                page.reload()
                assert 'reviewed message' in page.locator('#editor-body').input_value()
                expect(page.locator('.asset-option .badge')).to_have_text('Approved')
                # Changing the brand invalidates an earlier approval.
                page.locator('nav a[data-page="brand"]').click()
                page.locator('#voice').fill('Warm, clear, useful.')
                page.get_by_role('button',name='Save Brand Brain').click()
                expect(page.locator('#toast')).to_contain_text('Brand Brain saved')
                page.locator('nav a[data-page="studio"]').click()
                expect(page.locator('.asset-option .badge')).to_have_text('Needs review')
                page.locator('[data-action="approve-asset"]').click()
                expect(page.locator('.asset-option .badge')).to_have_text('Approved')
                # New independent asset, using a real dialog form.
                page.locator('[data-action="new-asset"]').click()
                page.locator('#modal #channel').select_option('Email')
                page.locator('#brief').fill('Invite founders to try our marketing workflow.')
                page.locator('#modal button[type="submit"]').click()
                expect(page.locator('#modal')).not_to_be_visible()
                expect(page.locator('.asset-option')).to_have_count(2)
                assert page.locator('#editor-body').input_value().startswith('Subject:')
                # Save and review a campaign.
                page.locator('nav a[data-page="campaigns"]').click()
                page.locator('[data-action="new-campaign"]').first.click()
                page.locator('#modal #name').fill('Founder launch')
                page.locator('#modal button[type="submit"]').click()
                expect(page.locator('#modal')).not_to_be_visible()
                page.locator('[data-action="review-campaign"]').click()
                expect(page.locator('.review-score')).to_contain_text('100')
                expect(page.locator('.checks .badge')).to_have_count(5)
                # CSV import recalculates actual metrics, no fixed dashboard numbers.
                page.locator('nav a[data-page="analytics"]').click()
                page.locator('[data-action="import-metrics"]').first.click()
                csv_text=f'date,channel,campaign,spend,impressions,clicks,leads,revenue\n{date.today().isoformat()},LinkedIn,Founder launch,50,2000,100,10,250\n'
                page.locator('#csv-file').set_input_files({'name':'metrics.csv','mimeType':'text/csv','buffer':csv_text.encode()})
                page.locator('#modal button[type="submit"]').click()
                expect(page.locator('#modal')).not_to_be_visible()
                expect(page.locator('.kpi-value').first).to_have_text('10')
                expect(page.locator('.kpi-value').nth(2)).to_have_text('$5.00')
                page.locator('[data-action="analyze"]').click()
                expect(page.locator('#toast')).to_contain_text('Analysis complete')
                # Chat saves both the prompt and the response.
                page.locator('nav a[data-page="ask"]').click()
                page.locator('#question').fill('Which channel is working?')
                page.locator('#chat-form button').click()
                expect(page.locator('.message.assistant')).to_have_count(1)
                expect(page.locator('.message.assistant')).to_contain_text('10 leads')
                page.reload()
                expect(page.locator('.message.user')).to_have_text('Which channel is working?')
                # Reject cross-site writes, directory traversal and non-JSON writes.
                assert page.request.post(base+'/api/brand',headers={'Origin':'https://untrusted.example'},data={}).status==403
                assert page.request.get(base+'/.data/cmo.sqlite3').status==404
                assert page.request.post(base+'/api/brand',data='name=evil',headers={'Content-Type':'text/plain'}).status==415
                # XSS-like user text stays text in the UI.
                page.locator('#question').fill('<img src=x onerror="alert(1)">')
                page.locator('#chat-form button').click()
                expect(page.locator('.message.user')).to_have_count(2)
                expect(page.locator('.message.user img')).to_have_count(0)
                # Capture desktop and mobile layouts. Check all pages for horizontal overflow.
                screenshot=Path('artifacts');screenshot.mkdir(exist_ok=True)
                page.locator('nav a[data-page="dashboard"]').click()
                expect(page.locator('#toast')).not_to_have_class(re.compile(r'\bshow\b'),timeout=10000)
                page.screenshot(path=str(screenshot/'overview-desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                for name in ['dashboard','brand','planner','studio','campaigns','analytics','ask']:
                    page.locator(f'nav a[data-page="{name}"]').click()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{name} overflows mobile viewport'
                page.screenshot(path=str(screenshot/'chat-mobile.png'),full_page=True)
                assert not errors, errors
                browser.close()
                print('PASS: persistent brand, 7-day plan → asset, editing, approval/export, brand-change re-review, email drafting, campaign review, CSV analytics, contextual chat, XSS rendering, API guards, 7 mobile pages; no console or runtime errors.')
        finally:
            server.shutdown()
            server.server_close()


if __name__=='__main__':
    run()
