#!/usr/bin/env python3
"""Run: python3 server.py. Standard library only; one trusted local workspace."""
import argparse
import json
import logging
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from cmo.agent import AgentError
from cmo.service import InputError, Service
from cmo.store import Store

ROOT = Path(__file__).resolve().parent


def handler_for(service):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'CMO/1.0'

        def log_message(self, fmt, *args):
            # Never log query strings, headers, payloads, or provider errors.
            logging.info('%s %s', self.command, self.path.split('?')[0])

        def send(self, body, status=200, content_type='application/json; charset=utf-8', filename=None):
            if content_type.startswith('application/json'):
                body = json.dumps(body, ensure_ascii=False).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def dispatch(self):
            try:
                # Local bind + Host/Origin checks protect the unauthenticated local API.
                host = self.headers.get('Host', '')
                if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
                    return self.send({'error': 'Unrecognized host. Use the local server address.'}, 403)
                origin = self.headers.get('Origin')
                if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
                    return self.send({'error': 'Cross-origin requests are not allowed.'}, 403)
                path = urlparse(self.path).path
                if self.command == 'GET':
                    return self.get(path)
                if self.command != 'POST' or not path.startswith('/api/'):
                    return self.send({'error': 'Not found.'}, 404)
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    return self.send({'error': 'Use application/json.'}, 415)
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                except ValueError:
                    return self.send({'error': 'Invalid content length.'}, 400)
                if length < 1 or length > 300000:
                    return self.send({'error': 'Request body must be between 1 and 300,000 bytes.'}, 413)
                self.connection.settimeout(15)
                try:
                    data = json.loads(self.rfile.read(length))
                except (json.JSONDecodeError, UnicodeError):
                    raise InputError('Invalid JSON body.')
                if not isinstance(data, dict):
                    raise InputError('JSON body must be an object.')
                return self.post(path, data)
            except InputError as error:
                self.send({'error': str(error)}, 400)
            except AgentError as error:
                self.send({'error': str(error)}, 502)
            except ValueError as error:
                self.send({'error': 'Record conflict. Reload and try again.'}, 409)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                logging.exception('Unexpected application error')
                self.send({'error': 'Unexpected server error. Check the server log.'}, 500)

        def get(self, path):
            if path == '/api/health':
                return self.send({'status': 'ok', 'mode': service.agent.mode})
            if path == '/api/state':
                state = service.state()
                for a in state['assets']:
                    a['brand_check'] = service.brand_check(a['body'])
                    a['needs_review'] = a['status'] == 'Approved' and a['approved_fingerprint'] != service.fingerprint()
                return self.send(state)
            if path in ('/api/export/assets', '/api/export/metrics'):
                kind = path.rsplit('/', 1)[1]
                return self.send(service.export(kind), content_type='text/csv; charset=utf-8', filename=f'cmo-{kind}.csv')
            if path == '/api/export/workspace':
                return self.send(service.state(), filename='cmo-workspace-backup.json')
            static = {'/': (ROOT / 'index.html', 'text/html; charset=utf-8'),
                      '/index.html': (ROOT / 'index.html', 'text/html; charset=utf-8'),
                      '/web/app.js': (ROOT / 'web/app.js', 'text/javascript; charset=utf-8'),
                      '/web/style.css': (ROOT / 'web/style.css', 'text/css; charset=utf-8')}
            if path in static:
                file, mime = static[path]
                return self.send(file.read_bytes(), content_type=mime)
            return self.send({'error': 'Not found.'}, 404)

        def post(self, path, data):
            routes = {'/api/brand': service.save_brand, '/api/plans': service.create_plan,
                      '/api/assets': service.create_asset, '/api/campaigns': service.create_campaign,
                      '/api/metrics/import': service.import_metrics, '/api/chat': service.chat,
                      '/api/insights': lambda _: service.insights()}
            if path in routes:
                return self.send(routes[path](data))
            match = re.fullmatch(r'/api/assets/(\d+)/(save|approve|variation)', path)
            if match:
                return self.send(service.asset_action(int(match[1]), match[2], data))
            match = re.fullmatch(r'/api/campaigns/(\d+)/review', path)
            if match:
                return self.send(service.review_campaign(int(match[1])))
            return self.send({'error': 'Not found.'}, 404)

        do_GET = dispatch
        do_POST = dispatch
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--db', default=os.environ.get('CMO_DB_PATH', str(ROOT / '.data/cmo.sqlite3')))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    service = Service(Store(args.db))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(service))
    server.daemon_threads = True
    print(f'CMO AI running on local port {args.port}; generation mode: {service.agent.mode}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
