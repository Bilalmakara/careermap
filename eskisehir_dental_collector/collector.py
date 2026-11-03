#!/usr/bin/env python3
"""Eskişehir diş klinikleri araştırma aracı. E-posta göndermez."""
import argparse, csv, json, os, re, sys, time, logging, unicodedata
from datetime import datetime
from urllib.parse import urlparse, urljoin
from pathlib import Path
from difflib import SequenceMatcher
import requests
from bs4 import BeautifulSoup
from artifact_tool import Workbook, SpreadsheetFile

OFFICIAL = {
 'poliklinik': 'https://eskisehirism.saglik.gov.tr/TR-39645/ozel-agiz-ve-dis-sagligi-poliklinikleri.html',
 'muayenehane': 'https://eskisehirism.saglik.gov.tr/TR-39637/dis-hekimi-muayenehaneleri.html',
}
QUERIES = ['diş kliniği Eskişehir', 'özel ağız ve diş sağlığı polikliniği Eskişehir', 'diş hekimi muayenehanesi Eskişehir',
 'diş kliniği Tepebaşı Eskişehir', 'diş kliniği Odunpazarı Eskişehir', 'diş hekimi Sivrihisar Eskişehir',
 'diş hekimi Çifteler Eskişehir', 'diş hekimi Alpu Eskişehir', 'diş hekimi Mahmudiye Eskişehir',
 'diş hekimi İnönü Eskişehir', 'diş hekimi Seyitgazi Eskişehir', 'diş hekimi Mihalıççık Eskişehir',
 'diş hekimi Sarıcakaya Eskişehir', 'diş hekimi Mihalgazi Eskişehir', 'diş hekimi Beylikova Eskişehir',
 'diş hekimi Günyüzü Eskişehir', 'diş hekimi Han Eskişehir']
FIELDS = ['Klinik Adı','Kurum Türü','İlçe','Adres','Telefon','Kurumsal E-posta','Web Sitesi','E-posta Kaynak URL','Kaynak URL(ler)','Kaynak Türü','Google Place ID','Google İşletme Durumu','Veri Durumu','Son Kontrol','Başvuru Durumu']
EMAIL_RE = re.compile(r'(?<![\w.+-])([\w.+-]+@[\w.-]+\.[a-zA-Z]{2,})(?![\w.-])')
PHONE_RE = re.compile(r'(?:\+90|0)?\s*\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{2}[\s.-]*\d{2}')
BAD_DOMAINS = {'facebook.com','instagram.com','linkedin.com','google.com','maps.google.com','youtube.com','x.com','twitter.com','wa.me','whatsapp.com'}
HEADERS={'User-Agent':'DentalClinicResearchBot/1.0 (public contact lookup; respectful rate limits)'}
logger=logging.getLogger('dental')

def clean(s): return ' '.join(str(s or '').split()).strip()
def canon(s):
 s=clean(s).lower().translate(str.maketrans('çğıöşü','cgiosu'))
 s=unicodedata.normalize('NFKD', s)
 s=re.sub(r'\b(ozel|agiz|ve|dis|sagligi|poliklinigi|poliklinik|klinik|muayenehanesi|dt|dr|dishekimi)\b',' ',s)
 return re.sub(r'[^a-z0-9]','',s)
def district(text):
 t=clean(text).lower()
 for d in ['Tepebaşı','Odunpazarı','Sivrihisar','Çifteler','Alpu','Mahmudiye','İnönü','Seyitgazi','Mihalıççık','Sarıcakaya','Mihalgazi','Beylikova','Günyüzü','Han']:
  if d.lower() in t: return d
 return ''
def domain(u):
 try: return urlparse(u).hostname.lower().removeprefix('www.')
 except: return ''
def allowed_website(url):
 p=urlparse(url)
 return p.scheme in ('http','https') and p.hostname and not any(p.hostname==d or p.hostname.endswith('.'+d) for d in BAD_DOMAINS)

def fetch(session,url):
 try:
  r=session.get(url,headers=HEADERS,timeout=18,allow_redirects=True)
  r.raise_for_status()
  if 'html' not in r.headers.get('content-type','text/html').lower(): return None
  return BeautifulSoup(r.text,'html.parser')
 except requests.RequestException as e:
  logger.warning('Sayfa alınamadı: %s (%s)',url,e); return None

def record(name,typ,source,address='',citydistrict=''):
 return {'Klinik Adı':clean(name),'Kurum Türü':typ,'İlçe':citydistrict or district(address),'Adres':clean(address),'Telefon':'','Kurumsal E-posta':'','Web Sitesi':'',
 'E-posta Kaynak URL':'','Kaynak URL(ler)':source,'Kaynak Türü':'İl Sağlık Müdürlüğü','Google Place ID':'','Google İşletme Durumu':'','Veri Durumu':'Kontrol edilmeli','Son Kontrol':datetime.now().strftime('%Y-%m-%d'),'Başvuru Durumu':'Başvurulmadı'}

