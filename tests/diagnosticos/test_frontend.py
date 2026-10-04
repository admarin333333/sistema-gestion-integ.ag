import requests

r = requests.post('http://127.0.0.1:8010/api/auth/login', json={'usuario':'admin','password':'admin123'})
token = r.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

r2 = requests.get('http://localhost:5173/cliente-ficha/22', headers={'Authorization': 'Bearer ' + token})
print('Status:', r2.status_code)
print('Length:', len(r2.text))
print('Has root div:', 'id="root"' in r2.text)
print('Has React root:', 'data-reactroot' in r2.text)
print('First 500 chars:', r2.text[:500])