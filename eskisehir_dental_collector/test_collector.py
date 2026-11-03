import unittest, tempfile
from pathlib import Path
from bs4 import BeautifulSoup
from unittest.mock import patch
from collector import official_records, record, merge, export, scrape_email

class FakeSession:
 def get(self,*args,**kwargs): raise RuntimeError('mock required')

class TestCollector(unittest.TestCase):
 def test_official_parsing(self):
  html='<table><tr><th>KURULUŞUN ADI</th><th>GÖREVİ</th><th>ADRESİ</th></tr><tr><td>Özel Test Ağız ve Diş Sağlığı Polikliniği</td><td>Ortodonti</td><td>Tepebaşı / Eskişehir</td></tr></table>'
  with patch('collector.fetch',return_value=BeautifulSoup(html,'html.parser')):
   rows=official_records(FakeSession())
  self.assertEqual(len(rows),2)
  self.assertEqual(rows[0]['İlçe'],'Tepebaşı')
 def test_merge_same_name_different_district(self):
  r1=record('Özel Modapol Ağız ve Diş Sağlığı Polikliniği','Poliklinik','url','Tepebaşı / Eskişehir')
  r2=record('Özel Modapol Ağız ve Diş Sağlığı Polikliniği','Poliklinik','url','Odunpazarı / Eskişehir')
  self.assertEqual(len(merge([r1,r2])),2)
 def test_merge_duplicate(self):
  a=record('Özel Test Diş Kliniği','Poliklinik','url','Tepebaşı / Eskişehir')
  b=record('Özel Test Diş Kliniği','Poliklinik','url2','Tepebaşı / Eskişehir')
  self.assertEqual(len(merge([a,b])),1)
 def test_xlsx(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'test.xlsx'; export([record('Özel Test Diş Kliniği','Poliklinik','url')],p)
   self.assertTrue(p.exists());self.assertGreater(p.stat().st_size,2000)

if __name__=='__main__': unittest.main()
