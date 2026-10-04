import requests
import re

r = requests.post('http://127.0.0.1:8010/api/auth/login', json={'usuario':'admin','password':'admin123'})
token = r.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

r2 = requests.get('http://localhost:5173/cliente-ficha/22', headers={'Authorization': 'Bearer ' + token})
print('Status:', r2.status_code)
print('Length:', len(r2.text))

match = re.search(r'<div id="root">(.*?)</div>', r2.text, re.DOTALL)
if match:
    print('Root content:', match.group(1)[:1000])
else:
    print('No root div found')
    print('First 2000 chars:', r2.text[:2000])