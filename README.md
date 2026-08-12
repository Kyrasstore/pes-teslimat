# PES / eFootball Hesap Teslimat Sistemi (Otomatik Gmail)

Alıcı “Kod İste” butonuna basınca site **otomatik olarak Gmail’e bağlanır** ve en son gelen doğrulama kodunu çeker.

## Nasıl Çalışır?

1. **Sen (Admin)**
   - `/admin` → şifre: `pes2026admin` (mutlaka değiştir)
   - Yeni hesap ekle → **Mail + Mail Şifresi**
   - Sistem otomatik teslimat kodu üretir
   - Bu kodu alıcıya ver

2. **Alıcı**
   - Siteye girer → teslimat kodunu yazar
   - Mail ve şifreyi görür
   - “**Kod İste**” butonuna basar
   - Site Gmail’e bağlanır → en yeni doğrulama kodunu bulur → gösterir

3. Sen hiçbir şey yapmak zorunda değilsin. Kodlar anlık gelir.

## Önemli: Gmail App Password

Gmail hesaplarında **2 Adımlı Doğrulama** açıksa normal şifre çalışmaz.

Çözüm:
1. Gmail hesabına gir
2. Google Hesap → Güvenlik → 2 Adımlı Doğrulama
3. En altta **Uygulama Şifreleri** (App Passwords) oluştur
4. 16 haneli şifreyi al
5. Sisteme **normal şifre yerine bu App Password**’ü yaz

2 Adımlı Doğrulama kapalıysa normal şifre de çalışabilir (Google bazen engeller).

## Yerel Test

```bash
cd pes_teslimat
python app.py
```

- Alıcı: http://127.0.0.1:5000
- Admin: http://127.0.0.1:5000/admin

## Gerçek Site (Ücretsiz - Render)

1. https://render.com → GitHub ile hesap aç
2. Bu klasörü GitHub’a yükle
3. New → Web Service
4. Build: `pip install flask`
5. Start: `python app.py`
6. Deploy → sana link verir

## Manuel Yedek

Admin panelde “Mevcut Kod” kutusuna elle kod yazarsan, otomatik Gmail yerine o kod gösterilir.  
Boş bırakırsan tamamen otomatik çalışır.

## Dosya Yapısı

```
pes_teslimat/
├── app.py
├── database.db          (otomatik oluşur)
├── templates/
│   ├── index.html
│   ├── delivery.html
│   ├── admin_login.html
│   └── admin_panel.html
└── README.md
```

## Notlar

- Kod arama: Son 30 dakikadaki maillere bakar
- 6 haneli kodları öncelikli arar
- Gmail IMAP kullanır (imap.gmail.com)
- Hata olursa alıcıya mesaj gösterir (“Mail girişi başarısız” vs.)

Sorun olursa söyle, ayarları değiştiririz.
