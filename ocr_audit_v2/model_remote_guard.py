"""Inference deadline guard, independent of the frontend and its SSH tunnel.
Provider identity/auth helpers are unchanged from the verified training guard.
Only provider-injected credentials for this Pod are read; no account key is sent.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, os, subprocess, time
import urllib.request, urllib.error

def provider_environment(expected, environ=None, init_path=Path('/proc/1/environ')):
    """Recover provider-injected identity lost by SSH; never serialize secrets.

    The launch request must not inject an account key. Only the container's
    original environment is eligible as a credential fallback.
    """
    current=dict(os.environ if environ is None else environ)
    initial={}
    if init_path.exists():
        for item in init_path.read_bytes().split(b'\0'):
            if b'=' in item:
                name,value=item.split(b'=',1)
                if name in (b'RUNPOD_POD_ID',b'RUNPOD_API_KEY',b'RUNPOD_APIKEY',b'APIKEY'):
                    initial[name.decode()]=value.decode()
    identities=[e['RUNPOD_POD_ID'] for e in (current,initial) if e.get('RUNPOD_POD_ID')]
    assert identities and all(p==expected for p in identities), 'Provider identity absent or conflicting'
    current['RUNPOD_POD_ID']=expected
    for name in ('RUNPOD_API_KEY','RUNPOD_APIKEY','APIKEY'):
        if initial.get(name):
            assert not current.get(name) or current[name]==initial[name], 'Credential sources conflict'
            current[name]=initial[name]
    # Legacy runpodctl v1.14 uses Viper AutomaticEnv(apiKey), i.e. APIKEY.
    provider_key=initial.get('RUNPOD_API_KEY') or initial.get('RUNPOD_APIKEY')
    if provider_key and not current.get('APIKEY'):current['APIKEY']=provider_key
    return current

def commands(binary='runpodctl'):
    # Supporting both published CLI generations without exposing credential files.
    for get,stop in [(['pod','get'],['pod','stop']),(['get','pod'],['stop','pod'])]:
        p=subprocess.run([binary,*stop,'--help'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        if p.returncode==0:return [binary,*get],[binary,*stop]
    raise RuntimeError('No supported runpodctl stop command')

def own_pod_read(pod_id, environment, opener=urllib.request.urlopen):
    """Check only the assigned Pod. Legacy CLI get lists every account Pod.

    Use the provider-injected key in a header, never in a URL or diagnostics.
    No account-wide query and no credential fallback with broader permissions.
    """
    key=environment.get('RUNPOD_API_KEY') or environment.get('RUNPOD_APIKEY') or environment.get('APIKEY')
    report={'pod_id':pod_id,'provider_key_available':bool(key),'passed':False,
            'scope':'pod(input: {podId})','remote_stop_verified':False}
    if not key:return report
    query='query OwnPod($id: String!) { pod(input: {podId: $id}) { id desiredStatus } }'
    request=urllib.request.Request('https://api.runpod.io/graphql',
        data=json.dumps({'query':query,'variables':{'id':pod_id}}).encode(),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json',
                 'User-Agent':'RunPod-CLI/1.14.15'},method='POST')
    try:
        with opener(request,timeout=20) as response:
            report['http_status']=response.status
            value=json.load(response)
        if value.get('errors'):
            message=json.dumps(value['errors']).lower()
            report['error_classes']={s:s in message for s in ('unauthorized','forbidden','not found','cannot query','variable')}
        else:
            own=(value.get('data') or {}).get('pod') or {}
            report['identity_matches']=own.get('id')==pod_id
            report['desired_status']=own.get('desiredStatus')
            report['passed']=report['identity_matches'] and own.get('desiredStatus')=='RUNNING'
    except urllib.error.HTTPError as error:report['http_status']=error.code
    except Exception as error:report['error_type']=type(error).__name__
    return report

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pod', required=True)
    ap.add_argument('--deadline', required=True)
    args = ap.parse_args()
    deadline = datetime.fromisoformat(args.deadline).timestamp()
    if not 0 < deadline - time.time() <= 3 * 3600:
        raise ValueError('Deadline must be within three hours')
    env = provider_environment(args.pod)
    _, stop = commands()
    own = own_pod_read(args.pod, env)
    if not own['passed']:
        raise RuntimeError('Own-Pod authorization failed')
    Path('/root/model_guard_ready.json').write_text(json.dumps({
        'pod_id': args.pod, 'deadline': args.deadline, 'own_pod_authorization': True,
        'pid': os.getpid(), 'stop_verified': False}), encoding='utf-8')
    while time.time() < deadline:
        time.sleep(min(15, max(0, deadline - time.time())))
    # Continue retrying if the provider is temporarily unavailable; don't depend
    # on a foreground browser or a living HF container to retry stopping.
    while True:
        try:
            result = subprocess.run([*stop, args.pod], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
            Path('/root/model_guard_stop.json').write_text(json.dumps({
                'utc': datetime.now(timezone.utc).isoformat(),
                'returncode': result.returncode}), encoding='utf-8')
        except (OSError, subprocess.TimeoutExpired):
            pass
        time.sleep(15)


if __name__ == '__main__':
    main()
