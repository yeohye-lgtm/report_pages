"""Verify CDN serves the expected build, not merely an older HTTP 200 page."""
import json
import os
import time
from urllib.request import Request,urlopen
from urllib.parse import urljoin

base=os.environ['PAGES_URL'].rstrip('/')+'/'
sha=os.environ['GITHUB_SHA']
last_error=''
for attempt in range(10):
    try:
        def get(name):
            url=urljoin(base,'ai-risk/'+name)+'?build='+sha+'&attempt='+str(attempt)
            req=Request(url,headers={'Cache-Control':'no-cache','User-Agent':'report-pages-deployment-check'})
            with urlopen(req,timeout=20) as response:
                assert response.status==200
                return response.read().decode('utf-8')
        page=get('latest.html');data=json.loads(get('latest.json'))
        assert data.get('ui_version')=='2.0.0','JSON UI version mismatch'
        assert data.get('build_sha')==sha,'JSON build is stale'
        assert 'data-layout-revision="2.0.0"' in page,'HTML template mismatch'
        assert 'name="report-build"' in page and sha in page,'HTML build is stale'
        assert page.count('class="axis-row"')==5,'Missing five-axis board'
        assert 'risk_score' not in page,'Old score UI detected'
        print('LIVE VERIFIED',urljoin(base,'ai-risk/latest.html'),'build',sha,'data date',data['date'],'state',data['assessment_state'])
        break
    except Exception as error:
        last_error=type(error).__name__+': '+str(error)
        if attempt<9: time.sleep(12)
else:
    raise SystemExit('Public deployment verification failed: '+last_error)
