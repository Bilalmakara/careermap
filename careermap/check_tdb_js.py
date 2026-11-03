import requests, sys

r = requests.get('https://www.tdb.org.tr/assets/dentists.service-ypo3CvWM.js', timeout=10)
print('Len:', len(r.text))
sys.stdout.buffer.write(r.text.encode('utf-8'))
