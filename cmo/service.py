import csv
import hashlib
import io
import json
import math
import re
import sqlite3
from datetime import date, timedelta
from urllib.parse import urlparse
from .agent import Agent

CHANNELS = ('LinkedIn', 'Email', 'Instagram', 'Blog', 'Landing page')


class InputError(ValueError):
    pass


def text(data, key, maximum=2000, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise InputError(f'{key.replace("_", " ")} must be {"non-empty text" if required else "text"} of at most {maximum} characters.')
    return value.strip()


def number(value, label, maximum=1e9, integer=False):
    try:
        if isinstance(value, bool):
            raise ValueError()
        n = float(value)
        if not math.isfinite(n) or n < 0 or n > maximum or (integer and not n.is_integer()):
            raise ValueError()
        return int(n) if integer else n
    except (ValueError, TypeError, OverflowError):
        raise InputError(f'{label} must be a nonnegative {"whole " if integer else ""}number up to {maximum:g}.') from None


def iso_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except (TypeError, ValueError):
        raise InputError('Use a valid date in YYYY-MM-DD format.') from None


class Service:
    def __init__(self, store):
        self.store = store
        self.agent = Agent(store)

    def analytics(self):
        rows = self.store.list('metric')
        today = date.today()
        start = today - timedelta(days=29)
        prev_start = start - timedelta(days=30)
        current = [r for r in rows if start.isoformat() <= r['date'] <= today.isoformat()]
        previous = [r for r in rows if prev_start.isoformat() <= r['date'] < start.isoformat()]

        def totals(group):
            result = {k: round(sum(r[k] for r in group), 2) for k in ('spend', 'impressions', 'clicks', 'leads', 'revenue')}
            result['ctr'] = round(100 * result['clicks'] / result['impressions'], 2) if result['impressions'] else None
            result['cpl'] = round(result['spend'] / result['leads'], 2) if result['leads'] else None
            result['roas'] = round(result['revenue'] / result['spend'], 2) if result['spend'] else None
            return result

        total = totals(current)
        prior = totals(previous)
        channels = [{'channel': name, **totals([r for r in current if r['channel'] == name])}
                    for name in sorted({r['channel'] for r in current})]
        observations = [f'{len(current)} metric rows in the last 30 days: {total["leads"]:g} leads from ${total["spend"]:,.2f} spend.'] if current else [
            'No performance data in the last 30 days. Import your channel metrics to see evidence-based insights.']
        recommendations = ['Use consistent tracking links and record qualified leads weekly.']
        if current:
            eligible = [c for c in channels if c['leads'] >= 5 and c['spend'] > 0]
            if eligible:
                best = min(eligible, key=lambda c: c['cpl'])
                observations.append(f'{best["channel"]} has the lowest observed cost per lead (${best["cpl"]:.2f}) among channels with at least 5 leads and nonzero spend.')
                recommendations.append(f'Test a small budget shift toward {best["channel"]}; confirm lead quality before scaling. This is observational, not causal.')
            else:
                recommendations.append('Collect at least 5 leads per paid channel before comparing acquisition costs.')
            if previous and prior['leads']:
                delta = round(100 * (total['leads'] - prior['leads']) / prior['leads'], 1)
                observations.append(f'Lead count changed {delta:+g}% versus the previous 30-day period.')
            else:
                observations.append('There is not enough prior-period data to calculate a lead trend.')
            if total['spend'] > self.store.brand()['monthly_budget']:
                recommendations.append('The last 30 days of spend exceeds your monthly budget. Review spend before adding campaigns.')
        series = []
        for i in range(6):
            lo = start + timedelta(days=i * 5)
            hi = lo + timedelta(days=4)
            series.append({'date': lo.isoformat(), 'leads': sum(r['leads'] for r in current if lo.isoformat() <= r['date'] <= hi.isoformat())})
        return {'period': {'start': start.isoformat(), 'end': today.isoformat()}, 'totals': total,
                'previous': prior, 'channels': channels, 'series': series, 'row_count': len(current),
                'observations': observations, 'recommendations': recommendations}

    def context(self):
        return {'brand': self.store.brand(), 'analytics': self.analytics(),
                'plans': self.store.list('plan')[:2], 'campaigns': self.store.list('campaign')[:5],
                'recent_messages': self.store.list('message')[:8][::-1]}

    def state(self):
        return {'brand': self.store.brand(), 'plans': self.store.list('plan'),
                'assets': self.store.list('asset'), 'campaigns': self.store.list('campaign'),
                'metrics': self.store.list('metric'), 'messages': self.store.list('message')[::-1],
                'analytics': self.analytics(), 'usage': self.agent.usage()}

    def save_brand(self, data):
        brand = {key: text(data, key, maxlen, required) for key, maxlen, required in (
            ('name', 100, True), ('product', 500, True), ('audience', 500, True),
            ('positioning', 2000, True), ('voice', 1000, True), ('cta', 300, True),
            ('website', 500, False), ('banned_words', 1000, False))}
        if brand['website']:
            u = urlparse(brand['website'])
            if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
                raise InputError('Website must be a public HTTP(S) URL without credentials.')
        brand['monthly_budget'] = number(data.get('monthly_budget'), 'Monthly budget', 1e7)
        return self.store.save_brand(brand)

    def brand_check(self, body, brand=None):
        b = brand or self.store.brand()
        issues = []
        for word in b['banned_words'].split(','):
            word = word.strip()
            if word and re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', body, re.I):
                issues.append(f'Remove restricted phrase: {word}')
        if b['cta'].lower() not in body.lower():
            issues.append('Include the saved brand call to action.')
        if b['name'].lower() not in body.lower():
            issues.append('Mention the brand name.')
        if len(body.strip()) < 50:
            issues.append('Add enough context for a useful asset (at least 50 characters).')
        return {'issues': issues, 'score': max(0, 100 - 25 * len(issues)),
                'note': 'Rule-based check of name, CTA, restricted phrases and length. Human review is still required.'}

    def create_plan(self, data):
        goal = text(data, 'goal', 500)
        start = iso_date(data.get('week_start'))
        result = self.agent.run('plan', {'goal': goal, 'week_start': start.isoformat()}, self.context())
        items = [{'title': x['title'], 'channel': x['channel'], 'brief': x['brief'],
                  'date': (start + timedelta(days=i)).isoformat()} for i, x in enumerate(result['items'])]
        return self.store.create('plan', {'goal': goal, 'week_start': start.isoformat(), 'items': items, 'source': self.agent.mode})

    def create_asset(self, data):
        channel = text(data, 'channel', 50)
        if channel not in CHANNELS:
            raise InputError('Choose a supported channel.')
        brief = text(data, 'brief', 3000)
        title = text(data, 'title', 200, False)
        plan_id, plan_index = data.get('plan_id'), data.get('plan_index')
        if plan_id is not None:
            if type(plan_id) is not int or plan_id < 1:
                raise InputError('Plan ID must be a positive integer.')
            plan = self.store.get('plan', plan_id)
            if not plan or type(plan_index) is not int or not 0 <= plan_index < 7:
                raise InputError('Plan item does not exist.')
            existing = [a for a in self.store.list('asset') if a.get('plan_id') == plan_id and a.get('plan_index') == plan_index]
            if existing:
                return existing[0]
        result = self.agent.run('asset', {'channel': channel, 'brief': brief, 'title': title}, self.context())
        try:
            return self.store.create('asset', {'title': result['title'], 'body': result['body'],
            'channel': channel, 'brief': brief, 'status': 'Draft', 'source': self.agent.mode,
                'plan_id': plan_id, 'plan_index': plan_index, 'approved_fingerprint': None})
        except sqlite3.IntegrityError:
            # A second tab may have drafted the same plan item during generation.
            existing = [a for a in self.store.list('asset') if a.get('plan_id') == plan_id and a.get('plan_index') == plan_index]
            if existing:
                return existing[0]
            raise

    def require(self, kind, record_id):
        record = self.store.get(kind, record_id)
        if record is None:
            raise InputError('Record not found.')
        return record

    def fingerprint(self, brand=None):
        return hashlib.sha256(json.dumps(brand or self.store.brand(), sort_keys=True).encode()).hexdigest()

    def asset_action(self, record_id, action, data):
        a = self.require('asset', record_id)
        revision = data.get('revision')
        if type(revision) is not int or revision != a['revision']:
            raise InputError('This asset changed. Reload before saving or approving.')
        if action == 'save':
            title, body = text(data, 'title', 200), text(data, 'body', 16000)
            if a['title'] != title or a['body'] != body:
                a.update(title=title, body=body, status='Draft', approved_fingerprint=None)
        elif action == 'approve':
            brand = self.store.brand()
            check = self.brand_check(a['body'], brand)
            if check['issues']:
                raise InputError('Approval blocked: ' + '; '.join(check['issues']))
            a.update(status='Approved', approved_fingerprint=self.fingerprint(brand))
        elif action == 'variation':
            result = self.agent.run('asset', {'title': a['title'], 'channel': a['channel'], 'brief': a['brief'],
                'instruction': text(data, 'instruction', 1000)}, self.context())
            a.update(title=result['title'], body=result['body'], status='Draft', source=self.agent.mode, approved_fingerprint=None)
        else:
            raise InputError('Unknown asset action.')
        return self.store.update('asset', record_id, a, revision)

    def create_campaign(self, data):
        campaign = {key: text(data, key, limit) for key, limit in (
            ('name', 150), ('goal', 1000), ('audience', 500), ('offer', 2000), ('channel', 50), ('cta', 300))}
        if campaign['channel'] not in CHANNELS:
            raise InputError('Choose a supported channel.')
        campaign['budget'] = number(data.get('budget'), 'Budget', 1e7)
        campaign['deadline'] = iso_date(data.get('deadline')).isoformat()
        campaign.update(status='Draft', review=None)
        return self.store.create('campaign', campaign)

    def review_campaign(self, record_id):
        c = self.require('campaign', record_id)
        result = self.agent.run('review', c, self.context())
        b = self.store.brand()
        checks = [
            {'name': 'Audience match', 'passed': c['audience'].casefold() == b['audience'].casefold(),
             'detail': 'Audience matches the saved Brand Brain exactly.'},
            {'name': 'Clear CTA', 'passed': len(c['cta']) >= 10, 'detail': 'CTA contains at least 10 characters.'},
            {'name': 'Within budget', 'passed': c['budget'] <= b['monthly_budget'], 'detail': 'Campaign budget is within the saved monthly limit.'},
            {'name': 'Future deadline', 'passed': c['deadline'] >= date.today().isoformat(), 'detail': 'Deadline has not passed.'},
            {'name': 'Restricted phrases', 'passed': not any(x.startswith('Remove restricted') for x in self.brand_check(c['offer'])['issues']),
             'detail': 'Offer does not contain a restricted brand phrase.'},
        ]
        c.update(review={'summary': result['summary'], 'recommendations': result['recommendations'], 'checks': checks, 'score': sum(20 for x in checks if x['passed']),
                         'source': self.agent.mode}, status='Reviewed')
        return self.store.update('campaign', record_id, c, c['revision'])

    def import_metrics(self, data):
        raw = text(data, 'csv', 200000)
        reader = csv.DictReader(io.StringIO(raw))
        fields = ['date', 'channel', 'campaign', 'spend', 'impressions', 'clicks', 'leads', 'revenue']
        if reader.fieldnames != fields:
            raise InputError('CSV headers must be exactly: ' + ','.join(fields))
        prepared, keys = [], set()
        for index, row in enumerate(reader, 2):
            if index > 1001:
                raise InputError('Import at most 1,000 rows at a time.')
            if None in row or any(v is None for v in row.values()):
                raise InputError(f'Row {index}: incorrect number of columns.')
            try:
                r = {'date': iso_date(row['date']).isoformat(), 'channel': text(row, 'channel', 50),
                     'campaign': text(row, 'campaign', 150)}
                if r['date'] > date.today().isoformat():
                    raise InputError('Performance dates cannot be in the future.')
                if r['channel'] not in CHANNELS:
                    raise InputError('Unsupported channel.')
                for k in fields[3:]:
                    r[k] = number(row[k], k, integer=k in ('impressions', 'clicks', 'leads'))
                if r['clicks'] > r['impressions'] or r['leads'] > r['clicks']:
                    raise InputError('Expected leads ≤ clicks ≤ impressions.')
                key = (r['date'], r['channel'], r['campaign'])
                if key in keys:
                    raise InputError('Duplicate date/channel/campaign in this file.')
                keys.add(key)
                prepared.append(r)
            except InputError as error:
                raise InputError(f'Row {index}: {error}') from None
        if not prepared:
            raise InputError('CSV contains no data rows.')
        # Validate the entire file first, then upsert in one transaction.
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            from .store import now
            existing = {(r['date'], r['channel'], r['campaign']): r for r in self.store.list('metric')}
            added, updated = 0, 0
            for r in prepared:
                old = existing.get((r['date'], r['channel'], r['campaign']))
                if old:
                    db.execute('UPDATE records SET data=?,revision=revision+1,updated_at=? WHERE id=?', (json.dumps(r), now(), old['id']))
                    updated += 1
                else:
                    db.execute('INSERT INTO records(kind,data,created_at,updated_at) VALUES (?,?,?,?)', ('metric', json.dumps(r), now(), now()))
                    added += 1
        return {'added': added, 'updated': updated}

    def chat(self, data):
        q = text(data, 'question', 2000)
        result = self.agent.run('chat', {'question': q}, self.context())
        return self.store.create('message', {'question': q, 'answer': result['answer'], 'source': self.agent.mode})

    def insights(self):
        return {**self.agent.run('insights', {}, self.context()), 'source': self.agent.mode}

    def export(self, kind):
        if kind == 'assets':
            rows = [a for a in self.store.list('asset') if a['status'] == 'Approved' and a['approved_fingerprint'] == self.fingerprint()]
            fields = ['title', 'channel', 'body', 'status']
        elif kind == 'metrics':
            rows, fields = self.store.list('metric'), ['date', 'channel', 'campaign', 'spend', 'impressions', 'clicks', 'leads', 'revenue']
        else:
            raise InputError('Unknown export type.')
        out = io.StringIO(newline='')
        writer = csv.writer(out)
        writer.writerow(fields)
        for row in rows:
            values = [row.get(k, '') for k in fields]
            # Prevent formulas executing when CSV exports are opened in spreadsheets.
            writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
        return out.getvalue()
