"""Explicit opt-in PR summary publication. Not used by the local CLI."""
import json
import re
import urllib.request


def publish(event, repository, token, body, opener=urllib.request.urlopen):
    """Create one comment per opted-in run; no comment update or deduplication."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('invalid repository')
    pr = event.get('pull_request', {})
    number = event.get('number')
    # Only same-repository PRs; never grant write credentials to fork code.
    if type(number) is not int or number < 1 or pr.get('head', {}).get('repo', {}).get('full_name') != repository:
        raise ValueError('comment publication requires a same-repository pull request event')
    if not token:
        raise ValueError('comment publication requires an explicit token')
    # Avoid notification mentions and raw model text in public comments.
    payload = json.dumps({'body':body}).encode('utf-8')
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repository}/issues/{number}/comments',
        data=payload, method='POST', headers={'Authorization':f'Bearer {token}',
        'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10',
        'Content-Type':'application/json'})
    with opener(request, timeout=20) as response:
        return json.load(response)['html_url']
