import qrcode

upi_url = "upi://pay?pa=muhammedrazi01091@oksbi&pn=FitFusion&am=19&cu=INR"

qr = qrcode.make(upi_url)
qr.save("fitfusion_upi_qr.png")

print("QR code created successfully!")