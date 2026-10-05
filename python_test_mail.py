import smtplib

EMAIL = "feliwambo2005@gmail.com"
PASSWORD = "ryuxnndmmgumcaf"


server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)

server.set_debuglevel(1)

server.ehlo()

server.starttls()

server.ehlo()

server.login(EMAIL, PASSWORD)

print("LOGIN SUCCESS")

server.quit()