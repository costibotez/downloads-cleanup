#!/bin/bash
# Fills a folder with a fake, messy "Downloads" for the README screenshots.
# Uses macOS stock pictures and generated documents only, so no personal files appear in the screenshots.
#   bash docs/src/demo-files.sh /path/to/empty-folder
set -euo pipefail
OUT="${1:?usage: demo-files.sh <folder>}"
mkdir -p "$OUT"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PICS="/Library/User Pictures"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Photos with camera-style names, dated over the last two years.
n=4810
for f in "$PICS"/Animals/*.heic "$PICS"/Flowers/*.heic "$PICS"/Nature/*.heic "$PICS"/Fun/*.heic "$PICS"/Instruments/*.heic "$PICS"/Sports/*.heic; do
  n=$((n + 7))
  case $((n % 4)) in
    0) name="IMG_$n.heic" ;;
    1) name="$(uuidgen | tr 'A-Z' 'a-z').jpeg"; sips -s format jpeg "$f" --out "$OUT/$name" >/dev/null; touch -t "2025$(printf %02d $((n % 12 + 1)))1210$((n % 50 + 10))" "$OUT/$name"; continue ;;
    2) name="WhatsApp Image 2026-0$((n % 9 + 1))-1$((n % 9)) at 1$((n % 9)).2$((n % 9)).0$((n % 9)).jpeg"; sips -s format jpeg "$f" --out "$OUT/$name" >/dev/null; continue ;;
    3) name="$((n * 31337)).jpg"; sips -s format jpeg "$f" --out "$OUT/$name" >/dev/null; continue ;;
  esac
  cp "$f" "$OUT/$name"
  touch -t "2026$(printf %02d $((n % 9 + 1)))0$((n % 9 + 1))1200" "$OUT/$name"
done

# Two short b-roll clips made from the stock pictures.
clip() {  # clip <stock picture> <seconds> <output>
  sips -s format jpeg "$1" --out "$TMP/frame.jpg" >/dev/null
  ffmpeg -loglevel error -y -framerate 1 -i "$TMP/frame.jpg" -t "$2" -vf scale=720:720 -pix_fmt yuv420p "$3"
}
clip "$PICS/Nature/Leaf.heic" 4 "$OUT/IMG_5507.mov"
clip "$PICS/Flowers/Sunflower.heic" 3 "$OUT/VID_20260614_181102.mp4"

# A voice note.
say -o "$OUT/WhatsApp Audio 2026-10-20 at 18.02.11.m4a" --data-format=aac "Hey, it's me. Can you send the invoice from last week? Thanks!"

# PDFs with realistic text, rendered by Chrome.
pdf() {  # pdf <file name> <html body>
  printf '<html><body style="font:14px Helvetica;padding:48px;max-width:640px">%s</body></html>' "$2" > "$TMP/doc.html"
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$OUT/$1" "$TMP/doc.html" 2>/dev/null
}
for i in 1 2 3 4 5 6; do
  pdf "$((7000339240 + i * 13)).pdf" "<h1>FACTURA / INVOICE</h1><p>Seria NWS nr. 2026$i · Data facturii: 0$i.0$i.2026</p><p>Furnizor: Northwind Studio SRL<br>Client: Blue Harbor Media Ltd</p><table border=1 cellpadding=8><tr><td>Web design services</td><td>1,200.00 RON</td></tr><tr><td><b>Total de plata</b></td><td><b>1,428.00 RON</b></td></tr></table>"
done
pdf "Invoice-INV-0042.pdf" "<h1>Invoice INV-0042</h1><p>Amount due: £640.00 · Due 30 Nov 2026</p><p>Thank you for your business, Lakeside Coffee Co.</p>"
pdf "Receipt-2026-10-03.pdf" "<h1>Payment receipt</h1><p>Paid £12.99 to Cloud Storage Plus. Receipt #48213</p>"
pdf "statement_2026-09-01_2026-09-30.pdf" "<h1>Account statement</h1><p>Statement of account · September 2026 · IBAN RO00 DEMO 0000 0000 0000</p><p>Opening balance: 4,210.00 · Closing balance: 5,102.40</p>"
pdf "Extras_de_cont_08_2026.pdf" "<h1>Extras de cont</h1><p>Sold initial: 3,120.00 RON · Sold final: 4,210.00 RON</p>"
pdf "Service agreement - Blue Harbor (signed).pdf" "<h1>Service agreement</h1><p>This agreement is made between Northwind Studio SRL and Blue Harbor Media Ltd. Terms and conditions apply.</p>"
pdf "88f6b3cd1959aa4f5ff20c976efec82a.pdf" "<h1>Contract de prestari servicii</h1><p>Anexa 1 la contract. Partile au convenit urmatoarele...</p>"
pdf "Bilant_2025_Northwind.pdf" "<h1>Bilant anual 2025</h1><p>Balance sheet · Declaratia D101 depusa la ANAF</p>"
pdf "boarding-pass-OTP-LTN.pdf" "<h1>Boarding pass</h1><p>Flight W6 3001 · Bucharest OTP → London LTN · Seat 14C · Check-in closes 40 min before departure</p>"
pdf "1092941.pdf" "<h1>Product catalogue</h1><p>Autumn collection, pages 1-24.</p>"

# Office files, data, archives, code and installers.
printf 'Meeting notes\n\n- Launch date\n- Budget\n' > "$TMP/notes.txt"
textutil -convert docx "$TMP/notes.txt" -output "$OUT/Meeting notes (1).docx"
printf 'Brand brief\n\nTone: calm, confident.\n' > "$TMP/brief.txt"
textutil -convert docx "$TMP/brief.txt" -output "$OUT/Brand brief v3.docx"
printf 'name,email\nAlex,alex@example.com\nSam,sam@example.com\n' > "$OUT/newsletter-export-2026-10-01.csv"
printf '{"orders": 42}\n' > "$OUT/orders.json"
printf '<?php\necho "hello";\n' > "$OUT/functions.php"
printf '<!doctype html><title>Landing</title>\n' > "$OUT/landing-page.html"
for z in theme-child "Brand assets" project-export-final; do
  echo "$z" > "$TMP/readme.txt" && (cd "$TMP" && zip -q "$OUT/$z.zip" readme.txt)
done
cp "$OUT/theme-child.zip" "$OUT/theme-child (1).zip"
mkfile -n 1m "$OUT/Transmission-4.0.dmg"
printf 'BEGIN:VCALENDAR\nEND:VCALENDAR\n' > "$OUT/invite.ics"
: > "$OUT/IMG_6740.heic"   # a failed download

# A logo and a couple of screenshots.
sips -s format png "$PICS/Fun/Yin-Yang.heic" --out "$OUT/logo-final-v2.png" >/dev/null
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1440,900 --screenshot="$OUT/Screenshot 2026-10-12 at 09.41.22.png" "data:text/html,<h1 style='font:48px Helvetica;padding:60px'>Q4 dashboard</h1><p style='font:20px Helvetica;padding:0 60px'>Revenue up 12 percent. Signups 1,204. Churn 2.1 percent.</p>" 2>/dev/null
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1440,900 --screenshot="$OUT/Screenshot 2026-09-30 at 17.05.10.png" "data:text/html,<h1 style='font:48px Helvetica;padding:60px'>Checkout</h1><p style='font:20px Helvetica;padding:0 60px'>Order summary, shipping address, payment method.</p>" 2>/dev/null

# Everything older than the sorter's "still downloading" window.
find "$OUT" -type f -newermt "-5 minutes" -exec touch -t 202610010900 {} +
echo "Demo folder ready: $(find "$OUT" -maxdepth 1 -type f | wc -l | tr -d ' ') files in $OUT"