def official_records(session):
 result=[]
 for typ,url in OFFICIAL.items():
  soup=fetch(session,url)
  if not soup: continue
  tables=soup.select('table')
  seen=set()
  for table in tables:
   rows=table.select('tr')
   if len(rows)<2: continue
   header=clean(rows[0].get_text(' ',strip=True)).upper()
   if not any(k in header for k in ['KURULUŞ','HEKİM ADI','POLİKLİNİK','ADI SOYADI']): continue
   for tr in rows[1:]:
    cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
    if len(cells)<2 or not cells[0]: continue
    name=cells[0]
    if len(name)<5 or canon(name) in seen: continue
    seen.add(canon(name))
    addr=cells[-1]
    result.append(record(name,'Özel poliklinik' if typ=='poliklinik' else 'Bireysel muayenehane',url,addr,district(addr)))
  logger.info('Resmî kaynak %-15s -> %d kayıt',typ,len(seen))
 return result

def places_records(session,key,queries,max_queries=0):
 result=[]
 for q in (queries[:max_queries] if max_queries else queries):
  token=None
  for page in range(3):
   payload={'textQuery':q,'languageCode':'tr','regionCode':'TR','pageSize':20}
   if token: payload['pageToken']=token
   headers={'X-Goog-Api-Key':key,'X-Goog-FieldMask':'places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.businessStatus,nextPageToken','Content-Type':'application/json'}
   try:
    res=session.post('https://places.googleapis.com/v1/places:searchText',json=payload,headers=headers,timeout=30)
    if res.status_code!=200:
     logger.error('Google Places %s: %s',res.status_code,res.text[:300]); break
    data=res.json()
   except (requests.RequestException,ValueError) as exc:
    logger.error('Places hatası: %s',exc); break
   for p in data.get('places',[]):
    address=clean(p.get('formattedAddress'))
    if 'eskişehir' not in address.lower() and 'eskisehir' not in address.lower(): continue
    name=clean(p.get('displayName',{}).get('text'))
    if not name: continue
    r=record(name,'Google Places: kontrol edilmeli','https://www.google.com/maps/place/?q=place_id:'+p.get('id',''),address)
    r.update({'Telefon':clean(p.get('nationalPhoneNumber')),'Web Sitesi':p.get('websiteUri','') if allowed_website(p.get('websiteUri','')) else '',
       'Google Place ID':p.get('id',''),'Google İşletme Durumu':p.get('businessStatus',''),'Kaynak Türü':'Google Places'})
    result.append(r)
   token=data.get('nextPageToken')
   if not token: break
   time.sleep(2)
  logger.info('Places sorgusu tamamlandı: %s',q)
  time.sleep(.4)
 return result

def is_same(a,b):
 if a['Google Place ID'] and b['Google Place ID'] and a['Google Place ID']==b['Google Place ID']: return True
 # Different branches at different addresses must NOT be collapsed.
 ca,cb=canon(a['Klinik Adı']),canon(b['Klinik Adı'])
 if not ca or not cb: return False
 ratio=SequenceMatcher(None,ca,cb).ratio()
 aaddr=canon(a['Adres']); baddr=canon(b['Adres'])
 if aaddr and baddr and len(aaddr)>12 and len(baddr)>12:
  ar=SequenceMatcher(None,aaddr,baddr).ratio()
  if ar<.62: return False
 if a['İlçe'] and b['İlçe'] and a['İlçe']!=b['İlçe']: return False
 if a['Telefon'] and b['Telefon'] and re.sub(r'\D','',a['Telefon'])==re.sub(r'\D','',b['Telefon']) and ratio>.83: return True
 return ratio>.95 and (not aaddr or not baddr or SequenceMatcher(None,aaddr,baddr).ratio()>.70)

def merge(rows):
 combined=[]
 for row in rows:
  found=next((x for x in combined if is_same(x,row)),None)
  if not found: combined.append(dict(row));continue
  for k in ['Telefon','Web Sitesi','Google Place ID','Google İşletme Durumu','Adres','İlçe']:
   if not found[k] and row[k]: found[k]=row[k]
  if row['Kaynak URL(ler)'] not in found['Kaynak URL(ler)']: found['Kaynak URL(ler)']+=' | '+row['Kaynak URL(ler)']
  if row['Kaynak Türü'] not in found['Kaynak Türü']: found['Kaynak Türü']+=' + '+row['Kaynak Türü']
  if found['Kurum Türü'].startswith('Google') and not row['Kurum Türü'].startswith('Google'): found['Kurum Türü']=row['Kurum Türü']
 return combined

def scrape_email(session,website,delay=1.0):
 if not allowed_website(website):return ('','')
 home=website.rstrip('/')+'/'; visited=set(); paths=['','iletisim','contact','kariyer','career','hakkimizda']
 for path in paths:
  url=urljoin(home,path)
  if url in visited:continue
  visited.add(url)
  soup=fetch(session,url)
  if soup:
   if domain(url)!=domain(website):continue
   emails=[]
   for link in soup.select('a[href^="mailto:"]'):
    emails+=EMAIL_RE.findall(link.get('href',''))
   emails+=EMAIL_RE.findall(soup.get_text(' ',strip=True))
   emails+=EMAIL_RE.findall(str(soup))
   filtered=[]
   for mail in emails:
    mail=mail.lower().rstrip('.,;:')
    if any(t in mail for t in ['example.com','sentry.io','wixpress.com','cloudflare.com','schema.org','wordpress.org']):continue
    if mail not in filtered:filtered.append(mail)
   if filtered:
    filtered.sort(key=lambda x:(not x.startswith(('ik@','kariyer@','hr@','insankaynaklari@','info@','iletisim@')),domain(website) not in x))
    return filtered[0],url
  time.sleep(delay)
 return ('','')

