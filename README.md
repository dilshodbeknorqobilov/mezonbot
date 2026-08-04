# mezonbot

sudo cp pdfbot.service /etc/systemd/system/
sudo nano /etc/systemd/system/pdfbot.service   # BOT_TOKEN va User ni to'g'rilang

sudo systemctl daemon-reload
sudo systemctl enable pdfbot
sudo systemctl start pdfbot