def export(rows,out):
 wb=Workbook.create(); sh=wb.worksheets.add('Klinikler')
 sh.get_range_by_indexes(0,0,1,len(FIELDS)).values=[FIELDS]
 if rows:
  matrix=[[str(row.get(f,'') or '') for f in FIELDS] for row in rows]
  sh.get_range_by_indexes(1,0,len(matrix),len(FIELDS)).values=matrix
 sh.get_range_by_indexes(0,0,1,len(FIELDS)).format={'fill':'#183153','font':{'bold':True,'color':'#FFFFFF'},'row_height':31}
 sh.freeze_panes.freeze_rows(1)
 for col in range(len(FIELDS)):
  sh.get_range_by_indexes(0,col,max(2,len(rows)+1),1).format.column_width=29 if col in [0,3,5,6,7,8] else 19
 sh.get_range_by_indexes(0,0,max(2,len(rows)+1),len(FIELDS)).format.row_height=23
 meta=wb.worksheets.add('Bilgi')
 meta.get_range('A1:B7').values=[['Alan','Açıklama'],['Üretilme',datetime.now().strftime('%Y-%m-%d %H:%M')],['Kayıt sayısı',len(rows)],['Resmî liste','2024/2025 tarihli; güncel faaliyeti garanti etmez'],['Google Places','Kullanım ve saklama şartlarını kontrol edin'],['E-posta','Yalnızca kliniğin sitesinde açıkça yayımlanmış'],['Kontrol','Telefon ve e-posta sahibi doğrulanmadan başvuru göndermeyin']]
 meta.get_range('A1:B1').format={'fill':'#183153','font':{'bold':True,'color':'#FFFFFF'}}
 meta.get_range('A:A').format.column_width=27;meta.get_range('B:B').format.column_width=76
 SpreadsheetFile.export_xlsx(wb).save(str(out))

def main():
 parser=argparse.ArgumentParser(description='Eskişehir özel diş klinikleri ve muayenehane iletişim araştırması')
 parser.add_argument('--output',default='eskisehir_dis_klinikleri.xlsx')
 parser.add_argument('--places',action='store_true',help='GOOGLE_PLACES_API_KEY ile Places aramasını aç')
 parser.add_argument('--emails',action='store_true',help='Bulunan web sitelerinden yayımlanmış e-postaları araştır')
 parser.add_argument('--max-queries',type=int,default=0,help='Places sorgu limiti (0=tümü)')
 parser.add_argument('--delay',type=float,default=1.2,help='Web site istekleri arasında saniye')
 parser.add_argument('--input-csv',help='Ek kaynak CSV (Klinik Adı,Adres,Telefon,Web Sitesi...)')
 args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
 s=requests.Session();rows=official_records(s)
 if args.input_csv:
  with open(args.input_csv,encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f):
    if not r.get('Klinik Adı'):continue
    item=record(r['Klinik Adı'],r.get('Kurum Türü','Ek kaynak'),r.get('Kaynak URL(ler)',args.input_csv),r.get('Adres',''))
    for k in FIELDS:
     if k in r and r[k]:item[k]=r[k]
    rows.append(item)
 if args.places:
  key=os.getenv('GOOGLE_PLACES_API_KEY','')
  if not key:logger.error('GOOGLE_PLACES_API_KEY bulunamadı.');sys.exit(2)
  rows+=places_records(s,key,QUERIES,args.max_queries)
 rows=merge(rows)
 if not rows:
  logger.error('Hiç kayıt bulunamadı. Kaynak erişimini ve internet bağlantısını kontrol edin. Boş Excel üretilmedi.')
  sys.exit(3)
 if args.emails:
  sites={}
  for idx,r in enumerate(rows):
   site=r['Web Sitesi']
   if not site:continue
   d=domain(site)
   if d not in sites:sites[d]=scrape_email(s,site,max(.5,args.delay))
   email,url=sites[d]
   if email:r['Kurumsal E-posta'],r['E-posta Kaynak URL']=email,url
   logger.info('Web inceleme %d/%d: %s',idx+1,len(rows),site)
 for r in rows:
  r['Veri Durumu']='E-posta bulundu (doğrulama gerekli)' if r['Kurumsal E-posta'] else 'E-posta bulunamadı / kontrol edilmeli'
 rows.sort(key=lambda r:(r['İlçe'],r['Klinik Adı'].lower()))
 out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
 export(rows,out)
 logger.info('TAMAMLANDI | %d tekil kayıt | %d e-posta | %s',len(rows),sum(bool(r['Kurumsal E-posta']) for r in rows),out)

if __name__=='__main__':main()
